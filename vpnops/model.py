"""Pure configuration builders. This file is also bundled into the remote agent."""
import ipaddress
import json
import re
from urllib.parse import quote, urlencode

ROOT = "/opt/vpn-ai-ops"
IMAGE = "ghcr.io/sagernet/sing-box"
CONTAINER = "vpn-ai-ops-sing-box"
FIELDS = {"server_ip", "ssh_user", "ssh_port", "ssh_identity_file", "zone_id",
          "base_domain", "vpn_domain", "ws_domain", "acme_email",
          "sing_box_version", "reality_server"}


class OpsError(Exception):
    """An actionable error whose text is safe to print."""


def require(condition, message):
    if not condition:
        raise OpsError(message)


def validate_version(version):
    require(isinstance(version, str) and re.fullmatch(r"[1-9]\d*\.\d+\.\d+", version),
            "版本必须是精确稳定版，例如 1.13.14；不接受 latest、v 前缀或预发布版")
    return version


def validate_config(c):
    require(isinstance(c, dict) and set(c) == FIELDS, "配置字段必须与 config.example.json 完全一致；秘密只放环境变量")
    require(isinstance(c["server_ip"], str), "server_ip 必须是 IPv4 字符串")
    try:
        ipaddress.IPv4Address(c["server_ip"])
    except (ValueError, TypeError):
        raise OpsError("server_ip 必须是 IPv4 地址") from None
    require(isinstance(c["ssh_user"], str) and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", c["ssh_user"]), "非法 SSH 用户名")
    require(type(c["ssh_port"]) is int and 1 <= c["ssh_port"] <= 65535, "非法 SSH 端口")
    require(c["ssh_port"] not in [443, 8443], "SSH 端口不能与代理监听端口冲突")
    require(isinstance(c["ssh_identity_file"], str) and not any(x in c["ssh_identity_file"] for x in "\r\n\x00"), "非法私钥路径")
    require(isinstance(c["zone_id"], str) and re.fullmatch(r"[0-9a-f]{32}", c["zone_id"]), "Zone ID 必须是 32 位小写十六进制")
    for field in ["base_domain", "vpn_domain", "ws_domain", "reality_server"]:
        domain = c[field]
        require(isinstance(domain, str) and len(domain) <= 253 and "." in domain and
                all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in domain.split(".")),
                f"{field} 必须是小写 ASCII/Punycode 域名")
    for field in ["vpn_domain", "ws_domain"]:
        require(c[field].endswith("." + c["base_domain"]), f"{field} 必须是 base_domain 的子域名")
    require(c["vpn_domain"] != c["ws_domain"], "两个入口必须使用不同子域名")
    require(isinstance(c["acme_email"], str) and re.fullmatch(r"[a-zA-Z0-9._+%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", c["acme_email"]), "非法 ACME 邮箱")
    validate_version(c["sing_box_version"])
    return c


def server_config(c, keys):
    tls = {"enabled": True, "certificate_path": "/etc/sing-box/certs/fullchain.pem",
           "key_path": "/etc/sing-box/certs/key.pem"}
    return {
        "log": {"level": "warn", "timestamp": True},
        "inbounds": [
            {"type": "vless", "tag": "reality", "listen": "0.0.0.0", "listen_port": 443,
             "users": [{"uuid": keys["uuid"], "flow": "xtls-rprx-vision"}],
             "tls": {"enabled": True, "server_name": c["reality_server"],
                     "reality": {"enabled": True, "handshake": {"server": c["reality_server"], "server_port": 443},
                                 "private_key": keys["private_key"], "short_id": [keys["short_id"]]}}},
            {"type": "hysteria2", "tag": "hysteria2", "listen": "0.0.0.0", "listen_port": 443,
             "users": [{"password": keys["hy2_password"]}], "tls": dict(tls, alpn=["h3"])},
            {"type": "vless", "tag": "websocket", "listen": "0.0.0.0", "listen_port": 8443,
             "users": [{"uuid": keys["uuid"]}], "tls": tls,
             "transport": {"type": "ws", "path": keys["ws_path"]}}
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}]
    }


def compose_config(image):
    require(re.fullmatch(re.escape(IMAGE) + r"@sha256:[0-9a-f]{64}", image), "部署镜像必须解析成官方仓库 digest")
    return {"name": "vpn-ai-ops", "services": {"sing-box": {
        "image": image, "container_name": CONTAINER, "restart": "unless-stopped",
        "command": ["run", "-c", "/etc/sing-box/config.json"],
        "ports": ["0.0.0.0:443:443/tcp", "0.0.0.0:443:443/udp", "0.0.0.0:8443:8443/tcp"],
        "volumes": [f"{ROOT}/config:/etc/sing-box:ro", f"{ROOT}/certs:/etc/sing-box/certs:ro"],
        "read_only": True, "cap_drop": ["ALL"], "cap_add": ["NET_BIND_SERVICE"],
        "security_opt": ["no-new-privileges:true"], "pids_limit": 128,
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}
    }}}


def client_config(c, keys):
    proxies = [
        {"name": "Reality", "type": "vless", "server": c["vpn_domain"], "port": 443,
         "uuid": keys["uuid"], "network": "tcp", "tls": True, "udp": True,
         "flow": "xtls-rprx-vision", "servername": c["reality_server"], "client-fingerprint": "chrome",
         "reality-opts": {"public-key": keys["public_key"], "short-id": keys["short_id"]}},
        {"name": "Hysteria2", "type": "hysteria2", "server": c["vpn_domain"], "port": 443,
         "password": keys["hy2_password"], "sni": c["vpn_domain"], "alpn": ["h3"], "skip-cert-verify": False},
        {"name": "WebSocket", "type": "vless", "server": c["ws_domain"], "port": 8443,
         "uuid": keys["uuid"], "network": "ws", "tls": True, "udp": True,
         "servername": c["ws_domain"], "ws-opts": {"path": keys["ws_path"], "headers": {"Host": c["ws_domain"]}}}
    ]
    return {
        "mixed-port": 7890, "allow-lan": False, "mode": "rule", "ipv6": False, "log-level": "warning",
        "tun": {"enable": False, "stack": "mixed", "auto-route": True,
                "auto-detect-interface": True, "dns-hijack": ["any:53", "tcp://any:53"]},
        "dns": {"enable": True, "listen": "127.0.0.1:1053", "ipv6": False,
                "respect-rules": True, "enhanced-mode": "fake-ip", "fake-ip-range": "198.18.0.1/16",
                "fake-ip-filter": ["*.lan", "*.local", c["vpn_domain"], c["ws_domain"]],
                "default-nameserver": ["223.5.5.5", "119.29.29.29"],
                "proxy-server-nameserver": ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
                "direct-nameserver": ["https://dns.alidns.com/dns-query"],
                "nameserver": ["https://1.1.1.1/dns-query", "https://8.8.8.8/dns-query"]},
        "proxies": proxies,
        "proxy-groups": [
            {"name": "PROXY", "type": "select", "proxies": ["Reality", "WebSocket", "Hysteria2", "AUTO"]},
            {"name": "AUTO", "type": "fallback", "proxies": ["Reality", "WebSocket", "Hysteria2"],
             "url": "https://www.gstatic.com/generate_204", "interval": 300}],
        "rules": [f"DOMAIN,{c['vpn_domain']},DIRECT", f"DOMAIN,{c['ws_domain']},DIRECT",
                  f"IP-CIDR,{c['server_ip']}/32,DIRECT,no-resolve", "DOMAIN,dns.alidns.com,DIRECT", "DOMAIN,doh.pub,DIRECT",
                  "DOMAIN-SUFFIX,lan,DIRECT", "DOMAIN-SUFFIX,local,DIRECT", "DOMAIN-SUFFIX,cn,DIRECT",
                  "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve", "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
                  "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve", "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
                  "MATCH,PROXY"]
    }


def client_links(c, k):
    def vless(host, port, args, name):
        return f"vless://{quote(k['uuid'], safe='')}@{host}:{port}?{urlencode(args)}#{quote(name)}"
    return "\n".join([
        vless(c["vpn_domain"], 443, {"encryption": "none", "security": "reality", "type": "tcp",
              "sni": c["reality_server"], "fp": "chrome", "pbk": k["public_key"],
              "sid": k["short_id"], "flow": "xtls-rprx-vision"}, "Reality"),
        f"hysteria2://{quote(k['hy2_password'], safe='')}@{c['vpn_domain']}:443?" +
        urlencode({"sni": c["vpn_domain"], "alpn": "h3", "insecure": "0"}) + "#Hysteria2",
        vless(c["ws_domain"], 8443, {"encryption": "none", "security": "tls", "type": "ws",
              "sni": c["ws_domain"], "host": c["ws_domain"], "path": k["ws_path"]}, "WebSocket")
    ]) + "\n"
