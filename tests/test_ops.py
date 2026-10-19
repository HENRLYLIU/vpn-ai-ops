import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from vpnops import cli, remote
from vpnops.cloudflare import Cloudflare
from vpnops.model import (OpsError, IMAGE, validate_config, validate_version,
                          server_config, compose_config, client_config, client_links)

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "config.example.json").read_text())
DIGEST = IMAGE + "@sha256:" + "a" * 64
KEYS = {"uuid": "00000000-0000-4000-8000-000000000001", "private_key": "TEST_PRIVATE_ONLY",
        "public_key": "TEST_PUBLIC_ONLY", "short_id": "aabbccddeeff0011", "hy2_password": "test+/@:?",
        "ws_path": "/test+path/"}


class ModelTests(unittest.TestCase):
    def test_rejects_shell_and_domain_injection(self):
        for key, value in [("ssh_user", "root;id"), ("server_ip", "--help"),
                           ("vpn_domain", "vpn.example.com.evil.test"), ("reality_server", "$(id)"),
                           ("server_ip", True), ("ssh_port", True), ("ssh_port", 443), ("acme_email", "a@b.com\ncommand")]:
            with self.subTest(key=key), self.assertRaises(OpsError):
                validate_config(dict(CONFIG, **{key: value}))

    def test_rejects_secrets_in_config(self):
        with self.assertRaises(OpsError):
            validate_config(dict(CONFIG, token="should-be-env"))

    def test_requires_exact_stable_version(self):
        for v in ["latest", "1.2", "v1.13.14", "1.14.0-alpha.1", "1.2.3;id"]:
            with self.subTest(version=v), self.assertRaises(OpsError):
                validate_version(v)

    def test_compose_rejects_nonofficial_digest(self):
        with self.assertRaises(OpsError):
            compose_config("other/image@sha256:" + "a" * 64)

    def test_client_and_server_agree_without_exporting_private_key(self):
        server, client = server_config(CONFIG, KEYS), client_config(CONFIG, KEYS)
        reality, hy2, ws = server["inbounds"]
        self.assertEqual(reality["tls"]["reality"]["short_id"][0], client["proxies"][0]["reality-opts"]["short-id"])
        self.assertEqual(hy2["users"][0]["password"], client["proxies"][1]["password"])
        self.assertEqual(ws["transport"]["path"], client["proxies"][2]["ws-opts"]["path"])
        self.assertNotIn(KEYS["private_key"], json.dumps(client))
        self.assertFalse(client["proxies"][1]["skip-cert-verify"])

    def test_links_escape_reserved_characters(self):
        from urllib.parse import urlsplit, unquote, parse_qs
        links = client_links(CONFIG, KEYS).splitlines()
        self.assertEqual(len(links), 3)
        self.assertEqual(unquote(urlsplit(links[1]).username), KEYS["hy2_password"])
        self.assertEqual(parse_qs(urlsplit(links[2]).query)["path"][0], KEYS["ws_path"])


class CloudflareTests(unittest.TestCase):
    def setUp(self):
        self.cf = Cloudflare("unit-test-placeholder", CONFIG["zone_id"])

    def fake(self, conflict=False):
        def request(method, suffix, body=None):
            if suffix == "":
                return {"name": "example.com", "status": "active"}
            if suffix == "/settings/ssl":
                return {"value": "strict"}
            if "dns_records?" in suffix:
                if conflict and "ws.example.com" in suffix:
                    return [{"type": "AAAA", "name": "ws.example.com", "content": "::1", "proxied": True}]
                return []
            return body
        return request

    def test_preflight_both_names_before_any_write(self):
        with patch.object(self.cf, "request", side_effect=self.fake(conflict=True)) as calls:
            with self.assertRaises(OpsError):
                self.cf.ensure(CONFIG)
            self.assertTrue(all(x.args[0] == "GET" for x in calls.call_args_list))

    def test_creates_correct_proxy_states(self):
        with patch.object(self.cf, "request", side_effect=self.fake()) as calls:
            self.cf.ensure(CONFIG)
            writes = [x.args[2] for x in calls.call_args_list if x.args[0] == "POST"]
            self.assertEqual([x["proxied"] for x in writes], [False, True])

    def test_existing_matching_records_are_idempotent(self):
        def fake(method, suffix, body=None):
            if "dns_records?" in suffix:
                ws = "ws.example.com" in suffix
                return [{"type": "A", "name": CONFIG["ws_domain" if ws else "vpn_domain"],
                         "content": CONFIG["server_ip"], "proxied": ws}]
            return self.fake()(method, suffix, body)
        with patch.object(self.cf, "request", side_effect=fake) as calls:
            self.cf.ensure(CONFIG)
            self.assertTrue(all(x.args[0] == "GET" for x in calls.call_args_list))

    def test_strict_tls_required_without_changing_zone(self):
        with patch.object(self.cf, "request", side_effect=[{"name": "example.com", "status": "active"}, {"value": "flexible"}]) as calls:
            with self.assertRaises(OpsError):
                self.cf.ensure(CONFIG)
            self.assertEqual(calls.call_count, 2)


class LocalTests(unittest.TestCase):
    def test_compiled_bundle_is_standalone(self):
        compile(cli.bundle_source(), "remote-bundle", "exec")

    def test_token_never_in_ssh_command(self):
        with patch("vpnops.cli.shutil.which", return_value="/usr/bin/ssh"), patch("vpnops.cli.subprocess.run", return_value=subprocess.CompletedProcess([], 0, '{"ok":true}', "")) as run:
            cli.remote(CONFIG, "deploy", token="UNIT_TEST_SECRET")
        args, kwargs = run.call_args
        self.assertNotIn("UNIT_TEST_SECRET", " ".join(args[0]))
        self.assertIn("UNIT_TEST_SECRET", kwargs["input"])
        self.assertIn("StrictHostKeyChecking=yes", args[0])

    def test_init_and_export_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.local.json"
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["--config", str(path), "init"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(OpsError):
                cli.main(["--config", str(path), "init"])
            with patch("vpnops.cli.remote", return_value={"mihomo": client_config(CONFIG, KEYS), "links": client_links(CONFIG, KEYS)}):
                report = cli.export_clients(CONFIG, tmp)
            self.assertNotIn(KEYS["hy2_password"], json.dumps(report))
            self.assertEqual((Path(tmp) / "mihomo.yaml").stat().st_mode & 0o777, 0o600)

    def test_plan_never_connects(self):
        with patch("vpnops.cli.remote") as call, contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--config", str(cli.REPO / "config.example.json"), "plan"])
        self.assertEqual(result, 0)
        call.assert_not_called()


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.base_patch = patch.object(remote, "BASE", self.base)
        self.base_patch.start()
        self.state = {"manager": remote.MANAGED, "phase": "ready", "config": copy.deepcopy(CONFIG), "image": DIGEST}
        remote.write_json(self.base / "state.json", self.state)
        remote.write_json(self.base / "keys.json", KEYS)
        remote.write_json(self.base / "compose.json", compose_config(DIGEST))
        remote.write_json(self.base / "config/config.json", server_config(CONFIG, KEYS))
        remote.write_private(self.base / "certs/key.pem", "test certificate key")
        remote.write_private(self.base / "acme/account.conf", "test account secret")

    def tearDown(self):
        self.base_patch.stop()
        self.tmp.cleanup()

    def test_errors_never_echo_command_output(self):
        r = subprocess.CompletedProcess([], 1, "UNIT_SECRET", "failed")
        with patch("vpnops.remote.subprocess.run", return_value=r), self.assertRaises(OpsError) as ctx:
            remote.run(["example"], "测试")
        self.assertNotIn("UNIT_SECRET", str(ctx.exception))
        self.assertEqual((self.base / "last-error.log").stat().st_mode & 0o777, 0o600)

    def test_backup_contains_restore_data_and_rotates(self):
        for _ in range(10):
            result = remote.backup()
        archives = list((self.base / "backups").glob("*.tar.gz"))
        self.assertEqual(len(archives), 8)
        self.assertEqual(Path(result["location"]).stat().st_mode & 0o777, 0o600)
        with tarfile.open(result["location"]) as tar:
            self.assertIn("config/config.json", tar.getnames())
            self.assertIn("acme/account.conf", tar.getnames())

    def test_rollback_preserves_renewed_certificate(self):
        result = remote.backup()
        remote.write_private(self.base / "certs/key.pem", "newly renewed key")
        with patch.object(remote, "check_config"), patch.object(remote, "compose"), patch.object(remote, "wait_running"), patch.object(remote, "health", return_value={"ok": True}):
            remote.rollback_files(Path(result["location"]))
        self.assertEqual((self.base / "certs/key.pem").read_text(), "newly renewed key")

    def test_upgrade_checks_new_image_before_backup_or_changes(self):
        with patch.object(remote, "resolve_image", return_value=IMAGE + "@sha256:" + "b" * 64), patch.object(remote, "check_config", side_effect=OpsError("bad config")), patch.object(remote, "backup") as backup:
            with self.assertRaises(OpsError):
                remote.upgrade("1.13.15")
        backup.assert_not_called()
        self.assertEqual(remote.load_state()["image"], DIGEST)

    def test_failed_upgrade_restores_old_version(self):
        with patch.object(remote, "resolve_image", return_value=IMAGE + "@sha256:" + "b" * 64), patch.object(remote, "check_config"), patch.object(remote, "compose"), patch.object(remote, "wait_running", side_effect=[OpsError("new failed"), None]), patch.object(remote, "health", return_value={"ok": True}):
            with self.assertRaisesRegex(OpsError, "已回滚"):
                remote.upgrade("1.13.15")
        self.assertEqual(remote.load_state()["config"]["sing_box_version"], "1.13.14")
        self.assertEqual(json.loads((self.base / "compose.json").read_text()), compose_config(DIGEST))

    def test_deploy_ready_does_not_rotate_keys_or_install(self):
        with patch.object(remote, "preflight"), patch.object(remote, "health", return_value={"ok": True}), patch.object(remote, "install_docker") as install:
            remote.deploy(CONFIG, "unused", "unused")
        install.assert_not_called()
        self.assertEqual(json.loads((self.base / "keys.json").read_text()), KEYS)

    def test_different_deployment_identity_is_rejected(self):
        with self.assertRaises(OpsError):
            remote.require_identity(dict(CONFIG, ws_domain="other.example.com"), self.state)

    def test_unmanaged_directory_rejected(self):
        (self.base / "state.json").unlink()
        with self.assertRaises(OpsError):
            remote.load_state()


if __name__ == "__main__":
    unittest.main()
