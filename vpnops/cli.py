"""Local CLI: SSH transport, safe exports, and real client protocol checks."""
import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import zlib

from .cloudflare import Cloudflare
from .model import OpsError, require, validate_config, validate_version

REPO = Path(__file__).resolve().parent.parent


def secure_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.is_symlink(), "拒绝覆盖符号链接")
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".vpn-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def bundle_source():
    return (REPO / "vpnops/model.py").read_text() + "\n" + (REPO / "vpnops/remote.py").read_text()


def ssh_args(c):
    require(shutil.which("ssh"), "请安装 OpenSSH 客户端")
    args = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
            "-p", str(c["ssh_port"])]
    if c["ssh_identity_file"]:
        key = Path(c["ssh_identity_file"]).expanduser().resolve()
        require(key.is_file(), "SSH 私钥路径不存在")
        args += ["-i", str(key), "-o", "IdentitiesOnly=yes"]
    return args + [c["ssh_user"] + "@" + c["server_ip"]]


def remote(c, command, **extras):
    source = bundle_source()
    encoded = base64.b64encode(zlib.compress(source.encode())).decode()
    loader = "import base64,zlib;exec(zlib.decompress(base64.b64decode(" + repr(encoded) + ")))"
    interpreter = ["python3", "-c", loader]
    if c["ssh_user"] != "root":
        interpreter = ["sudo", "-n", *interpreter]
    payload = {"command": command, "config": c, **extras}
    if command == "deploy":
        payload["source"] = source
    try:
        r = subprocess.run([*ssh_args(c), shlex.join(interpreter)], input=json.dumps(payload),
                           capture_output=True, text=True, timeout=2400)
    except subprocess.TimeoutExpired:
        raise OpsError("SSH 操作超时；服务端可能仍在执行，先检查状态，不要并发重试") from None
    try:
        result = json.loads(r.stdout)
    except ValueError:
        # SSH diagnostic messages contain no credentials, but don't blindly echo remote banners.
        raise OpsError("SSH 未返回有效结果。先验证已知主机指纹、公钥登录、Python 3.10+ 与免密 sudo；不要关闭主机校验") from None
    if r.returncode not in (0, 2) or "error" in result:
        raise OpsError(result.get("error", "远程命令失败"))
    return result


def export_clients(c, output):
    data = remote(c, "export")
    directory = Path(output).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Do not chmod an arbitrary existing user directory; each generated file is private.
    secure_write(directory / "mihomo.yaml", json.dumps(data["mihomo"], indent=2, ensure_ascii=False) + "\n")
    secure_write(directory / "shadowrocket.txt", data["links"])
    return {"ok": True, "files": [str(directory / "mihomo.yaml"), str(directory / "shadowrocket.txt")],
            "contains_secrets": True, "client_dns": "开启客户端 TUN 后进行设备 DNS 验收"}


def verify_clients(c, path, binary):
    executable = shutil.which(binary) or str(Path(binary).expanduser().resolve())
    require(Path(executable).is_file(), "找不到 mihomo 核心；先从官方 Release 安装对应平台二进制")
    require(shutil.which("curl"), "真实客户端验证需要 curl")
    data = json.loads(Path(path).read_text())
    require({p["name"] for p in data["proxies"]} == {"Reality", "Hysteria2", "WebSocket"}, "需要本项目导出的三线路客户端配置")
    results = []
    for proxy in data["proxies"]:
        proxy = dict(proxy)
        if proxy["name"] != "WebSocket":
            proxy["server"] = c["server_ip"]  # avoid local fake-IP DNS loops for direct entries
        with tempfile.TemporaryDirectory(prefix="vpn-ai-verify-") as tmp:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            config = {"mixed-port": port, "bind-address": "127.0.0.1", "allow-lan": False,
                      "mode": "rule", "log-level": "error", "ipv6": False,
                      "proxies": [proxy], "rules": ["MATCH," + proxy["name"]],
                      "dns": {"enable": False}, "tun": {"enable": False}}
            file = Path(tmp) / "test.yaml"
            secure_write(file, json.dumps(config))
            test = subprocess.run([executable, "-t", "-d", tmp, "-f", str(file)], capture_output=True, timeout=30)
            if test.returncode:
                results.append({"line": proxy["name"], "ok": False, "reason": "客户端配置检查失败"})
                continue
            process = subprocess.Popen([executable, "-d", tmp, "-f", str(file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                ready = False
                for _ in range(30):
                    if process.poll() is not None:
                        break
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            ready = True
                            break
                    except OSError:
                        time.sleep(0.1)
                if not ready:
                    results.append({"line": proxy["name"], "ok": False, "reason": "客户端启动失败"})
                    continue
                response = subprocess.run(["curl", "--silent", "--show-error", "--fail", "--noproxy", "",
                                           "--proxy", f"socks5h://127.0.0.1:{port}", "--max-time", "25",
                                           "https://api.ipify.org"], capture_output=True, text=True, timeout=30)
                exit_ip = response.stdout.strip()
                try:
                    exit_ip = str(ipaddress.IPv4Address(exit_ip))
                except ValueError:
                    exit_ip = None
                results.append({"line": proxy["name"], "ok": response.returncode == 0 and exit_ip == c["server_ip"],
                                "exit_ip": exit_ip, "expected_ip": c["server_ip"]})
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    return {"ok": all(x["ok"] for x in results), "protocol_tests": results,
            "client_dns": "NOT_TESTED: 必须在用户设备开启 TUN 后单独验证"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI 驱动 VPN 部署与维护（先读 AGENTS.md）")
    parser.add_argument("--config", default="config.local.json", help="本地私有配置文件")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["init", "plan", "preflight", "deploy", "status", "backup"]:
        sub.add_parser(name)
    p = sub.add_parser("upgrade")
    p.add_argument("--version", required=True)
    p = sub.add_parser("rollback")
    p.add_argument("--backup", required=True, help="服务器返回的备份文件名，非任意路径")
    p = sub.add_parser("export")
    p.add_argument("--output", default="artifacts")
    p = sub.add_parser("verify")
    p.add_argument("--client", default="artifacts/mihomo.yaml")
    p.add_argument("--mihomo", default="mihomo")
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    if args.command == "init":
        require(not config_path.exists(), "配置已存在，不覆盖")
        secure_write(config_path, (REPO / "config.example.json").read_text())
        result = {"ok": True, "config": str(config_path), "next": "填写资源参数后运行 plan；先按 README 验证 SSH 主机指纹"}
    else:
        require(config_path.is_file(), "配置不存在，请先运行 init")
        c = validate_config(json.loads(config_path.read_text()))
        if args.command == "plan":
            result = {"ok": True, "target": c["server_ip"], "image_tag": "v" + c["sing_box_version"],
                      "dns": [{"name": c["vpn_domain"], "proxied": False}, {"name": c["ws_domain"], "proxied": True}],
                      "server_directory": "/opt/vpn-ai-ops", "ports": [f"{c['ssh_port']}/tcp", "443/tcp", "443/udp", "8443/tcp"],
                      "maintenance": ["acme.sh 证书续期", "每日巡检", "每周备份，保留 8 份"],
                      "mutations": ["创建缺失 DNS", "安装 Docker（若缺失）及基础依赖", "添加 UFW 规则（不启用/重置）", "启动自身容器和维护定时器"],
                      "network_requests": False}
        elif args.command in ["preflight", "deploy"]:
            require(ipaddress.IPv4Address(c["server_ip"]).is_global and c["zone_id"] != "0" * 32,
                    "请先替换示例 IP 和 Zone ID")
            token = os.environ.get("CF_API_TOKEN", "")
            cf = Cloudflare(token, c["zone_id"])
            server = remote(c, "preflight")
            dns = cf.plan(c)
            if args.command == "preflight":
                result = {"ok": True, "server": server, "dns_plan": dns}
            else:
                print("预检通过，开始 DNS 与服务端部署；可能需要数分钟。", file=__import__("sys").stderr, flush=True)
                cf.ensure(c)
                result = remote(c, "deploy", token=token)
                if result["ok"]:
                    result["clients"] = export_clients(c, "artifacts")
        elif args.command == "export":
            result = export_clients(c, args.output)
        elif args.command == "verify":
            result = verify_clients(c, args.client, args.mihomo)
        elif args.command == "upgrade":
            result = remote(c, "upgrade", version=validate_version(args.version))
            if result["ok"]:
                c["sing_box_version"] = result["version"]
                secure_write(config_path, json.dumps(c, indent=2) + "\n")
        elif args.command == "rollback":
            result = remote(c, "rollback", backup=args.backup)
            if result["ok"]:
                c["sing_box_version"] = result["version"]
                secure_write(config_path, json.dumps(c, indent=2) + "\n")
        else:
            result = remote(c, args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 2
