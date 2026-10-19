# Cloudflare API Token 新手教程

你需要在 Cloudflare 里创建一把**给部署脚本使用的专用钥匙**。有了它，脚本才能帮你设置域名解析，并在以后自动续期证书。

本文用 `example.com` 举例。操作时选你自己的域名，不要照抄示例域名。

## 先认识三个名字

| 名字 | 可以怎样理解 | 本项目里怎么用 |
| --- | --- | --- |
| API Token | 一把有指定权限的专用钥匙 | 用来证明脚本有权操作你的域名，必须保密 |
| Zone | 一个域名在 Cloudflare 里的管理区域 | 例如 `example.com` 这个区域包含 `vpn.example.com`、`ws.example.com` 等解析记录 |
| Zone ID | 这个管理区域的编号 | 填进 `config.local.json` 的 `zone_id`，告诉脚本要操作哪个区域 |

**“只作用于该 Zone”就是：只允许这把钥匙操作你选中的域名，不授权给账号里的其他域名。** Cloudflare 允许分别设置 Token 的权限与资源范围。[官方说明](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)

## 第一步：打开创建页面

1. 登录 [Cloudflare 控制台](https://dash.cloudflare.com/)。
2. 进入 **My Profile（我的个人资料）→ API Tokens（API 令牌）**。
3. 点击 **Create Token（创建令牌）**。
4. 选择 **Create Custom Token（创建自定义令牌）**。
5. Token 名称可以填 `vpn-ai-ops`，方便以后识别用途。

这里使用个人资料中的 User API Token 创建流程。界面可能显示英文，也可能显示中文，按括号里的含义对应即可。[官方创建步骤](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)

## 第二步：添加三条权限

在 **Permissions（权限）** 区域添加三行，分别选择下面三列：

| 第一列 | 第二列 | 第三列 | 含义及本项目用途 |
| --- | --- | --- | --- |
| Zone | DNS | Edit | 编辑域名解析。本项目创建两个 VPN 入口；证书签发和续期还需要临时添加 TXT 验证记录。 |
| Zone | Zone | Read | 读取域名区域信息。本项目检查选中的域名是否正确、是否已经激活。 |
| Zone | Zone Settings | Read | 读取域名设置。本项目检查 SSL/TLS 是否为 `Full (strict)`。 |

`Read` 是读取；`Edit` 包含创建、读取、修改和删除等操作。`Zone / DNS / Edit` 表示一行里的三个选项，不需要把这串文字填进名称框。[权限含义](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)

**DNS 编辑权限覆盖选中域名下的 DNS 记录，不只限于 `vpn` 和 `ws` 两条。** 本项目代码只创建所需记录并拒绝覆盖冲突记录，但持有 Token 的人具有你授予的完整权限。因此要把它当作密码保管。

## 第三步：限定只能操作哪个域名

在 **Zone Resources（区域资源）** 中选择：

```text
Include（包含） → Specific zone（指定区域） → 你的域名
```

例如选 `example.com`，不要选 `All zones（所有区域）`。这里选的是整个域名区域，不是单独填写 `vpn.example.com`。[资源范围说明](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)

## 第四步：理解两个可选设置

**Client IP Address Filtering（客户端 IP 地址过滤）** 相当于“允许使用这把钥匙的 IP 白名单”。它不是必填项，首次搭建可以先不添加限制；这样仍然需要持有 Token 才能访问，并且权限仍受前面选定的域名范围约束。设置白名单则能进一步限制使用来源。[官方限制说明](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/)

如果你决定填写，本项目需要允许两处请求来源：

- **运行部署脚本的电脑或 AI 执行环境的公网出口 IP**：它要调用 Cloudflare 创建解析记录。如果 AI 在云端运行，这个地址不一定是你家电脑的 IP。
- **VPS 的公网出口 IP**：服务器以后要调用 Cloudflare 自动续期证书。

这里填写的是 Cloudflare 实际看到的公网来源，不能填电脑的 `192.168.x.x` 内网地址。如果使用代理，实际出口也可能改变；家庭宽带换了公网 IP 后，白名单需要同步更新。这种限制针对 API 请求来源，不是在填写手机连接 VPN 时使用的 IP。

**TTL / 有效期** 用来限定 Token 何时有效，也是可选项。若设置了到期日期，请记下提醒：到期前让 AI 帮你更新服务器上的续期凭据，否则自动续期会失败。只在本机换一个 Token，不会自动更新 VPS 上已经保存的凭据。[IP 与有效期限制](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/)

## 第五步：生成并保存 Token

点击 **Continue to summary（继续查看摘要）**，核对三条权限和选中的域名，然后点击 **Create Token（创建令牌）**。

生成的 Token 是一串字符，**只显示一次**。将它保存到自己的密码管理器；不要贴到聊天、GitHub、公开截图或录屏中。这里创建的是 API Token，不需要使用账号的 Global API Key。[官方保存提示](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)

<a id="find-zone-id"></a>

## 第六步：另外找到 Zone ID

Token 和 Zone ID 是两个不同的值，两者都需要准备：

1. 回到 Cloudflare 控制台，点击你准备用来搭建 VPN 的域名。
2. 打开 **Overview（概览）**，找到页面靠下的 **API** 区域。
3. 复制 **Zone ID** 旁边的编号，不要复制成 **Account ID**。
4. 把 Zone ID 填入 `config.local.json` 的 `zone_id` 字段。**Token 不填进这个 JSON 文件。**

Zone ID 的查找位置来自 [Cloudflare 官方说明](https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/)。

<a id="use-token"></a>

## 创建好了，怎么交给项目使用？

在仓库目录、将要执行部署命令的 **Bash / Zsh 终端**里，先单独运行：

```bash
read -rs CF_API_TOKEN
```

这时终端在等你输入。粘贴 Token 后按回车；屏幕没有显示字符是正常的。然后在**同一个终端**执行：

```bash
export CF_API_TOKEN
python3 vpnctl.py preflight
```

`CF_API_TOKEN` 是脚本约定的环境变量名称，可以理解为“当前终端临时交给脚本的钥匙”。不要把真实 Token 写进命令文本或聊天消息里。

如果 AI 在其他终端、容器或云端工作，它不一定能读取你刚才设置的变量。告诉 AI：“我已经创建 Token，请指导我在你实际执行部署的环境中安全设置它”，使用该工具提供的安全输入方式；不要为了方便直接发送 Token。关闭终端后也可能需要重新输入。

`preflight` 会检查 Token 权限、域名和服务器条件，**还不会创建 DNS 或部署服务**。它通过后再按 [README](../README.md#实际执行的命令) 继续。部署结束，可以用 `unset CF_API_TOKEN` 清除当前终端里的变量；服务器自动续期使用的是其受限目录中已保存的凭据。

## 遇到问题先检查什么？

| 提示或现象 | 先检查 |
| --- | --- |
| 找不到 `CF_API_TOKEN` | 是否先输入并 export；AI 与你是否在同一个执行环境 |
| Cloudflare API 返回 403 | 三条权限是否齐全、是否选对域名、白名单是否包含实际来源、Token 是否过期 |
| Zone ID 格式错误或域名不匹配 | 是否误填了 Token 或 Account ID；编号是否来自当前域名 |
| 提示 SSL/TLS 必须为 Full (strict) | 读取设置的权限不会替你修改设置；按项目要求检查 Cloudflare 的 SSL/TLS 页面 |
| 初次部署成功，后来证书续期失败 | VPS 出口是否被白名单挡住，或者 Token 已到期、被撤销 |

不确定页面怎么选时，可以告诉 AI 字段名称和错误提示，让它继续指导；不要发送 Token 本身。
