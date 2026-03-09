# WeChat Auto Reply

Ubuntu X11 下的微信自动读信与自动回复工具。当前默认实现采用“独立聊天窗口 + `xwd` 精确截窗 + 本地 OpenAI 兼容多模态模型”的方案，不依赖官方 API，也不解析微信本地数据库。配置和能力分为三层：`guard`、`tools`、`experimental`。

## 当前能力

- `guard`：自动发现白名单独立聊天窗口、自动读新消息、自动文本回复、自动下载入站文件
- `tools`：`send-text`、`send-file`、`pause` / `resume` / `status`
- `experimental`：可选历史补读；默认不进入守护主流程
- `calibrate` 校验独立窗口布局
- `once` 执行一次检测与回复流程
- `daemon` 常驻轮询
- 记录审计日志与最近消息状态
- 使用同一个本地多模态模型同时读窗口与生成回复
- 自动忽略本人 / 机器人已发的出站消息
- 默认只看当前屏；仅在启用实验历史补读后才会上翻

## 运行前提

- Ubuntu X11 会话
- 已安装并登录微信 Linux 桌面版
- 已安装 `ffmpeg`、`xwininfo`、`xdotool`、`xinput`、`xsel`
- 本地 `ollama serve` 正在运行
- 推荐系统包：`python3-pyatspi`、`accerciser`

## 安装

```bash
cd /home/dgx/github/DevToolbox/wechat-auto-reply
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mkdir -p ~/.config/wechat-auto-reply
cp config.example.yaml ~/.config/wechat-auto-reply/config.yaml
```

按实际环境修改 `~/.config/wechat-auto-reply/config.yaml`，至少确认：

- `window.monitor_mode`
- `window.display`
- `window.xauthority`
- `ollama.api_format`
- `ollama.base_url`
- `guard.whitelist.private_chats`
- `guard.whitelist.group_chats`
- `reply.per_contact_prompts`

## 命令

```bash
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml calibrate
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml status
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml once
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml daemon
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml send-text --chat Jing --text "你好"
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml send-file --chat Jing --path /abs/path/to/file.md
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml pause
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml resume
```

## 推荐启动方式

日常建议直接用脚本，不用手敲 `systemctl`：

```bash
bash scripts/start_wechat_auto_reply.sh
bash scripts/stop_wechat_auto_reply.sh
```

这两个脚本分别会：

- 启动 `wechat-auto-reply.service`
- 停止 `wechat-auto-reply.service`
- 打印当前服务状态，方便确认有没有真的启动 / 停止

当前仓库默认已经关闭“登录后自动启动”：

```bash
systemctl --user disable wechat-auto-reply.service
```

也就是说，只有你手动运行启动脚本时，它才会开始接管白名单窗口。

## 启动本地 LM Studio 模型

如果你使用 LM Studio 的 OpenAI 兼容接口，可以先运行：

```bash
bash scripts/start_lm_studio_model.sh
```

默认会尝试：

- 将 `/home/dgx/Downloads/LM-Studio-0.4.6-1-arm64.AppImage` 解包到 `~/.cache/lm-studio-appimage/`
- 通过 `systemd --user` 启动 `lmstudio-app.service`
- 等待 `http://127.0.0.1:1234/v1/models`
- 加载 `qwen/qwen3.5-35b-a3b`

可通过环境变量覆盖：

```bash
MODEL_KEY=qwen/qwen3.5-35b-a3b \
MODEL_IDENTIFIER=qwen/qwen3.5-35b-a3b \
SERVER_PORT=1234 \
bash scripts/start_lm_studio_model.sh
```

常用检查命令：

```bash
systemctl --user status lmstudio-app.service
curl http://127.0.0.1:1234/v1/models
lms ps
```

## 状态文件

- 配置：`~/.config/wechat-auto-reply/config.yaml`
- 校准：`~/.local/state/wechat-auto-reply/calibration.json`
- 运行状态：`~/.local/state/wechat-auto-reply/runtime_state.json`
- 审计日志：`~/.local/state/wechat-auto-reply/audit.jsonl`
- 全局暂停标记：`~/.local/state/wechat-auto-reply/paused.flag`

## 使用建议

- 默认 `guard` 主线只监控标题命中白名单、且当前已打开的独立聊天窗口。
- 默认不会切主窗口找会话，只看已经单独弹出的聊天窗口。
- 第一次先打开目标联系人独立窗口，再运行 `calibrate` 和 `status`。
- 先用 `once` 验证单次流程，再切到 `daemon`。
- 首次看到某个独立窗口时只建立基线，不会对当前已显示的旧消息自动补发。
- 当前回复判定只看“当前最底部最新一条非系统消息”。
- 如果当前最底部最新一条是自己发的右侧消息，程序不会回复，也不会再往上捞旧消息。
- 如果输入框已有草稿，本工具会跳过该会话，避免覆盖你的手工输入。
- 入站文件会在微信内部先执行下载，再整理到 `guard.files.downloads.root_dir/<聊天标题>/`。
- 这是前台 GUI 自动化，不是协议级机器人。发送时可能短暂抢焦点。

## systemd --user

示例单元文件见 [systemd/wechat-auto-reply.service](/home/dgx/github/DevToolbox/wechat-auto-reply/systemd/wechat-auto-reply.service)。
