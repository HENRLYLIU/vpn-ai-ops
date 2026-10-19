# VPN AI Ops

**准备好 VPS 和 Cloudflare 域名，把这个仓库交给 AI，完成个人代理网关的搭建和维护。**

AI 负责理解资源、执行命令、诊断问题；脚本负责可重复的部署、证书续期、巡检、备份、升级和回滚。日常定时任务在 VPS 上运行，不需要 AI 会话一直在线。

> 状态：首版。自动化测试和本地真实协议验证见 [测试记录](docs/testing.md)。首次公开教学前，仍需在一台全新测试 VPS 和独立测试域名完成云端验收；不把本地测试等同于生产部署验证。

## 搭建结果

| 线路 | 入口 | 用途 |
| --- | --- | --- |
| VLESS + Reality | `vpn.<域名>:443/tcp`，DNS Only | 默认主线路 |
| Hysteria2 | `vpn.<域名>:443/udp`，DNS Only | UDP 备用线路 |
| VLESS + WebSocket + TLS | `ws.<域名>:8443/tcp`，Cloudflare Proxied | CDN 备用入口 |

服务器使用 Docker Compose 管理 sing-box。签发 Let's Encrypt 证书，输出 Clash Verge Rev / mihomo 配置及 Shadowrocket 导入链接。

这里的“VPN”是个人代理网关：电脑通过客户端的 TUN 模式接管流量，并非企业站点互联 VPN。首版不安装 Sub2API、面板或公开订阅服务。

## 你需要准备

1. 一台**全新的 Ubuntu 24.04 VPS**，公网 IPv4，amd64 或 arm64；建议至少 1 GiB 内存、2 GiB 空闲磁盘。
2. 一个已在 Cloudflare 激活的域名。SSL/TLS 模式设为 **Full (strict)**。已有网站使用其他模式时先评估，不要为演示直接改生产域名全站设置。
3. 在 Cloudflare 创建一个 **API Token（给脚本使用的专用钥匙）**，并且只授权给你用来搭建 VPN 的域名。它用于自动设置域名解析和续期证书。**不懂 Token、Zone 或权限怎么选？直接照着 [Cloudflare Token 新手教程](docs/cloudflare-token.md) 操作**，里面有逐项填写说明；来源 IP 限制是可选项。
4. 可用的 SSH 公钥登录：root，或带免密 sudo 的账户。VPS 有 Python 3.10+（Ubuntu 24.04 通常自带）。
5. 本地/AI 执行环境：macOS、Linux 或 Windows WSL，Python 3.10+、OpenSSH、Git；无需 pip 安装。AI 必须具有终端、SSH 和联网能力。
6. 云安全组允许实际 SSH 端口、`443/tcp`、`443/udp`、`8443/tcp`。无需开放 `80`。项目不会操作云厂商安全组。

## 把这段话交给 AI

先克隆本项目，或在 AI 工具中打开仓库目录，然后发送：

```text
请阅读本仓库 AGENTS.md、README.md 和 prompts/deploy.md，使用现有脚本帮我搭建个人 VPN。
我已准备一台全新 Ubuntu 24.04 VPS 和 Cloudflare 托管域名。
先收集缺失的非敏感参数，指导我在本机安全设置 Token 和 SSH 登录，运行 plan 与 preflight。
预检通过后执行部署、导出客户端配置、逐条验证三条线路，并安装项目已有的自动维护任务。
发现已有业务或 DNS 冲突时先停下说明。不要把秘密写入聊天或 Git。
交付时区分已验证项与需要我在手机/电脑上完成的 TUN、DNS 验收。
```

第一次使用 Cloudflare，请先看 [Token 创建教程](docs/cloudflare-token.md)，再按 [资源填写清单](docs/setup.md) 准备信息。完整部署提示词在 [prompts/deploy.md](prompts/deploy.md)。

## 实际执行的命令

在仓库根目录执行。AI 会帮你填写配置和解释结果。

```bash
python3 vpnctl.py init
# 编辑 config.local.json，只填非敏感资源信息
python3 vpnctl.py plan
```

首次 SSH 连接前，通过云控制台核对主机指纹，再手动连接一次，将已核对的主机加入 `known_hosts`。脚本始终使用严格主机校验，不会关闭检查，也不会自动信任未经核实的指纹。

在将要运行部署命令的 Bash / Zsh 终端中，先单独执行下面这一行：

```bash
read -rs CF_API_TOKEN
```

粘贴 Token 后按回车。输入过程中看不到字符是正常的。然后在**同一个终端**继续执行：

```bash
export CF_API_TOKEN
python3 vpnctl.py preflight
python3 vpnctl.py deploy
unset CF_API_TOKEN
```

若 AI 使用另一个终端或云端环境，它不会自动获得这里设置的 Token；请按 [教程中的使用说明](docs/cloudflare-token.md#use-token) 让 AI 指导你安全传入，不要发到聊天里。

`deploy` 会创建缺失 DNS、安装依赖、签发证书、生成密钥、启动容器，安装每日巡检与每周备份，最后将客户端文件保存到 `artifacts/`。重新执行不会轮换已生成密钥；完整部署已有标记时只进行健康检查和重新导出。

证书续期所需 Token 会由 acme.sh 保存在服务器受限目录内，这是无人值守续期的必要条件。不会复制到本地输出或 Git。

部署后由 AI 安装/找到官方 mihomo 核心，再验证真实连接：

```bash
python3 vpnctl.py verify --mihomo /absolute/path/to/mihomo
```

该命令启动临时本地核心，依次测试 Reality、Hysteria2、WebSocket 的出口 IP，结束后关闭进程。它不接管系统流量，也不代替用户设备上的 DNS 验收。

## 后续维护

| 动作 | 命令或调度 | 行为 |
| --- | --- | --- |
| 巡检 | `python3 vpnctl.py status` | 返回脱敏 JSON；服务端每日自动检查 |
| 备份 | `python3 vpnctl.py backup` | 每周自动备份，服务器保留最近 8 份 |
| 重新导出 | `python3 vpnctl.py export` | 私有文件写到 `artifacts/` |
| 升级 | `python3 vpnctl.py upgrade --version X.Y.Z` | 指定稳定版本，校验、备份、重建；服务端失败自动回滚 |
| 回滚 | `python3 vpnctl.py rollback --backup <返回的文件名>` | 先备份当前状态，恢复旧配置和镜像，保留已续期证书 |
| 证书续期 | acme.sh cron | 续期后重启本项目的 sing-box 容器加载证书 |

`X.Y.Z` 是待选择的真实版本，不是可直接复制的值。当前模板基线为 sing-box **1.13.14**，部署时固定镜像 digest；不追踪 `latest`。升级成功会同步本地配置中的版本号，并要求重新测试客户端。

自动维护**不包含**自动升大版本、重启操作系统、异地备份或默认外部告警。巡检结果写到 `/opt/vpn-ai-ops/reports/`；失败可由 systemd 状态或日志监控采集。操作详见 [维护手册](docs/operations.md)，可复制 [维护提示词](prompts/maintain.md)。

## 分享前看这里

- [分享讲稿与演示顺序](docs/sharing.md)
- [故障排查](docs/troubleshooting.md)
- [架构、数据边界与回滚范围](docs/architecture.md)
- [测试与云端验收清单](docs/testing.md)
- [上游官方文档与版本依据](docs/sources.md)

`config.local.json`、`artifacts/`、Token、密钥、备份均不应提交。`.gitignore` 只是防误操作，公开前还应运行 `python3 scripts/check_public_files.py` 并人工检查暂存区。许可证：[MIT](LICENSE)。
