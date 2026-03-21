# TigerVNC Viewer Shortcut

这个目录保存一个可移植的 TigerVNC 启动脚本，方便在不同 Linux 机器上复用。

## 文件

- `xtigervncviewer_shortcut.sh`: 通用启动脚本
- `desktop/xtigervncviewer_shortcut.desktop`: 桌面启动器模板
- `install_desktop_launchers.sh`: 安装到桌面的脚本

## 特性

- 支持交互输入 `IP/主机名 + 显示号`
- 支持直接传参
- 支持 `zenity`，没有 `zenity` 时回退到终端输入
- 记住上次输入，默认保存在 `~/.config/xtigervncviewer_shortcut/last-target.conf`
- 不依赖当前机器上的固定绝对路径

## 用法

交互式启动：

```bash
./xtigervncviewer_shortcut.sh
```

直接指定目标：

```bash
./xtigervncviewer_shortcut.sh 192.168.100.137 2
./xtigervncviewer_shortcut.sh 192.168.100.137:2
./xtigervncviewer_shortcut.sh --target 192.168.100.137:2
```

如果你的 viewer 不叫 `xtigervncviewer`，可以指定环境变量：

```bash
XTIGERVNCVIEWER_BIN=/path/to/xtigervncviewer ./xtigervncviewer_shortcut.sh
```

## 迁移

把整个目录拷到别的机器后，只要满足以下条件就可以运行：

- 系统里有 `bash`
- 系统里有 `xtigervncviewer`，或者通过 `XTIGERVNCVIEWER_BIN` 指定
- 需要图形输入框时，安装 `zenity`；否则脚本会回退到终端提示

## 安装桌面快捷方式

把启动器安装到当前用户桌面：

```bash
cd ~/github/DevToolbox/xtigervncviewer_shortcut
./install_desktop_launchers.sh
```

如果你想把安装目标目录写死成别的路径，也可以用：

```bash
XDG_DESKTOP_DIR=~/Desktop ./install_desktop_launchers.sh
```
