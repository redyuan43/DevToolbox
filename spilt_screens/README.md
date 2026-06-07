# Ubuntu X11 Window Split Tools

这个目录提供多个面向 Ubuntu GNOME X11 的窗口平铺/聚焦/配置脚本：

- `split3.sh`: 将当前显示器上的窗口平铺为 1 到 3 列
- `split.sh`: 统一入口，使用 `split --num 3|4|8|16` 整理当前已有窗口
- `split4.sh`: 将当前显示器固定为 `2 列 x 2 行` 网格（4 个槽位）
- `split6_recorded.sh`: 按 2026-03-14 当前桌面录制的 6 终端布局恢复窗口位置
- `split8.sh`: 将当前显示器固定为 `4 列 x 2 行` 网格（8 个槽位）
- `split16.sh`: 将当前显示器固定为 `4 列 x 4 行` 网格（16 个槽位）
- `launch_ptyxis_split.sh`: `split --open` 使用的 Ptyxis 启动实现
- `focus_split6_slot.sh`: 聚焦六分屏中的某个槽位，并把鼠标移动到该槽位中心
- `export_split6_hotkeys.sh`: 导出当前 `split6` 相关 GNOME 快捷键备份

适用于终端、浏览器、编辑器等普通顶层窗口，不依赖 GNOME Shell 扩展。

## 功能概览

### split3.sh

- 按当前活动窗口所在显示器工作
- 只收集当前工作区、当前显示器上的普通可见窗口
- 自动根据窗口数量退化为 1 列、2 列或 3 列
- 对终端类窗口会读取 `WM_NORMAL_HINTS`，按当前显示器可用像素自动换算最接近的列数和行数
- 支持 `--dry-run` 和 `--verbose`

### split6.sh

- 使用固定 `3 x 2` 槽位布局
- 基于 `_NET_WORKAREA` 计算可用区域，自动避开 GNOME 顶栏和 Dock
- 终端类窗口会按当前显示器尺寸自动换算字符网格大小，减少不同显示器上的错位
- 支持一次性整理窗口，或使用守护进程自动补位
- 支持 `--daemon`、`--status`、`--stop`、`--dry-run`、`--verbose`
- 内部边界留有轻微重叠，用来遮住 GNOME 窗口阴影缝隙

### split6_recorded.sh

- 只处理终端类窗口
- 使用当前录制下来的 6 槽位布局，右侧区域保持空出
- 超过 6 个终端时，只移动最靠左的 6 个
- 支持 `--dry-run` 和 `--verbose`

### split8.sh

- 使用固定 `4 x 2` 槽位布局（8 槽位）
- 基于 `_NET_WORKAREA` 计算可用区域，自动避开 GNOME 顶栏和 Dock
- 宽高余数会平均分配到各列/行，槽位只相差最多 1 像素
- 内部边界留有轻微重叠，用来遮住终端字符网格尺寸导致的几像素缝隙
- 8 个窗口时会覆盖整块当前显示器可用区域
- 支持 `--daemon`、`--status`、`--stop`、`--dry-run`、`--verbose`

### split16.sh

- 使用固定 `4 x 4` 槽位布局（16 槽位）
- 同样基于 `_NET_WORKAREA` 计算可用区域，尽量占满可用空间
- 终端类窗口同样会按当前显示器尺寸自动换算列数和行数
- 窗口不足 16 个时保留空槽位，不做拉伸填满
- 支持 `--daemon`、`--status`、`--stop`、`--dry-run`、`--verbose`

### split.sh

- 面向 Ubuntu 默认终端 Ptyxis
- `split --num N` 默认只整理当前已有窗口，不新建窗口
- 需要新开 Ptyxis 时，使用 `split --num N --open`
- `--open` 支持 `--count N`、`--workdir DIR`、`--settle SECONDS`
- 对 `4/8/16` 布局会先启动对应守护进程，让新窗口出现时自动补位

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
- `launch_ptyxis_split.sh` 额外需要 `ptyxis` 命令；当前 Flatpak wrapper `/home/ivan/.local/bin/ptyxis` 可用

## 快速开始

进入目录并授予执行权限：

```bash
cd /home/ivan/github/DevToolbox/spilt_screens
chmod +x split.sh split3.sh split4.sh split8.sh split16.sh launch_ptyxis_split.sh configure_split6_hotkeys.sh
```

直接运行：

```bash
split --num 3
split --num 4
split --num 8
split --num 16
```

安装 Desktop 桌面启动器：

```bash
./install_desktop_launchers.sh
```

预览而不移动窗口：

```bash
./split3.sh --dry-run
./split6.sh --dry-run
./split6_recorded.sh --dry-run
./split8.sh --dry-run
./split16.sh --dry-run
```

查看调试信息：

```bash
./split3.sh --verbose
./split6.sh --verbose
./split6_recorded.sh --verbose
./split8.sh --verbose
./split16.sh --verbose
```

桌面启动器模板位于 `desktop/`，安装脚本会复制到 `~/Desktop` 并尽量标记为受信任。

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

## split6_recorded.sh 用法

命令：

```bash
./split6_recorded.sh [--dry-run] [--verbose] [--help]
```

行为：

- 使用当前活动窗口判断目标显示器
- 只收集当前工作区、当前显示器上的终端类窗口
- 会把录制时的布局按当前工作区比例做缩放
- 如果终端超过 6 个，只移动最靠左的 6 个

## split8.sh 用法

命令：

```bash
./split8.sh [--daemon|--status|--stop] [--dry-run] [--verbose] [--help]
```

行为：

- 固定使用 `4 列 x 2 行`
- 最多填充 8 个槽位
- 8 个窗口时会覆盖整块当前显示器可用区域
- 守护模式会锁定启动时所在的显示器与工作区
- 运行时状态目录：`~/.cache/split8`

槽位编号：

```text
1 2 3 4
5 6 7 8
```

## split16.sh 用法

命令：

```bash
./split16.sh [--daemon|--status|--stop] [--dry-run] [--verbose] [--help]
```

行为：

- 固定使用 `4 列 x 3 行`
- 最多填充 12 个槽位
- 少于 12 个窗口时，其余槽位保持为空
- 守护模式会锁定启动时所在的显示器与工作区
- 运行时状态目录：`~/.cache/split16`

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

- `Ctrl+Alt+3`：`split --num 3`
- `Ctrl+Alt+4`：`split --num 4`
- `Ctrl+Alt+8`：`split --num 8`
- `Ctrl+Alt+Shift+8`：`split --num 16`

## 安装到 PATH

如果你希望直接使用 `split` 命令：

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/split3.sh" ~/.local/bin/split3
ln -sf "$(pwd)/split4.sh" ~/.local/bin/split4
ln -sf "$(pwd)/split8.sh" ~/.local/bin/split8
ln -sf "$(pwd)/split16.sh" ~/.local/bin/split16
ln -sf "$(pwd)/split.sh" ~/.local/bin/split
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
- 终端窗口受字符网格限制，脚本会尽量逼近目标尺寸，但个别像素级误差仍可能存在
- 部分 GNOME 特殊窗口状态无法完全清除，脚本仅做尽力处理
- `split6.sh --daemon` 使用轻量轮询，不是事件驱动，因此响应是近实时而不是瞬时
