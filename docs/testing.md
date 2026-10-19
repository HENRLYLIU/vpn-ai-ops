# 验证与发布门槛

## 本地验证（2026-10-19）

- Python 3.14.5（本机）及 Python 3.10（隔离容器）单元测试：各 22 项通过。覆盖参数防注入、DNS 冲突先检查后写入、重复部署保留密钥、私有文件权限、备份保留、升级失败回滚、回滚保留已续期证书等。
- Python 语法编译、CLI 离线 plan、公开文件检查通过。
- 真实配置校验：sing-box **1.13.14** 官方容器、mihomo **1.19.32** 官方 macOS arm64 二进制通过。mihomo 下载摘要与 GitHub Release asset digest 一致。
- 本地协议冒烟：Reality、Hysteria2、WebSocket 均经过真实 sing-box → mihomo 代理访问 `https://example.com`，返回 HTTP 200。
- 测试中发现并修正了两个核心对日志级别名称的差异：sing-box `warn`，mihomo `warning`。

本地冒烟中的 HY2/WS 使用临时自签名证书，并**仅在测试客户端**关闭证书校验。正式生成模板没有关闭校验；生产证书校验由部署后的 `status` 与 `verify` 验收。

## 复现命令

无需 VPS 或 Token 的检查：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q vpnctl.py vpnops scripts tests
python3 vpnctl.py --config config.example.json plan
python3 scripts/check_public_files.py
```

协议冒烟需要本地 Docker、OpenSSL、curl 和从官方 Release 下载并核对摘要的 mihomo：

```bash
python3 scripts/smoke_local.py --mihomo /absolute/path/to/mihomo
```

该脚本只创建临时 Docker 容器、本地高位端口和临时证书，结束后清理容器、进程与临时目录。会下载官方 sing-box 镜像并访问外部测试站点。不会读取 `config.local.json` 或连接用户 VPS。

GitHub Actions 配置包含 Python 3.10/3.12/3.14 离线检查；未推送前不能声称远程 CI 已运行。

## 首次公开教学前的云端验收

以下尚未在本项目的新部署流程中实测，须用**全新测试 VPS + 独立测试域名**完成，不能用已有生产服务器充当首次部署测试对象。

- [ ] 全新 Ubuntu 24.04 amd64 部署；若声称 arm64 云端支持，也完成相应实例部署。
- [ ] 非 root 免密 sudo 路径实测。
- [ ] Cloudflare 两条记录、Full (strict) 检查和 DNS-01 正式证书签发。
- [ ] 服务器三端口、sing-box 配置和日志、源站证书校验。
- [ ] `verify` 三条线路均返回预期 VPS 出口 IP，WebSocket 确实经过 Cloudflare。
- [ ] Clash Verge Rev 开启 TUN，分别验证国内直连、代理流量和 DNS 接管。
- [ ] Shadowrocket 三条导入链接实机验证。
- [ ] acme.sh 续期调度和成功后重载路径；避免强制生产签发触发限流。
- [ ] 手动触发 health / backup service，检查 JSON 报告、权限和备份内容。
- [ ] 在测试实例演练重复部署、失败后续跑、一次兼容升级与回滚。
- [ ] 在云控制台验证安全组；在保持第二个 SSH 会话的条件下启用 UFW。
- [ ] 导出后重新克隆公开仓库，确认没有泄露资源、Token 或节点凭据。

模板检查与单元测试不覆盖 apt 包安装、systemd、Cloudflare API 实际权限、CA 限流、网络封锁或客户端 GUI 行为。这些限制应在分享时明确说明。
