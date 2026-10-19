"""Root-side executor. No shell interpolation of user input and no secret stdout."""
import datetime
import fcntl
import hashlib
import io
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import uuid

if __package__:
    from .model import (ROOT, IMAGE, CONTAINER, OpsError, require, validate_config,
                        validate_version, server_config, compose_config, client_config, client_links)
    import json
    import re

BASE = Path(ROOT)
ACME_VERSION = "3.1.6"
ACME_SHA256 = "0d3f9000ac44a6331314742a88c475f79134e24fc991997883652adc59efc486"
MANAGED = "vpn-ai-ops/v1"


def write_private(path, content, mode=0o600):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path, obj):
    write_private(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def run(args, label, timeout=120, env=None, cwd=None, allowed=(0,)):
    try:
        r = subprocess.run(args, text=True, capture_output=True, timeout=timeout, env=env, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        raise OpsError(f"{label}：执行失败或超时；请检查依赖和网络") from None
    if r.returncode not in allowed:
        if (BASE / "state.json").exists():
            write_private(BASE / "last-error.log", r.stdout + r.stderr)
        raise OpsError(f"{label}失败，退出码 {r.returncode}；脱敏排查服务端 last-error.log，禁止原文粘贴")
    return r.stdout.strip()


def compose(*args):
    return run(["docker", "compose", "-f", str(BASE / "compose.json"), *args], "Compose " + args[0], timeout=300)


def load_state():
    require((BASE / "state.json").is_file(), "未发现本项目管理的部署")
    s = json.loads((BASE / "state.json").read_text())
    require(s.get("manager") == MANAGED, "目录不是本项目管理，拒绝操作")
    validate_config(s["config"])
    return s


def require_identity(c, state):
    for key in ["server_ip", "vpn_domain", "ws_domain", "zone_id", "base_domain", "reality_server", "acme_email"]:
        require(c[key] == state["config"][key], f"{key} 与受管部署不一致；域名迁移需要单独方案")


def preflight(c):
    require(os.geteuid() == 0, "服务器需要 root 或免密 sudo 权限")
    os_info = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    require(os_info.get("ID", "").strip('"') == "ubuntu" and os_info.get("VERSION_ID", "").strip('"') == "24.04",
            "首版仅支持 Ubuntu 24.04；不会尝试改造其他系统")
    require(shutil.disk_usage("/opt").free >= 2 * 1024**3, "至少需要 2 GiB 可用磁盘")
    mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    require(int(mem["MemTotal"].split()[0]) >= 450000, "至少需要 512 MiB 级别的 VPS")
    if shutil.which("crontab"):
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        active_acme = [x for x in cron.stdout.splitlines() if "acme.sh" in x and "--cron" in x and not x.lstrip().startswith("#")]
        require(all(str(BASE / "acme") in x for x in active_acme),
                "发现其他 acme.sh 续期任务；首版不接管或影响已有证书账户")
    owned_running = False
    if BASE.exists():
        state = load_state()
        require_identity(c, state)
        if shutil.which("docker"):
            r = subprocess.run(["docker", "inspect", CONTAINER], capture_output=True, text=True)
            if r.returncode == 0:
                container = json.loads(r.stdout)[0]
                labels = container["Config"].get("Labels") or {}
                require(labels.get("com.docker.compose.project") == "vpn-ai-ops", "同名容器不属于本项目")
                owned_running = container["State"]["Running"]
    elif Path("/opt/sing-box").exists():
        raise OpsError("检测到已有 /opt/sing-box；首版不自动迁移已有代理服务")
    if not owned_running:
        for port, kind in [(443, socket.SOCK_STREAM), (443, socket.SOCK_DGRAM), (8443, socket.SOCK_STREAM)]:
            with socket.socket(socket.AF_INET, kind) as sock:
                try:
                    sock.bind(("0.0.0.0", port))
                except OSError:
                    raise OpsError(f"端口 {port}/{'udp' if kind == socket.SOCK_DGRAM else 'tcp'} 已占用，拒绝覆盖") from None
    # Verify the Reality target can negotiate TLS 1.3 before any mutation.
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    try:
        with socket.create_connection((c["reality_server"], 443), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=c["reality_server"]):
                pass
    except OSError:
        raise OpsError("Reality 目标无法通过 TLS 1.3 校验；先检查目标和网络") from None
    return {"ok": True, "os": "Ubuntu 24.04", "managed": BASE.exists(),
            "cloud_security_group": "须在云控制台允许 SSH、443/tcp、443/udp、8443/tcp"}


def install_docker():
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    run(["apt-get", "update"], "刷新 apt 索引", 300, env=env)
    run(["apt-get", "install", "-y", "ca-certificates", "curl", "openssl", "cron", "ufw"], "安装基础依赖", 600, env=env)
    if not shutil.which("docker"):
        for pkg in ["docker.io", "docker-compose", "podman-docker", "containerd", "runc"]:
            r = subprocess.run(["dpkg-query", "-W", "-f=${Status}", pkg], capture_output=True, text=True)
            require("install ok installed" not in r.stdout, f"发现冲突包 {pkg}，不自动卸载")
        Path("/etc/apt/keyrings").mkdir(mode=0o755, exist_ok=True)
        run(["curl", "-fsSL", "--max-time", "60", "https://download.docker.com/linux/ubuntu/gpg", "-o", "/etc/apt/keyrings/docker.asc"], "下载 Docker 官方签名")
        os.chmod("/etc/apt/keyrings/docker.asc", 0o644)
        arch = run(["dpkg", "--print-architecture"], "检查架构")
        require(arch in ["amd64", "arm64"], "只支持 amd64 / arm64")
        write_private("/etc/apt/sources.list.d/vpn-ai-ops-docker.sources",
                      f"Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: noble\nComponents: stable\nArchitectures: {arch}\nSigned-By: /etc/apt/keyrings/docker.asc\n", 0o644)
        run(["apt-get", "update"], "刷新 Docker 索引", 300, env=env)
        run(["apt-get", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"], "安装 Docker 官方软件包", 900, env=env)
    run(["docker", "info"], "验证 Docker")
    run(["docker", "compose", "version"], "验证 Compose")
    run(["systemctl", "enable", "--now", "cron"], "启用证书续期调度")


def resolve_image(version):
    validate_version(version)
    tag = f"{IMAGE}:v{version}"
    run(["docker", "pull", tag], "拉取固定版本 sing-box", 600)
    data = json.loads(run(["docker", "image", "inspect", tag], "读取镜像摘要"))[0]
    digest = next((x for x in data.get("RepoDigests", []) if x.startswith(IMAGE + "@sha256:")), None)
    require(digest is not None, "官方镜像 digest 缺失")
    compose_config(digest)  # validate origin and digest
    return digest


def generate_keys(image):
    output = run(["docker", "run", "--rm", "--network", "none", image, "generate", "reality-keypair"], "生成 Reality 密钥")
    private = re.search(r"PrivateKey:\s*([\w-]+)", output)
    public = re.search(r"PublicKey:\s*([\w-]+)", output)
    require(private and public, "无法解析 Reality 密钥生成结果")
    return {"uuid": str(uuid.uuid4()), "private_key": private[1], "public_key": public[1],
            "short_id": secrets.token_hex(8), "hy2_password": secrets.token_urlsafe(32),
            "ws_path": "/" + secrets.token_urlsafe(24)}


def install_certificate(c, token):
    home = BASE / "acme"
    acme = home / "acme.sh"
    if not acme.exists():
        url = f"https://codeload.github.com/acmesh-official/acme.sh/tar.gz/refs/tags/{ACME_VERSION}"
        with urllib.request.urlopen(url, timeout=60) as response:
            archive = response.read(4 * 1024**2)
        require(hashlib.sha256(archive).hexdigest() == ACME_SHA256, "acme.sh 源码摘要不匹配，已停止")
        with tempfile.TemporaryDirectory(dir=BASE) as tmp:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
                for member in tar.getmembers():
                    name = Path(member.name)
                    require(not name.is_absolute() and ".." not in name.parts and not member.issym() and not member.islnk(), "acme.sh 压缩包存在不安全路径")
                    require(member.isfile() or member.isdir(), "acme.sh 压缩包包含特殊文件")
                tar.extractall(tmp)
            src = Path(tmp) / f"acme.sh-{ACME_VERSION}"
            run(["sh", str(src / "acme.sh"), "--install", "--home", str(home), "--config-home", str(home),
                 "--accountemail", c["acme_email"], "--no-profile"], "安装固定版本 acme.sh", 120, cwd=src)
    env = dict(os.environ, CF_Token=token, CF_Zone_ID=c["zone_id"])
    run([str(acme), "--issue", "--home", str(home), "--server", "letsencrypt", "--dns", "dns_cf",
         "-d", c["vpn_domain"], "-d", c["ws_domain"], "--keylength", "ec-256", "--dnssleep", "60"],
        "DNS-01 证书签发", 900, env=env, allowed=(0, 2))
    reload_cmd = f"if /usr/bin/docker inspect {CONTAINER} >/dev/null 2>&1; then /usr/bin/docker restart {CONTAINER} >/dev/null; fi"
    run([str(acme), "--install-cert", "--home", str(home), "-d", c["vpn_domain"], "--ecc",
         "--key-file", str(BASE / "certs/key.pem"), "--fullchain-file", str(BASE / "certs/fullchain.pem"),
         "--reloadcmd", reload_cmd], "安装证书及续期回调", 120, env=env)
    for folder in [home, BASE / "certs"]:
        os.chmod(folder, 0o700)
        for p in folder.rglob("*"):
            if p.is_file() and (p.suffix in [".conf", ".key", ".pem", ".cer"]):
                os.chmod(p, 0o600)


def check_config(image=None):
    image = image or load_state()["image"]
    run(["docker", "run", "--rm", "--network", "none", "-v", f"{BASE}/config:/etc/sing-box:ro",
         "-v", f"{BASE}/certs:/etc/sing-box/certs:ro", image, "check", "-c", "/etc/sing-box/config.json"], "sing-box 配置校验")
    compose("config", "--quiet")


def wait_running():
    for _ in range(10):
        time.sleep(1)
        data = json.loads(run(["docker", "inspect", CONTAINER], "读取容器状态"))[0]
        if not data["State"]["Running"] or data["State"].get("Restarting") or data["RestartCount"]:
            raise OpsError("容器未稳定运行；请查看脱敏日志")


def install_timers(source):
    require(source and "def remote_main(" in source, "远程执行器源码缺失")
    write_private(BASE / "agent.py", source, 0o700)
    for job, schedule in [("health", "daily"), ("backup", "weekly")]:
        prefix = f"vpn-ai-ops-{job}"
        write_private(f"/etc/systemd/system/{prefix}.service", f"""[Unit]
Description=VPN AI Ops {job}
After=docker.service network-online.target
[Service]
Type=oneshot
UMask=0077
ExecStart=/usr/bin/python3 {ROOT}/agent.py scheduled-{job}
TimeoutStartSec=600
""", 0o644)
        write_private(f"/etc/systemd/system/{prefix}.timer", f"""[Unit]
Description=VPN AI Ops scheduled {job}
[Timer]
OnCalendar={schedule}
RandomizedDelaySec=1800
Persistent=true
[Install]
WantedBy=timers.target
""", 0o644)
    run(["systemctl", "daemon-reload"], "加载维护定时器")
    run(["systemctl", "enable", "--now", "vpn-ai-ops-health.timer", "vpn-ai-ops-backup.timer"], "启用维护定时器")


def deploy(c, token, source):
    preflight(c)
    if BASE.exists():
        state = load_state()
        require(state["config"]["sing_box_version"] == c["sing_box_version"], "请使用 upgrade 修改已部署版本")
        if state["phase"] == "ready":
            return health()
    else:
        BASE.mkdir(mode=0o700)
        state = {"manager": MANAGED, "phase": "preparing", "config": c}
        write_json(BASE / "state.json", state)
    for folder in ["config", "certs", "backups", "reports"]:
        (BASE / folder).mkdir(mode=0o700, exist_ok=True)
    install_docker()
    image = state.get("image") or resolve_image(c["sing_box_version"])
    state["image"] = image
    write_json(BASE / "state.json", state)
    if not (BASE / "keys.json").exists():
        write_json(BASE / "keys.json", generate_keys(image))
    keys = json.loads((BASE / "keys.json").read_text())
    install_certificate(c, token)
    write_json(BASE / "config/config.json", server_config(c, keys))
    write_json(BASE / "compose.json", compose_config(image))
    check_config(image)
    # Add only our rules. Never reset UFW, change SSH, or enable an inactive firewall.
    for rule in [f"{c['ssh_port']}/tcp", "443/tcp", "443/udp", "8443/tcp"]:
        run(["ufw", "allow", rule], "补充 UFW 规则")
    compose("up", "-d")
    wait_running()
    report = health()
    require(report["ok"], "服务端健康检查失败；请运行 status 查看脱敏结果")
    install_timers(source)
    state["phase"] = "ready"
    write_json(BASE / "state.json", state)
    backup()
    return dict(health(), acceptance="SERVER_READY_CLIENT_TEST_REQUIRED")


def health():
    state = load_state()
    failures, warnings = [], []
    disk = shutil.disk_usage(BASE)
    disk_used = round((disk.total - disk.free) / disk.total * 100, 1)
    if disk_used >= 85:
        warnings.append("磁盘使用率达到 85%")
    if Path("/var/run/reboot-required").exists():
        warnings.append("系统更新等待重启；需要维护窗口")
    memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    available_mb = int(memory["MemAvailable"].split()[0]) // 1024
    if available_mb < 100:
        warnings.append("可用内存不足 100 MiB")
    container = {}
    try:
        d = json.loads(run(["docker", "inspect", CONTAINER], "检查容器"))[0]
        container = {"running": d["State"]["Running"], "restarts": d["RestartCount"], "oom": d["State"]["OOMKilled"]}
        if not container["running"] or container["oom"] or d["State"].get("Restarting"):
            failures.append("容器未健康运行")
        if container["restarts"]:
            warnings.append("容器存在重启记录")
        if d["Config"]["Image"] != state["image"]:
            failures.append("运行镜像与记录 digest 不一致")
        check_config()
    except OpsError:
        failures.append("容器或配置检查失败")
    expires = None
    try:
        with socket.create_connection(("127.0.0.1", 8443), timeout=10) as sock:
            with ssl.create_default_context().wrap_socket(sock, server_hostname=state["config"]["ws_domain"]) as tls:
                cert = tls.getpeercert()
                expires = cert["notAfter"]
                if ssl.cert_time_to_seconds(expires) - time.time() < 21 * 86400:
                    warnings.append("TLS 证书不足 21 天")
    except (OSError, ValueError, KeyError):
        failures.append("源站 TLS 验证失败")
    for rel in ["keys.json", "config/config.json", "certs/key.pem", "acme/account.conf"]:
        p = BASE / rel
        if not p.is_file() or p.stat().st_mode & 0o077:
            failures.append(f"秘密文件权限异常：{rel}")
    ufw = run(["ufw", "status"], "读取 UFW")
    if "Status: inactive" in ufw:
        warnings.append("UFW 未启用；须确认云安全组，启用前验证第二个 SSH 会话")
    for job in ["health", "backup"]:
        r = subprocess.run(["systemctl", "is-active", f"vpn-ai-ops-{job}.timer"], capture_output=True)
        if r.returncode:
            warnings.append(f"{job} 定时器未激活")
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if not any(str(BASE / "acme") in x and "--cron" in x and not x.lstrip().startswith("#") for x in cron.stdout.splitlines()):
        failures.append("未找到受管 acme.sh 续期任务")
    if subprocess.run(["systemctl", "is-active", "cron"], capture_output=True).returncode:
        failures.append("cron 服务未运行")
    snapshots = list((BASE / "backups").glob("*.tar.gz"))
    latest_backup = max((x.stat().st_mtime for x in snapshots), default=0)
    if not latest_backup or time.time() - latest_backup > 8 * 86400:
        warnings.append("没有最近 8 天内的备份")
    report = {"ok": not failures, "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "version": state["config"]["sing_box_version"], "image": state["image"],
              "container": container, "disk_used_percent": disk_used, "memory_available_mib": available_mb,
              "load_average": list(os.getloadavg()), "certificate_expires": expires,
              "failures": failures, "warnings": warnings,
              "client_protocols": "NOT_TESTED", "client_dns": "NOT_TESTED"}
    return report


def backup():
    load_state()
    directory = BASE / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    name = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4) + ".tar.gz"
    path = directory / name
    tmp = path.with_suffix(".partial")
    try:
        with tarfile.open(tmp, "w:gz") as tar:
            for rel in ["state.json", "keys.json", "compose.json", "config", "certs", "acme"]:
                tar.add(BASE / rel, arcname=rel)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    for old in sorted(directory.glob("*.tar.gz"), key=lambda p: (p.stat().st_mtime_ns, p.name))[:-8]:
        old.unlink()
    return {"ok": True, "backup": name, "location": str(path), "contains_secrets": True,
            "offsite_backup": "NOT_CONFIGURED"}


def rollback_files(path):
    # Read exact regular-file members; never extract archive paths or overwrite renewed certs.
    current = load_state()
    files = {}
    with tarfile.open(path, "r:gz") as tar:
        for rel in ["state.json", "keys.json", "compose.json", "config/config.json"]:
            m = tar.getmember(rel)
            require(m.isfile() and m.size < 1024 * 1024, "备份成员不合法")
            files[rel] = tar.extractfile(m).read().decode()
    old = json.loads(files["state.json"])
    require(old.get("manager") == MANAGED, "备份不是本项目生成")
    require_identity(current["config"], old)
    require(json.loads(files["compose.json"]) == compose_config(old["image"]), "备份 Compose 内容不符合受管模板")
    validate_config(old["config"])
    # Refuse restoring arbitrary client secrets/config edits disguised as an upgrade snapshot.
    require(json.loads(files["keys.json"]) == json.loads((BASE / "keys.json").read_text()), "快照密钥不同，需专门迁移流程")
    require(json.loads(files["config/config.json"]) == server_config(old["config"], json.loads(files["keys.json"])),
            "备份服务端配置不符合受管模板；手工改动需要单独恢复方案")
    for rel, content in files.items():
        write_private(BASE / rel, content)
    check_config(old["image"])
    compose("up", "-d", "--force-recreate")
    wait_running()
    require(health()["ok"], "回滚后的健康检查失败")


def upgrade(version):
    validate_version(version)
    state = load_state()
    require(state["phase"] == "ready", "首次部署未完成，不能升级")
    if version == state["config"]["sing_box_version"]:
        return dict(health(), changed=False)
    new_image = resolve_image(version)
    # Validate before touching the active Compose or restarting the service.
    check_config(new_image)
    snapshot = backup()["backup"]
    try:
        state["config"]["sing_box_version"] = version
        state["image"] = new_image
        write_json(BASE / "compose.json", compose_config(new_image))
        write_json(BASE / "state.json", state)
        compose("up", "-d", "--force-recreate")
        wait_running()
        require(health()["ok"], "新版本健康检查失败")
    except Exception:
        try:
            rollback_files(BASE / "backups" / snapshot)
        except Exception:
            raise OpsError(f"升级失败且回滚未通过；停止继续修改，恢复快照 {snapshot}") from None
        raise OpsError(f"升级失败，已回滚到快照 {snapshot}；仍需客户端复验") from None
    return dict(health(), rollback_backup=snapshot, client_protocols="RETEST_REQUIRED")


def remote_main():
    os.umask(0o077)
    require(os.geteuid() == 0, "远程执行器需要 root")
    # Lock in /run, not the deployment directory, so preflight never claims ownership.
    with open("/run/vpn-ai-ops.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OpsError("另一个部署/维护任务正在运行") from None
        if len(sys.argv) > 1 and sys.argv[1].startswith("scheduled-"):
            job = sys.argv[1].removeprefix("scheduled-")
            require(job in ["health", "backup"], "未知定时任务")
            report = health() if job == "health" else backup()
            write_json(BASE / "reports" / f"latest-{job}.json", report)
        else:
            request = json.load(sys.stdin)
            command = request["command"]
            c = validate_config(request["config"])
            if command == "preflight":
                report = preflight(c)
            elif command == "deploy":
                report = deploy(c, request["token"], request["source"])
            else:
                require_identity(c, load_state())
                if command == "status":
                    report = health()
                elif command == "backup":
                    report = backup()
                elif command == "upgrade":
                    report = upgrade(request["version"])
                elif command == "rollback":
                    name = request["backup"]
                    require(re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}\.tar\.gz", name), "非法备份文件名")
                    target = BASE / "backups" / name
                    require(target.is_file(), "备份不存在")
                    # Pin bytes before rotation can prune the requested snapshot.
                    with tempfile.TemporaryDirectory(dir=BASE) as tmp:
                        copy = Path(tmp) / "restore.tar.gz"
                        shutil.copyfile(target, copy)
                        rescue = backup()["backup"]
                        try:
                            rollback_files(copy)
                        except Exception:
                            try:
                                rollback_files(BASE / "backups" / rescue)
                            except Exception:
                                raise OpsError(f"回滚和恢复均失败，需人工处理快照 {rescue}") from None
                            raise OpsError(f"回滚失败，已恢复操作前快照 {rescue}") from None
                    report = dict(health(), rescue_backup=rescue, client_protocols="RETEST_REQUIRED")
                elif command == "export":
                    state = load_state()
                    keys = json.loads((BASE / "keys.json").read_text())
                    report = {"ok": True, "mihomo": client_config(state["config"], keys), "links": client_links(state["config"], keys)}
                else:
                    raise OpsError("未知远程命令")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["ok"] else 2


if __name__ == "__main__":
    try:
        sys.exit(remote_main())
    except OpsError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    except Exception:
        print(json.dumps({"ok": False, "error": "执行器异常；检查配置、权限和网络，禁止输出秘密调试"}, ensure_ascii=False))
        sys.exit(1)
