# 排错顺序

| 现象 | 首先检查 | 避免的误操作 |
| --- | --- | --- |
| SSH 无法返回 JSON | 手动公钥登录、known_hosts 指纹、Python、sudo -n | 关闭主机校验或自动接受变更指纹 |
| Cloudflare 403 | Token 的三个权限、Zone 范围、来源 IP 限制 | 用 Global API Key 绕过 |
| DNS 冲突 | 是否是旧业务、是否遗留 AAAA/CNAME、两条入口代理状态 | 自动删除或覆盖记录 |
| Docker 安装失败 | apt 源、网络、已有 docker.io/containerd、架构 | 自动卸载未知业务依赖 |
| 证书失败 | Zone、Token、TXT 更新、CA 限流、VPS 时间 | 循环强制签发 |
| 容器退出 | 固定版本、配置检查、证书路径与挂载权限 | 使用 latest 或 chmod 777 |
| Reality 不通 | 直连路由、Reality 目标、public key/short ID、客户端版本 | 将 vpn 子域名开启橙色云 |
| Hysteria2 不通 | UDP 443 的云安全组/宿主机网络、SNI、证书 | 仅凭 TCP 443 可达认定 UDP 正常 |
| WebSocket 不通 | ws 橙色云、Full (strict)、8443、Host/path/SNI、WAF | 关闭 TLS 校验 |
| DNS 显示 198.18.x.x | 本机是否运行 fake-ip/TUN；对照服务器解析 | 把客户端 fake-IP 当作真实 Cloudflare A 记录 |
| 网页能打开但 verify 失败 | 分别检查三条线路和出口，确认没有其他代理接管 | 只测网页就报告所有协议成功 |
| timer 失败 | systemctl 状态、脱敏报告、磁盘、权限、任务锁 | 直接自动升级或重启整机 |

Cloudflare 根路径返回 404 不等于 WebSocket 入口不可用；正确随机 path 下的 Upgrade 返回 101 才说明 WebSocket 握手成功。最终仍应运行真实客户端协议测试。

一些网络或 Cloudflare 规则可能按来源、User-Agent 拦截请求。比较本地、VPS、真实客户端的结果，保留 HTTP 状态和时间，不要直接归因于应用宕机。

本地测试期间避免多个代理软件互相接管：VPS 的 IP 和两个入口域名保持直连规则。`verify` 的 TCP 直连入口使用真实 VPS IP，TLS SNI 仍保留域名。
