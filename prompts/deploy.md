# 交给 AI 的部署任务

将以下内容复制给有终端、SSH 和网络能力的 AI：

```text
请使用本仓库完成个人 VPN 搭建。先阅读 AGENTS.md、README.md、docs/setup.md 和 docs/operations.md。

目标：全新 Ubuntu 24.04 VPS + Cloudflare Zone，三线路代理网关、可导入的客户端文件、自动续期/巡检/备份。
使用已有 vpnctl.py，不重新编写一键安装脚本，不把秘密输出到会话。

1. 检查本地 Python、SSH、Git。读取 config.example.json，集中收集缺失的非敏感资源参数。
2. 执行 init，填写 config.local.json。指导我通过 SSH Agent/私钥路径连接、从云控制台核对主机指纹。
3. 指导我在安全终端输入 CF_API_TOKEN，不要求我把值粘到聊天。确认 Zone 激活、Full (strict)、云安全组。
4. 执行 plan 和 preflight。说明计划中的域名、端口、服务器目录及维护任务。
5. 我要求搭建即授权按这个范围进行常规部署；预检通过后继续 deploy，不对每个命令重复确认。
   如发现已有业务、DNS 冲突、需要删除/迁移资源或资源不足，先报告具体问题，不绕过保护。
6. deploy 完成后执行 status；从官方 Release 找到适合本机的 mihomo 核心，核对下载摘要，运行 verify。
7. 某线路失败时读取最小范围的脱敏信息，按 docs/troubleshooting.md 定位。不关闭 TLS 校验，不反复强制签证书。
8. 给出 artifacts 下的本地文件路径，不展示文件内容。指导我导入客户端并开启 TUN。
9. UFW 如果尚未启用，先检查现有规则、实际 SSH 端口与第二个 SSH 会话，再按已授权范围启用；不要 reset。
   若还需关闭 SSH 密码登录，必须先验证第二个公钥会话再修改，保留当前连接。
10. 确认证书续期任务、两个 systemd timer 和第一份备份已存在。
11. 交付报告分别列出：服务端检查、三线路真实出口、手机/电脑 TUN 与 DNS、待处理事项。
    未完成的客户端或 DNS 验收必须标记“未验证”，不能宣称全部成功。

可以使用当前项目的官方文档链接；版本升级或配置变化时优先 Context7（若可用），否则查官方原始文档。
请持续执行到完成或遇到确实需要我提供的资源，最终给出可复核的证据。
```
