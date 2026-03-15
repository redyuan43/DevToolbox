# WeChat Auto Reply

Ubuntu X11 下的微信自动读信与自动回复工具。当前默认实现采用“独立聊天窗口 + `xwd` 精确截窗 + 本地 OpenAI 兼容多模态模型”的方案，不依赖官方 API，也不解析微信本地数据库。配置和能力分为三层：`guard`、`tools`、`experimental`。

## 当前进度

### 当前代码已经解决的问题

- 已经支持独立聊天窗口模式下的文本自动化：窗口发现、状态查询、显式 `send-text` / `send-file`、守护流程和审计日志。
- 已经支持 `db-detect` 链路：可监听 `session/message` 目录写入，新增 `db-detect`、`db-detect-once`、`db-status` 命令。
- 已经支持两条数据库检测路径：
  - `sqlcipher + hook`：为后续直接读库预留完整链路。
  - `memory` 回退：拿不到 key 时，仍可基于数据库事件和进程内存识别目标群。
- 已经能在本机稳定定位目标群 `chatroom id`，并在数据库活动发生时按规则前置已有群窗口。
- 已经能区分群窗口里常见的 `text` / `file` / `image` / `system` 项，群聊里也增加了基于气泡颜色的方向修正，减少把自己消息误判成入站消息的概率。
- 已经定位到本机账号级密钥材料入口：
  - `~/Documents/xwechat_files/all_users/login/<wxid>/key_info.db`
  - `~/.xwechat/login/<wxid>/key_info.dat`

### 当前还存在的问题

- 还没有拿到 `message_0.db` / `session.db` 的最终 SQLCipher key，`sqlcipher` 直读正文链路尚未打通。
- 当前这版 Ubuntu `xwechat` 大概率把 WCDB / SQLCipher 静态编进了主二进制，`LD_PRELOAD` 的 `sqlite3_*` hook 在本机上可能拿不到调用日志，`db_hook.jsonl` 可能为空。
- `memory` 模式现在更适合做“检测到群活动、识别群身份、前置窗口”，还不是稳定的全量明文读库方案。
- 群聊正文如果完全不依赖窗口视觉，纯内存提取仍有噪音；目前更稳定的是“知道哪个群有活动、谁发的、是否需要弹窗”。
- 整套自动化仍然依赖 Ubuntu X11 前台 GUI 环境，不是协议级机器人，也不支持 Wayland。

### 后面打算继续修复的问题

- 继续逆向 `key_info_data` 的解封装逻辑，补齐 `message_0.db` / `session.db` 的真实解密参数。
- 在能稳定开库后，完成目标群会话表、消息表和最新消息字段的直接查询，减少对窗口视觉的依赖。
- 将当前 `openat` backtrace 收敛到真实函数入口，再重新布置动态探针，避免把中段返回地址误当作 probe 点。
- 在数据库直读链路成熟后，把 `db-detect` 从“活动检测 + 弹窗”提升到“直接读取最新消息内容和发送者”的稳定模式。

## 当前能力

- `guard`：自动发现白名单独立聊天窗口、自动读新消息、自动文本回复、自动下载入站文件
- `tools`：`send-text`、`send-file`、`pause` / `resume` / `status`
- `db`：可选的本地数据库事件检测链路；优先走 `sqlcipher + hook`，拿不到 key 时自动回退到“DB 文件事件 + 主进程内存解析目标群身份”
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
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml db-detect-once
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml db-detect
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml db-status
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

## 数据库检测模式

`db-detect` 现在有两种模式：

- `sqlcipher`：带 hook 重启微信，抓 key 和 `PRAGMA cipher_*`，再只读开库
- `memory`：不重启微信，直接监听 `message/session` 目录写入，并通过 root helper 解析主 `wechat` 进程内存里的目标群标识；如果目标群独立窗口已打开，还会在触发时抓一次窗口，识别最新消息类型/方向/文本，并按规则前置该窗口

当前推荐 `resolver_mode: memory`，直接走数据库触发 + 进程内存解析，不再依赖截图和视觉识别。

如果你要走更完整的 `sqlcipher` 链路，先用：

```bash
bash scripts/start_wechat_with_db_hook.sh
```

它会：

- 编译 `native/wechat_db_hook.c`
- 停掉当前微信主进程
- 通过 `LD_PRELOAD` 重启微信
- 把数据库 key / `PRAGMA cipher_*` 相关调用写到 `~/.local/state/wechat-auto-reply/db_hook.jsonl`

当前 hook 已经覆盖：

- `sqlite3_open_v2`
- `sqlite3_key`
- `sqlite3_key_v2`
- `sqlite3_exec`
- `sqlite3_prepare_v2`

如果 `db_hook.jsonl` 仍然是空的，说明当前这版 Ubuntu `xwechat` 更可能把 WCDB / SQLCipher 静态塞进了主二进制，没有走可被 `LD_PRELOAD` 直接拦截的动态 `sqlite3_*` 符号。

数据库检测链路再运行：

```bash
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml db-detect-once
python3 main.py --config ~/.config/wechat-auto-reply/config.yaml db-detect
```

`memory` 回退模式不需要重启微信，但要求当前机器支持：

```bash
sudo -n true
```

也就是当前用户能无密码执行 `sudo`，因为读取 `/proc/<wechat-pid>/mem` 需要 root。

当前 `memory` 模式的默认行为是：

- 只监控 `db_parse.target_chat_title`
- 只在数据库有写入事件时工作，不做高频窗口轮询
- 如果目标群独立窗口已经打开：
  - 识别最新可见消息是 `text` / `file` / `image`
  - 判断是 `inbound` 还是 `outbound`
  - 只有“别人发来的新消息”才会触发前置窗口
- 如果目标群独立窗口没打开：
  - 不自动打开群
  - 只记录 `popup_window_missing`

`sqlcipher` 链路额外依赖系统包：

```bash
sudo apt-get install -y sqlcipher
```

`sqlcipher` 模式现在不只是“知道有新行”，而是会：

- 自动探测 `session.db` / `message_0.db` 的候选表结构
- 缓存目标群会话映射到 `db_schema_cache.json`
- 在成功开库后查询目标群最近消息行
- 尝试从消息行里提取 `latest_text`、`latest_sender_id`、`latest_sender_name`、`latest_message_type`

当前本机额外确认到一条本地线索：

- `~/Documents/xwechat_files/all_users/login/<wxid>/key_info.db`
- `~/.xwechat/login/<wxid>/key_info.dat`

这两处保存了账号级 `key_info_data` blob。当前实现已经能定位并分析这类材料，但还没有把它完全解封装成 `message_0.db` 的最终 SQLCipher key。

## 状态文件

- 配置：`~/.config/wechat-auto-reply/config.yaml`
- 校准：`~/.local/state/wechat-auto-reply/calibration.json`
- 运行状态：`~/.local/state/wechat-auto-reply/runtime_state.json`
- 审计日志：`~/.local/state/wechat-auto-reply/audit.jsonl`
- 数据库 hook 日志：`~/.local/state/wechat-auto-reply/db_hook.jsonl`
- 数据库目标缓存：`~/.local/state/wechat-auto-reply/db_target_cache.json`
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
- `db-detect` 当前优先用于“感知目标群是否有数据库侧活动”和“解析目标群内部 `chatroom id`”；它还不是稳定的全量明文读库能力。

## systemd --user

示例单元文件见 [systemd/wechat-auto-reply.service](/home/dgx/github/DevToolbox/wechat-auto-reply/systemd/wechat-auto-reply.service)。
