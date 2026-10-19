# 参数准备：由 AI 查询与填写

本页给执行 AI 阅读。用户只提供 VPS 地址、登录身份、域名、设备类型和必要授权；不要把本表当成需要用户逐格填写的问卷。先按 [环境与授权准备](ai-environment.md) 检查工具和凭据。

## 参数来源

| 字段 | AI 如何获取 |
| --- | --- |
| server_ip | 用户指定的目标 VPS 公网 IPv4；不从其他私人运维资料猜测 |
| ssh_user / ssh_port | 使用用户提供值；未提供时说明先尝试 root / 22，失败后只询问缺失信息 |
| ssh_identity_file | 已验证的专用密钥路径；使用默认密钥或 SSH Agent 时留空。不读取私钥正文 |
| zone_id | 通过获授权的 Cloudflare API MCP 或 API，按 base_domain 精确查询 |
| base_domain | 用户提供并已在其 Cloudflare 账号激活的域名 |
| vpn_domain / ws_domain | 默认 vpn.<域名>、ws.<域名>，先检查冲突；有冲突先解释，不覆盖 |
| acme_email | 用户指定的证书联系邮箱，缺少时与其他无法查询的信息一次询问 |
| sing_box_version | 使用当前仓库基线 1.13.14；部署固定 digest，不擅自切换 latest |
| reality_server | 默认使用模板中的 gateway.icloud.com，由 VPS 预检验证 TLS 1.3 可达性 |

运行 `init`，由 AI 填写被 Git 忽略的 `config.local.json`。Token 仅通过 `CF_API_TOKEN` 注入，密码不写 JSON。不要输出完整配置。

## 部署前由 AI 完成

1. 核实新 Ubuntu 24.04 VPS、Python 3.10+、可信 SSH 公钥登录、root 或已具备免密 sudo 的账户。
2. 查询 Zone 的激活状态、DNS 和 Full (strict)；共享 Zone 设置或已有业务冲突按 AGENTS.md 处理。
3. 验证实际执行进程可用的受限 Token。MCP OAuth 不能代替当前 CLI 的 Token 输入；路径见环境清单。
4. 检查云安全组的实际 SSH 端口、443 TCP/UDP、8443 TCP；不需要开放 80。没有云厂商控制权限时只请求必要的放行操作。Docker 发布端口不能仅依赖 UFW 做访问控制。
5. 由 AI 执行 `plan`、`preflight`，按 [部署流程](../prompts/deploy.md) 持续实施。

## 客户端由 AI 尽可能配置

- 为目标设备选择官方客户端；安装第三方软件需要的系统授权由用户完成，已有授权范围内不反复询问。
- Clash Verge Rev 导入 `artifacts/mihomo.yaml`，其内容采用 JSON/YAML 兼容语法。具备桌面工具时由 AI 导入，否则只给用户最短导入步骤。
- TUN 默认关闭，由 GUI 获取系统权限后开启；`verify` 不接管系统流量。切换本机路由前保留原配置和恢复步骤。
- Shadowrocket 导入 `artifacts/shadowrocket.txt` 的三条链接；无手机控制能力时请用户导入并逐条测试。付费购买、账号登录与系统授权由用户决定和完成。
- 默认只提供最小分流：私网、`.lan`、`.local`、`.cn` 直连，其余走代理，不是完整国内域名规则库。验收不得把任意国内网站都当作应直连对象。
- 规则组 `PROXY` 可选线路或 `AUTO`；自动回退组会检查可用性。不要把自动回退误认为三条线路已分别通过验收。
- 文件含可用凭据，只在用户设备间私下传输，不上传订阅转换网站、公开聊天或公开材料。
