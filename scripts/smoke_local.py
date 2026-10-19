#!/usr/bin/env python3
"""Disposable local protocol smoke test; never connects to a user's VPS.

Requires local Docker, OpenSSL, curl and an official mihomo binary. The test
uses a temporary self-signed cert with verification disabled ONLY in this
test's Hysteria2/WebSocket clients. Production templates keep verification on.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vpnops.cli import secure_write
from vpnops.model import server_config, client_config


def run(args, timeout=120):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        # Test data only; never point this helper at a production configuration.
        raise RuntimeError(f"{args[0]} failed with exit {r.returncode}; {(r.stdout + r.stderr)[:600]}")
    return r.stdout.strip()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mihomo", required=True)
    args = parser.parse_args()
    core = str(Path(args.mihomo).resolve())
    repo = Path(__file__).resolve().parents[1]
    config = json.loads((repo / "config.example.json").read_text())
    image = "ghcr.io/sagernet/sing-box:v" + config["sing_box_version"]
    print("Pulling pinned official sing-box image…", flush=True)
    run(["docker", "pull", image], 600)
    generated = run(["docker", "run", "--rm", image, "generate", "reality-keypair"])
    keys = {"uuid": str(uuid.uuid4()), "private_key": re.search(r"PrivateKey:\s*(\S+)", generated)[1],
            "public_key": re.search(r"PublicKey:\s*(\S+)", generated)[1], "short_id": secrets.token_hex(8),
            "hy2_password": secrets.token_urlsafe(24), "ws_path": "/" + secrets.token_urlsafe(16)}
    name = "vpn-ai-ops-smoke-" + secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix="vpn-ai-ops-smoke-") as tmp:
        root = Path(tmp)
        certs = root / "certs"
        certs.mkdir()
        run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-keyout", str(certs / "key.pem"), "-out", str(certs / "fullchain.pem"),
             "-subj", "/CN=example.com"])
        os.chmod(certs / "key.pem", 0o600)
        server = server_config(config, keys)
        secure_write(root / "config.json", json.dumps(server))
        volumes = ["-v", f"{root}:/etc/sing-box:ro"]
        run(["docker", "run", "--rm", *volumes, image, "check", "-c", "/etc/sing-box/config.json"])
        # Check the unmodified production client template with the real client core.
        client = client_config(config, keys)
        secure_write(root / "production.yaml", json.dumps(client))
        run([core, "-t", "-d", tmp, "-f", str(root / "production.yaml")])
        print("Production server/client configuration checks passed.", flush=True)
        tcp, udp, ws = free_port(), free_port(), free_port()
        run(["docker", "run", "-d", "--name", name, "--read-only", "--cap-drop", "ALL", "--cap-add", "NET_BIND_SERVICE",
             "--security-opt", "no-new-privileges:true", *volumes,
             "-p", f"127.0.0.1:{tcp}:443/tcp", "-p", f"127.0.0.1:{udp}:443/udp",
             "-p", f"127.0.0.1:{ws}:8443/tcp", image, "run", "-c", "/etc/sing-box/config.json"])
        try:
            time.sleep(2)
            results = []
            for production_proxy, port in zip(client["proxies"], [tcp, udp, ws]):
                proxy = copy.deepcopy(production_proxy)
                proxy.update(server="127.0.0.1", port=port)
                if proxy["name"] != "Reality":
                    proxy["skip-cert-verify"] = True  # TEST CERT ONLY
                socks = free_port()
                case = root / proxy["name"]
                case.mkdir()
                test = {"mixed-port": socks, "bind-address": "127.0.0.1", "allow-lan": False,
                        "log-level": "error", "proxies": [proxy], "rules": ["MATCH," + proxy["name"]],
                        "tun": {"enable": False}, "dns": {"enable": False}}
                secure_write(case / "client.yaml", json.dumps(test))
                process = subprocess.Popen([core, "-d", str(case), "-f", str(case / "client.yaml")],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    time.sleep(1)
                    require_running = process.poll() is None
                    status = run(["curl", "--silent", "--show-error", "--fail", "--noproxy", "",
                                  "--proxy", f"socks5h://127.0.0.1:{socks}", "--max-time", "30",
                                  "--output", "/dev/null", "--write-out", "%{http_code}", "https://example.com"], 35)
                    ok = require_running and status == "200"
                    results.append(ok)
                    print(json.dumps({"protocol": proxy["name"], "http": status, "ok": ok}), flush=True)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            return 0 if all(results) else 1
        finally:
            run(["docker", "rm", "-f", name])


if __name__ == "__main__":
    sys.exit(main())
