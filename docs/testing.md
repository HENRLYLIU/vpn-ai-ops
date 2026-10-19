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

## 正式使用前的云端验收

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

模板检查与单元测试不覆盖 apt 包安装、systemd、Cloudflare API 实际权限、CA 限流、网络封锁或客户端 GUI 行为。这些限制应在交付报告中明确说明。

## AI 主导的首次使用流程验收（待实测）

文档已按“用户准备资源与授权，AI 执行实施”组织。以下项目仍待实际 AI 环境和全新 VPS 验证，不能用文档检查或既有单元测试替代。

- [ ] 用户只提供 README 中的资源信息；AI 自行查询 Zone ID、填写配置并执行命令，没有把技术参数表交给用户填写。
- [ ] 已有 SSH Agent / 公钥与安全保存 Token 的路径，AI 可连续完成预检、部署与验证。
- [ ] 只有密码时，核验可信指纹，通过安全工具输入并追加专用公钥；验证第二连接且原登录方式仍可用，工具记录中无秘密。
- [ ] 没有安全密码通道时，AI 明确指出能力缺口，不将密码写进命令、脚本或聊天。
- [ ] Cloudflare API MCP 实际查询账号、Zone、DNS 和 SSL 设置；缺权限时提出具体授权动作，不把“已连接”视为权限已具备。
- [ ] MCP 已授权但 CLI Token 缺失时，AI 准备或指导一次安全交付；不复制 OAuth 会话，不绕过 preflight，不把生成的秘密返回工具记录。
- [ ] 没有 MCP、但具有有效 Token 和必要资源权限时，仍可走现有 CLI 部署路径。
- [ ] 共享 Zone、DNS 冲突和云安全组未放行时，AI 保留进度并请求最小必要动作；不覆盖旧业务。
- [ ] 设备有/无控制工具两种路径分别验收，系统授权由用户完成；报告清楚区分服务端、三线路及 TUN/DNS。
- [ ] 本地 AI 退出后，VPS 的巡检、备份和续期调度仍正常；记录实际测试与未测试范围，避免为验证流程强制生产签发。
