# 官方来源与版本基线

核对日期：2026-10-19。本项目参考上游官方文档编写；升级前请核对目标版本的官方说明。

- [Docker Ubuntu 官方 apt 安装](https://docs.docker.com/engine/install/ubuntu/)：官方软件源、签名与 Compose plugin。不会运行第三方 Docker 一键脚本。
- [sing-box VLESS inbound](https://sing-box.sagernet.org/configuration/inbound/vless/)、[TLS / Reality](https://sing-box.sagernet.org/configuration/shared/tls/)、[Hysteria2 inbound](https://sing-box.sagernet.org/configuration/inbound/hysteria2/)、[WebSocket transport](https://sing-box.sagernet.org/configuration/shared/v2ray-transport/)。
- [sing-box v1.13.14](https://github.com/SagerNet/sing-box/releases/tag/v1.13.14)：本项目固定配置基线；不声称是最新版本。部署时记录 GHCR digest。
- [sing-box migration](https://sing-box.sagernet.org/migration/)：升级前核对配置迁移。
- [Cloudflare DNS create](https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/create/)、[Zone settings get](https://developers.cloudflare.com/api/resources/zones/subresources/settings/methods/get/)：DNS 与 strict TLS 预检。
- [Cloudflare API MCP 官方仓库](https://github.com/cloudflare/mcp/blob/main/README.md)：API MCP 地址、OAuth / API Token 授权及 DNS 操作能力。具体权限和秘密交付能力须在用户环境验证；本项目 CLI 尚无 MCP 适配，仍使用独立 API Token。
- [acme.sh](https://github.com/acmesh-official/acme.sh)、[Cloudflare DNS API](https://github.com/acmesh-official/acme.sh/wiki/dnsapi)：DNS-01、CF_Token/CF_Zone_ID、install-cert 和 reloadcmd。
- acme.sh 源码固定 `3.1.6`，下载自官方 codeload，SHA-256 固定在执行器中；校验失败时停止，不跳过。
- [mihomo VLESS](https://wiki.metacubex.one/config/proxies/vless/)、[Hysteria2](https://wiki.metacubex.one/config/proxies/hysteria2/)、[DNS](https://wiki.metacubex.one/config/dns/)：客户端模板依据。

源码摘要只验证与本项目选定内容一致；公开发布前仍应审查上游依赖与升级记录。
