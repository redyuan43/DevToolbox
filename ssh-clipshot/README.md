# Clipshot Paste Service

`clipshot` 用本机 Tailscale/SSH 作为共享端，解决“本机截图要贴到远端 SSH 命令里”的问题。

## 工作流

1. 本机截图。
2. 本机按 `Super+Ctrl+V`，或运行 `clipshot-send --paste nx1`。
3. 脚本用真实 `scp` 把截图传到 `nx1:~/Pictures/ssh-screenshots/latest.png`。
4. 脚本把 `/home/nx/Pictures/ssh-screenshots/latest.png` 写进本机剪贴板。
5. `--paste` 会自动向当前焦点窗口发送 `Ctrl+Shift+V`，把路径粘到已登录 `nx1` 的终端里。

传输只使用真实 `scp`。一步式自动粘贴会额外使用本机 `ydotool` 向当前焦点窗口发送 `Ctrl+Shift+V`；如果自动粘贴失败，远端路径仍保留在本机剪贴板里，可以手动粘贴。

## 本机安装

```bash
./install-local.sh --shortcut
```

如果不想注册 GNOME 快捷键，只安装命令：

```bash
./install-local.sh
```

手动把截图发到 `nx1` 并把远端路径放进本机剪贴板：

```bash
clipshot-send nx1
```

手动执行完整的一步式发送和粘贴：

```bash
clipshot-send --paste nx1
```

可选的旧本机共享上传命令：

```bash
clipshot-upload
```

如果剪贴板里没有图片，`clipshot-upload` 会自动使用 `~/Pictures/Screenshots` 里最近 15 分钟内的 PNG 截图。
可以用 `CLIPSHOT_SCREENSHOT_MAX_AGE_SECONDS` 调整这个时间窗口。

## 可选远端绑定

主路径不需要远端绑定。只有在你想让远端 shell 自己拉本机共享截图时，才需要安装这一段。
把远端工具安装到某个 SSH alias，例如 `nx3`：

```bash
./install-remote.sh nx3 --bashrc
```

打开新的远端 shell 后，按 `Ctrl+x Ctrl+s` 会上传本机当前剪贴板截图、拉取到远端并插入远端路径。
如果终端拦截 `Ctrl+s`，也可以按 `Ctrl+x Ctrl+v` 或 `Ctrl+x` 后再按普通 `v`。
也可以直接按 `F12` 作为单键触发。
触发后会打印 `clipshot: <远端图片路径>`，并把同一个路径插入当前命令行。

如果不写入远端 `~/.bashrc`：

```bash
./install-remote.sh nx3
source ~/.config/clipshot/clipshot.bash
```

## 配置

远端默认从下面的位置拉图：

```bash
ivan@ivan-tm1613.taild500c8.ts.net:~/.local/share/clipshot/latest.png
```

可以在远端覆盖：

```bash
export CLIPSHOT_SOURCE=ivan@ivan-tm1613.taild500c8.ts.net
export CLIPSHOT_SOURCE_PATH=~/.local/share/clipshot/latest.png
export CLIPSHOT_DEST_DIR=~/Pictures/ssh-screenshots
export CLIPSHOT_PRINT_PATH=latest
export CLIPSHOT_UPLOAD_COMMAND=~/.local/bin/clipshot-upload
export CLIPSHOT_SSH_OPTS='-o ConnectTimeout=5'
export CLIPSHOT_SCP_OPTS='-o ConnectTimeout=5'
```

## 验证

本机：

```bash
clipshot-send nx1
wl-paste --no-newline
```

一键粘贴验证：

```bash
clipshot-send --paste nx1
```

运行前把焦点放在已经登录 `nx1` 的终端命令行里。

旧共享上传验证：

```bash
clipshot-upload
file ~/.local/share/clipshot/latest.png
```

远端：

```bash
clipshot-pull
```

远端一键上传、拉取并插入路径的交互验证：

```bash
source ~/.config/clipshot/clipshot.bash
# 然后按 F12、Ctrl+x Ctrl+s、Ctrl+x Ctrl+v，或 Ctrl+x 后按 v
```

如果远端无法拉取，先确认远端能 SSH 到本机：

```bash
ssh ivan@ivan-tm1613.taild500c8.ts.net hostname
```
