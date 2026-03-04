# Ubuntu X11 Window Split Tools

这个目录提供两个面向 Ubuntu GNOME X11 的窗口平铺脚本：

- `split3.sh`: 将当前显示器上的窗口平铺为 1 到 3 列
- `split6.sh`: 将当前显示器固定为 `3 列 x 2 行` 网格，并支持后台守护模式

适用于终端、浏览器、编辑器等普通顶层窗口，不依赖 GNOME Shell 扩展。

## 功能概览

### split3.sh

- 按当前活动窗口所在显示器工作
- 只收集当前工作区、当前显示器上的普通可见窗口
- 自动根据窗口数量退化为 1 列、2 列或 3 列
- 支持 `--dry-run` 和 `--verbose`

### split6.sh

- 使用固定 `3 x 2` 槽位布局
- 基于 `_NET_WORKAREA` 计算可用区域，自动避开 GNOME 顶栏和 Dock
- 支持一次性整理窗口，或使用守护进程自动补位
- 支持 `--daemon`、`--status`、`--stop`、`--dry-run`、`--verbose`
- 内部边界留有轻微重叠，用来遮住 GNOME 窗口阴影缝隙

## 依赖

运行环境：

- Ubuntu GNOME on X11
- `bash`
- `xdotool`
- `xprop`
- `xwininfo`
- `xrandr`

安装依赖：

```bash
sudo apt update
sudo apt install -y xdotool x11-utils x11-xserver-utils
```

说明：

- `xprop` 和 `xwininfo` 通常由 `x11-utils` 提供
- `xrandr` 通常由 `x11-xserver-utils` 提供
- Wayland 不受支持；如果 `XDG_SESSION_TYPE=wayland`，脚本会直接退出

## 快速开始

进入目录并授予执行权限：

```bash
cd /home/dgx/github/DevToolbox/spilt_screens
chmod +x split3.sh split6.sh
```

直接运行：

```bash
./split3.sh
./split6.sh
```

预览而不移动窗口：

```bash
./split3.sh --dry-run
./split6.sh --dry-run
```

查看调试信息：

```bash
./split3.sh --verbose
./split6.sh --verbose
```

## split3.sh 用法

命令：

```bash
./split3.sh [--dry-run] [--verbose] [--help]
```

行为：

- 使用当前活动窗口判断目标显示器
- 收集当前工作区内的候选窗口
- 最多处理 3 个窗口
- 当匹配窗口少于 3 个时，自动回退为均分布局

适合场景：

- 浏览器 + 编辑器 + 终端三栏并排
- 双窗口对照
- 单窗口快速拉满当前可用区域

## split6.sh 用法

命令：

```bash
./split6.sh [--daemon|--status|--stop] [--dry-run] [--verbose] [--help]
```

一次性整理：

```bash
./split6.sh
```

启动后台守护进程：

```bash
./split6.sh --daemon
```

查看守护进程状态：

```bash
./split6.sh --status
```

停止守护进程：

```bash
./split6.sh --stop
```

行为：

- 固定使用 `3 列 x 2 行`
- 最多填充 6 个槽位
- 少于 6 个窗口时，其余槽位保持为空
- 守护模式运行时，新开窗口会优先进入下一个空槽位
- 如果 6 个槽位已满，新窗口保持原状
- 守护进程会锁定启动时所在的显示器与工作区

运行时文件：

- PID 文件：`~/.cache/split6/daemon.pid`
- 状态文件：`~/.cache/split6/state.env`
- 日志文件：`~/.cache/split6/daemon.log`

## 安装到 PATH

如果你希望直接使用 `split3` 和 `split6` 命令：

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/split3.sh" ~/.local/bin/split3
ln -sf "$(pwd)/split6.sh" ~/.local/bin/split6
```

确认 `~/.local/bin` 已在 `PATH` 中：

```bash
echo "$PATH"
```

## 退出码

- `0`: 成功
- `1`: 环境或依赖异常
- `2`: 没有找到可处理窗口
- `3`: 移动或缩放失败
- `4`: 守护进程或状态文件异常

## 已知限制

- 仅支持 X11，会话为原生 Wayland 时不可用
- 某些应用可能忽略通用 X11 的 resize/move 请求
- 部分 GNOME 特殊窗口状态无法完全清除，脚本仅做尽力处理
- `split6.sh --daemon` 使用轻量轮询，不是事件驱动，因此响应是近实时而不是瞬时
