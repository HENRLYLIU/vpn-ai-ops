# 资源与参数

第一次配置 Cloudflare？先看 [Cloudflare API Token 新手教程](cloudflare-token.md)。它会解释 Token 和 Zone 是什么、三个权限分别做什么，以及页面上每一步怎么选。

AI 一次收集以下非敏感信息即可，不要索取私钥全文或要求用户把 Token 粘贴到聊天。

| 字段 | 示例 | 说明 |
| --- | --- | --- |
| server_ip | `203.0.113.10` | 示例地址不可部署，替换为 VPS 公网 IPv4 |
| ssh_user | `root` | 也可使用免密 sudo 用户 |
| ssh_port | `22` | 不能与 443/8443 冲突 |
| ssh_identity_file | `""` | 留空用 SSH 默认密钥/Agent；否则填本机路径 |
| zone_id | 32 位十六进制 | 域名区域的编号，不是 Token 或 Account ID；[查看获取步骤](cloudflare-token.md#find-zone-id) |
| base_domain | `example.com` | 必须与 Zone 名称完全一致 |
| vpn_domain | `vpn.example.com` | 项目创建 DNS Only A 记录 |
| ws_domain | `ws.example.com` | 项目创建 Proxied A 记录 |
| acme_email | `you@example.com` | 证书账户邮箱 |
| sing_box_version | `1.13.14` | 基线稳定版本；升级前读迁移说明 |
| reality_server | `gateway.icloud.com` | VPS 预检必须通过该目标的 TLS 1.3 握手 |

步骤：

1. 在 Cloudflare 激活 Zone，并手动确认 Full (strict)。本项目只读检查此全站设置。
2. 按 [Token 新手教程](cloudflare-token.md) 为这个域名创建专用钥匙，添加 DNS Edit、Zone Read、Zone Settings Read 三条权限。教程也说明了可选的 IP 白名单和有效期设置。
3. 在云安全组开放实际 SSH 端口、443 TCP/UDP、8443 TCP。Docker 发布端口不能仅依赖 UFW 做访问控制。
4. 从云控制台取得 SSH 主机公钥指纹，在首次登录时比对。不要用 `StrictHostKeyChecking=no` 绕过验证。
5. 手动验证公钥登录、`python3 --version`，非 root 用户还要验证 `sudo -n true`。脚本没有自动装公钥、改 sshd 或关密码登录。
6. 运行 `init`，填写 `config.local.json`；从终端隐藏输入 `CF_API_TOKEN`。
7. 运行 `plan` 和 `preflight`。示例配置只能用于离线计划，不能部署。

客户端侧：

- Clash Verge Rev 导入 `artifacts/mihomo.yaml`。文件使用合法的 JSON/YAML 兼容语法，避免依赖额外 YAML 库。
- 默认只提供最小分流：私网、`.lan`、`.local`、`.cn` 直连，其余走代理。这不是完整国内域名规则库；用户可在理解规则后扩展。
- 配置的 TUN 默认关闭，交由 GUI 获取系统权限并开启。`verify` 不自动提升本机权限。
- 规则组 `PROXY` 可手动切换线路或选择 `AUTO`。自动回退组自身会检查可用性。
- Shadowrocket 导入 `artifacts/shadowrocket.txt` 中三条链接，逐条验收。不同客户端版本的链接兼容性应实机确认。
- 这些文件含可用凭据，只在自己的设备上传输，不上传订阅转换网站或公开分享图。
