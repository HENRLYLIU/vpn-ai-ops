#!/usr/bin/env python3
"""Conservative public-tree guard. Does not replace a real secret scanner/review."""
import ipaddress
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def scan():
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    findings = []
    forbidden = {"artifacts", "backups", ".tools", "credentials", "secrets", ".project-context"}
    for name in sorted(set(filter(None, files))):
        path = ROOT / name
        if not path.is_file():
            continue
        if (set(Path(name).parts) & forbidden or Path(name).name == "config.local.json" or
                (Path(name).name.startswith(".env") and Path(name).name != ".env.example") or
                path.suffix in [".pem", ".key", ".gz", ".db"]):
            findings.append((name, "private artifact included"))
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            findings.append((name, "unexpected binary"))
            continue
        patterns = [r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"(?:vless|hysteria2)://[0-9a-f-]{36}@",
                    r"(?i)(?:CF_API_TOKEN|CF_Token)\s*=\s*['\"][A-Za-z0-9_-]{30,}['\"]"]
        if any(re.search(p, text) for p in patterns):
            findings.append((name, "possible credential"))
        # Public IPv4s used by the generic DNS templates are explicitly allowed.
        allow = {"1.1.1.1", "8.8.8.8", "223.5.5.5", "119.29.29.29"}
        for value in re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", text):
            try:
                ip = ipaddress.ip_address(value)
            except ValueError:
                continue
            if ip.is_global and value not in allow:
                findings.append((name, "unexpected public IPv4; review manually"))
                break
    for name, reason in findings:
        print(f"FAIL {name}: {reason}")  # never print matched secret text
    if not findings:
        print(f"PASS: {len(set(filter(None, files)))} public files checked; ignored private paths excluded")
    return bool(findings)


if __name__ == "__main__":
    sys.exit(scan())
