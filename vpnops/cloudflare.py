"""Cloudflare DNS operations. Conflicting records are never overwritten."""
import json
import urllib.error
import urllib.parse
import urllib.request

from .model import OpsError, require


class Cloudflare:
    def __init__(self, token, zone_id):
        require(bool(token) and not any(x in token for x in "\r\n"), "请通过环境变量 CF_API_TOKEN 提供有效 Token")
        self.token, self.zone_id = token, zone_id

    def request(self, method, suffix, body=None):
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/zones/" + self.zone_id + suffix,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "User-Agent": "vpn-ai-ops/0.1"},
            method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.load(response)
        except urllib.error.HTTPError as e:
            raise OpsError(f"Cloudflare API HTTP {e.code}；检查 Token 的 Zone/DNS/Zone Settings 权限和资源范围") from None
        except (OSError, ValueError):
            raise OpsError("Cloudflare API 网络或响应错误") from None
        require(data.get("success"), "Cloudflare API 拒绝操作；检查权限和 Zone")
        return data["result"]

    def plan(self, c):
        zone = self.request("GET", "")
        require(zone["name"] == c["base_domain"] and zone["status"] == "active", "Zone 域名不匹配或尚未激活")
        ssl = self.request("GET", "/settings/ssl")
        require(ssl["value"] == "strict", "请在 Cloudflare 将 SSL/TLS 设为 Full (strict)，项目不会修改全站设置")
        actions = []
        for domain, proxied in [(c["vpn_domain"], False), (c["ws_domain"], True)]:
            records = self.request("GET", "/dns_records?" + urllib.parse.urlencode({"name": domain, "per_page": 100}))
            relevant = [x for x in records if x["type"] in ["A", "AAAA", "CNAME"]]
            desired = {"type": "A", "name": domain, "content": c["server_ip"], "ttl": 1, "proxied": proxied}
            if relevant:
                require(len(relevant) == 1 and all(relevant[0].get(k) == desired[k] for k in ["type", "name", "content", "proxied"]),
                        f"DNS 冲突：{domain} 已有不同的 A/AAAA/CNAME 或代理状态；请先审查，不自动覆盖")
            actions.append({"action": "keep" if relevant else "create", "record": desired})
        return actions

    def ensure(self, c):
        # Inspect BOTH names before the first mutation; re-read to reduce races.
        actions = self.plan(c)
        for action in actions:
            if action["action"] == "create":
                self.request("POST", "/dns_records", action["record"])
        return actions
