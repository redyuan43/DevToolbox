# Android Tablet Second Screen

在 Ubuntu 24 X11 主机上，把 Android 平板接成“第二屏风格”的显示目标工具集。这个目录现在是 `second_screen` 项目的归档位置，汇总了已经验证过的三条路径：

- `Sunshine + Moonlight`：共享当前桌面，适合“我就想看到现在这个桌面”
- `VKMS + xrandr`：在同一个 X11 会话里拉起虚拟副屏，窗口可以拖进虚拟显示区域
- `TigerVNC + AVNC`：独立平板工作区，适合作为兜底方案

## 目录

- `scripts/`
  运行与恢复脚本。包含 `start_second_screen_stream.sh`、`stop_second_screen_stream.sh`、`second_screen_status.sh` 以及 VKMS/VNC/workspace 辅助脚本。
- `docs/`
  记录本机验证过的说明文档，例如 `vkms-virtual-monitor.md` 和 `tablet-workspace.md`。
- `skill-src/android-tablet-sunshine-moonlight-ubuntu/`
  可发布到技能仓库的 skill 源目录，已经与 `my-skills-repo` 中发布版本对齐。
- `operator.md`
  当初问题拆解和操作思路的原始记录。
- `artifacts/`
  本机产物目录，例如已下载 APK 和工作区口令文件。该目录被 `.gitignore` 忽略。

## 快速开始

恢复虚拟副屏并重启 Sunshine：

```bash
cd /home/ivan/github/DevToolbox/android-tablet-second-screen
./scripts/start_second_screen_stream.sh
```

如果已经接好平板并希望顺手拉起 Moonlight：

```bash
cd /home/ivan/github/DevToolbox/android-tablet-second-screen
./scripts/start_second_screen_stream.sh --launch-moonlight
```

查看当前状态：

```bash
cd /home/ivan/github/DevToolbox/android-tablet-second-screen
./scripts/second_screen_status.sh
```

停止当前桌面第二屏链路：

```bash
cd /home/ivan/github/DevToolbox/android-tablet-second-screen
./scripts/stop_second_screen_stream.sh
```

如果需要独立平板工作区：

```bash
cd /home/ivan/github/DevToolbox/android-tablet-second-screen
./scripts/setup_tablet_workspace.sh
./scripts/start_tablet_workspace.sh
```

## 当前默认值

- 虚拟副屏输出：`Virtual-1-1`
- 锚定主屏：`HDMI-A-0`
- 默认分辨率：`2560x1600`
- 独立工作区显示号：`:2`

`2560x1600` 是这台机器上稳定且与平板 `2960x1848` 横屏逻辑分辨率比例接近的优选模式。

## 说明

- 这个目录已经取代原来的 `~/github/second_screen` 作为主维护位置。
- 脚本大多按自身目录计算相对路径，所以后续继续在这里维护不会有额外迁移成本。
