# Ubuntu X11 Window Split Tools

这个目录提供四个面向 Ubuntu GNOME X11 的窗口平铺/聚焦/配置脚本：

- `split3.sh`: 将当前显示器上的窗口平铺为 1 到 3 列
- `split6.sh`: 将当前显示器固定为 `3 列 x 2 行` 网格，并支持后台守护模式
- `focus_split6_slot.sh`: 聚焦六分屏中的某个槽位，并把鼠标移动到该槽位中心
- `export_split6_hotkeys.sh`: 导出当前 `split6` 相关 GNOME 快捷键备份

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

### focus_split6_slot.sh

- 读取 `split6` 写入的状态文件
- 按槽位号直接激活对应窗口
- 同时把鼠标移动到目标槽位中心
- 适合配合快捷键快速跳转六分屏中的某一格

### export_split6_hotkeys.sh

- 导出当前 `split6` 相关的 GNOME 快捷键
- 同时导出 GNOME Terminal 当前快捷键
- 默认输出到 `~/.cache/split6/hotkeys_backup.txt`

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
chmod +x split3.sh split6.sh focus_split6_slot.sh configure_split6_hotkeys.sh export_split6_hotkeys.sh
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

查看槽位状态并聚焦：

```bash
./focus_split6_slot.sh --status
./focus_split6_slot.sh 1
```

导出当前快捷键备份：

```bash
./export_split6_hotkeys.sh
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

## focus_split6_slot.sh 用法

命令：

```bash
./focus_split6_slot.sh SLOT
./focus_split6_slot.sh --status
```

槽位编号：

```text
1 2 3
4 5 6
```

行为：

- 读取 `~/.cache/split6/state.env`
- 选择指定槽位中的窗口
- 激活该窗口
- 将鼠标移动到该槽位中心

使用前提：

- 先运行过一次 `./split6.sh`
- 或运行 `./split6.sh --daemon`

否则不会有可用的槽位状态文件。

## GNOME 快捷键

执行下面的脚本可写入或更新 GNOME 自定义快捷键：

```bash
./configure_split6_hotkeys.sh
```

导出当前快捷键和 Terminal 键位：

```bash
./export_split6_hotkeys.sh
```

默认导出文件：

```bash
~/.cache/split6/hotkeys_backup.txt
```

如需导出到指定文件：

```bash
./export_split6_hotkeys.sh /tmp/split6_hotkeys_backup.txt
```

如需查看当前系统值：

```bash
gsettings get org.gnome.settings-daemon.plugins.media-keys terminal
gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings
```

默认快捷键：

- `Ctrl+Alt+0`：执行一次六分屏整理
- `Ctrl+Alt+Shift+6`：启动六分屏守护
- `Ctrl+Alt+Shift+5`：停止六分屏守护
- `Ctrl+Alt+1`：聚焦槽位 1
- `Ctrl+Alt+2`：聚焦槽位 2
- `Ctrl+Alt+3`：聚焦槽位 3
- `Ctrl+Alt+4`：聚焦槽位 4
- `Ctrl+Alt+5`：聚焦槽位 5
- `Ctrl+Alt+6`：聚焦槽位 6
- `Ctrl+Alt+7`：GNOME Terminal

聚焦键按编号对应：

```text
1 2 3
4 5 6
```

## 安装到 PATH

如果你希望直接使用 `split3`、`split6`、`focus_split6_slot` 和 `export_split6_hotkeys` 命令：

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/split3.sh" ~/.local/bin/split3
ln -sf "$(pwd)/split6.sh" ~/.local/bin/split6
ln -sf "$(pwd)/focus_split6_slot.sh" ~/.local/bin/focus_split6_slot
ln -sf "$(pwd)/export_split6_hotkeys.sh" ~/.local/bin/export_split6_hotkeys
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
