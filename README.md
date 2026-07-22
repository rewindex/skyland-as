# skyland-as

森空岛自动签到脚本，支持明日方舟和终末地的自动签到。

> 原始仓库：<https://gitee.com/FancyCabbage/skyland-auto-sign>

> [!TIP]
> 推荐使用 [GitHub Actions](#托管于-github-actions) 进行托管部署，无需本地保持运行。

## 目录

- [获取 Token](#获取-token)
- [环境配置](#环境配置)
- [配置方式](#配置方式)
- [参数优先级说明](#参数优先级说明)
- [运行脚本](#运行脚本)
- [托管于 GitHub Actions](#托管于-github-actions)
- [其他事项](#其他事项)

---

## 获取 Token

> [!IMPORTANT]
> **获取 TOKEN 教程**：
>
> 1. 登录 [森空岛](https://www.skland.com/)
> 2. 在 [这里](https://web-api.skland.com/account/info/hg) 获取 token（`data.content` 即为 token）

---

## 环境配置

安装项目依赖：

```bash
uv sync
```

运行以下命令验证环境是否配置成功：

```bash
python src/main.py --help
```

如果正常显示帮助信息，则说明环境配置成功。

---

## 配置方式

支持三种配置方式，优先级从高到低为：**命令行参数 > 配置文件 > 环境变量**。

### 1. 配置文件（推荐）

在项目根目录创建 `skyland-as.json` 文件，格式如下：

```json
{
  "accounts": [
    {
      "token": "你的 token",
      "games": ["arknights", "endfield"]
    },
    {
      "token": "另一个账号的 token",
      "games": ["arknights"]
    }
  ],
  "runtime": {
    "use_proxy": false,
    "exit_when_fail": false,
    "hide_sign_details": false,
    "log_level": "INFO",
    "no_push": false
  },
  "push": {
    "services": ["serverchan3", "telegram"],
    "serverchan3": {
      "sendkey": "你的 sendkey",
      "uid": "你的 uid"
    },
    "telegram": {
      "bot_token": "你的 Bot Token",
      "chat_id": "你的 Chat ID"
    }
  }
}
```

#### 账号配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `accounts` | array | 是 | 账号列表，支持多账号 |
| `accounts[].token` | string | 是 | 森空岛账号的 token |
| `accounts[].games` | array | 否 | 要签到的游戏列表，默认全部游戏 |

#### 游戏代码

| 代码 | 游戏 |
|------|------|
| `arknights` | 明日方舟 |
| `endfield` | 终末地 |

#### 运行时配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_proxy` | boolean | `false` | 是否启用本地 HTTPS 代理（`http://localhost:8000`） |
| `exit_when_fail` | boolean | `false` | 失败时是否返回非 0 退出码 |
| `hide_sign_details` | boolean | `false` | 是否隐藏角色名和奖励等详细日志 |
| `log_level` | string | `"INFO"` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `no_push` | boolean | `false` | 是否禁用全部推送 |

#### 推送配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `services` | array | 要使用的推送服务列表，未指定时默认全部跳过 |
| `serverchan3.sendkey` | string | Server 酱³ 的 sendkey，必填 |
| `serverchan3.uid` | string | Server 酱³ 的 uid，可选（若不设将自动从 sendkey 中提取） |
| `telegram.bot_token` | string | Telegram Bot Token，必填（从 @BotFather 获取） |
| `telegram.chat_id` | string | Telegram Chat ID，必填（接收消息的用户/群组/频道 ID） |

### 2. 环境变量

```bash
# 账号配置
export TOKEN="token1,token2"

# 运行时配置
export USE_PROXY=false
export EXIT_WHEN_FAIL=false
export HIDE_SIGN_DETAILS=false
export LOG_LEVEL=INFO
export NO_PUSH=false

# 推送配置
export PUSH_SERVICES="serverchan3,telegram"
export SC3_SENDKEY="你的 sendkey"
export SC3_UID="你的 uid"  # 可选，若不设将自动从 sendkey 提取
export TG_BOT_TOKEN="你的 Bot Token"
export TG_CHAT_ID="你的 Chat ID"
```

> **注意**：使用 `TOKEN` 环境变量进行配置会签到所有游戏，无法指定游戏类型。

### 3. 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--config PATH` | 指定配置文件路径，默认读取项目根目录的 `skyland-as.json` | `--config /workspace/skyland-as.json` |
| `--token TOKEN1,TOKEN2` | 指定账号 token，多个用英文逗号分隔 | `--token "token1,token2"` |
| `--games GAME1,GAME2` | 指定要签到的游戏，仅在使用 `--token` 时生效 | `--games arknights,endfield` |
| `--use-proxy` | 启用本地 HTTPS 代理（`http://localhost:8000`） | — |
| `--exit-when-fail` | 任一账号签到失败时返回非 0 退出码 | — |
| `--hide-sign-details` | 启用安全日志模式，隐藏详细签到信息 | — |
| `--log-level LEVEL` | 设置日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` | `--log-level DEBUG` |
| `--no-push` | 禁用全部推送 | — |
| `--push-services SERVICE1,SERVICE2` | 指定要启用的推送服务 | `--push-services serverchan3,telegram` |
| `--sc3-sendkey SENDKEY` | 指定 Server 酱³ 的 sendkey | `--sc3-sendkey "sctp123456tabcde"` |
| `--sc3-uid UID` | 指定 Server 酱³ 的 uid（可选） | `--sc3-uid "123456"` |
| `--tg-bot-token TOKEN` | 指定 Telegram Bot Token | `--tg-bot-token "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"` |
| `--tg-chat-id ID` | 指定 Telegram Chat ID | `--tg-chat-id "123456789"` |

---

## 参数优先级说明

配置优先级固定为：**命令行参数 > 配置文件 > 环境变量**

- **账号配置**：`--token` > `skyland-as.json` 中的 `accounts` > 环境变量 `TOKEN`
- **运行时配置**：命令行参数 > `skyland-as.json` 中的 `runtime` > 对应环境变量
- **推送配置**：命令行参数 > `skyland-as.json` 中的 `push` > 环境变量 `PUSH_SERVICES`、`SC3_SENDKEY`、`SC3_UID`、`TG_BOT_TOKEN`、`TG_CHAT_ID`

---

## 运行脚本

```bash
python src/main.py
```

### 常用示例

只签到明日方舟，并关闭推送：

```bash
python src/main.py \
  --token "token1" \
  --games arknights \
  --no-push
```

使用配置文件，但通过命令行开启安全日志和失败退出：

```bash
python src/main.py \
  --config /workspace/skyland-as.json \
  --hide-sign-details \
  --exit-when-fail
```

使用 Server 酱³ 推送并打开调试日志：

```bash
python src/main.py \
  --token "token1" \
  --push-services serverchan3 \
  --sc3-sendkey "你的 sendkey" \
  --sc3-uid "你的 uid" \
  --log-level DEBUG
```

---

## 托管于 GitHub Actions

> [!CAUTION]
> 若您决定将项目托管于 GitHub Actions 上，**请勿使用配置文件进行配置！**
> **这可能会导致意外的用户凭证泄露！**

> [!TIP]
> 目前非常推荐使用 GitHub Actions 签到。

### 步骤

1. 点击 `Use this template` > `Create a new repository`，推荐将可见性设置为 Private
2. 在 `Settings` > `Secrets and variables` > `Actions` 中进行配置

  > [!IMPORTANT]
  > 所有运行时配置项（非敏感）在 **Repository variables** 中配置，
  > 账号和推送凭据在 **Repository secrets** 中配置。
  >
  > | 类型 | 配置项 |
  > |------|--------|
  > | **Repository secrets** | `TOKEN`、`SC3_SENDKEY`、`SC3_UID`、`TG_BOT_TOKEN`、`TG_CHAT_ID` |
  > | **Repository variables** | `PUSH_SERVICES`、`USE_PROXY`、`EXIT_WHEN_FAIL`、`HIDE_SIGN_DETAILS`、`LOG_LEVEL`、`NO_PUSH` |
  >
  > GitHub 将自动禁用 60 天不活跃的仓库，因此有一个定时提交 commit 的 workflow，请勿禁用。

3. 手动触发一次 `Auto Sign` workflow 检查是否配置成功

---

## 其他事项

怕别用，用别怕。

其实森空岛的英文应该是 Skland；但是原仓库就是 Skyland。将错就错吧。¯\\\_(ツ)_/¯

许可证：[WTFPL](LICENSE)

<details>
  <summary>MIT License from original repo</summary>

```
MIT License

Copyright (c) 2023 xxyz30

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

</details>
