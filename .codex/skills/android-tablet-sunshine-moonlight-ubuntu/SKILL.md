---
name: android-tablet-second-screen-ubuntu
description: Configure an Android tablet as a second-screen-style display target for Ubuntu 24.x over USB and ADB. Use when the user wants a Moonlight Android client connected to a local simulated display output via Sunshine and VKMS, current-desktop sharing, a near-real extra screen on X11, or an independent fallback workspace via TigerVNC and AVNC.
---

# Android Tablet Second Screen On Ubuntu

Use this skill for Ubuntu 24.x plus an ADB-connected Android tablet when the user says "把安卓平板当副屏", "共享当前桌面到平板", "没有 fake HDMI 也想多一个桌面", or is confused between mirror, virtual monitor, and independent VNC desktop.

This skill bundles the practical paths that were validated in this workspace:

- `VKMS + Sunshine + Moonlight` for a software-created same-session output streamed to an Android tablet
- `Sunshine + Moonlight` for sharing the current Ubuntu desktop
- `VKMS + xrandr` for a same-session virtual monitor on X11 without a fake HDMI dongle
- `TigerVNC + AVNC` for an independent tablet workspace when the first two are not suitable
- `x11vnc --clip` as a transport fallback for the VKMS-created monitor region
- one-command recovery helpers for "电脑重启后把副屏拉起来"

Read [references/modes.md](references/modes.md) if the user is mixing up "current desktop", "real extra monitor", and "independent remote desktop".
Read [references/moonlight-vkms-runbook.md](references/moonlight-vkms-runbook.md) when the goal is: Android tablet runs Moonlight, Ubuntu simulates an extra display locally, and Sunshine streams that virtual output.

## Use This Skill For

- The user wants the current Ubuntu desktop on the tablet.
- The user wants "something like a second screen" without fake HDMI.
- The user wants a deterministic fallback workspace on the tablet.
- The user wants the Android and Ubuntu install helpers captured in a publishable skill.
- The user wants ADB-based verification of tablet resolution, focus, and installed apps.

## Do Not Use This Skill For

- Native OS-level extended display requirements that explicitly depend on hardware display sinks, DisplayLink, or compositor-specific Wayland features outside this workflow.
- Non-Android tablets or no-ADB environments.

## Decision Rule

1. If the user wants an Android tablet to behave like a software-only extra monitor:
   use `VKMS + Sunshine + Moonlight`; see [references/moonlight-vkms-runbook.md](references/moonlight-vkms-runbook.md).
2. If the user wants the current Ubuntu desktop mirrored/shared:
   use `Sunshine + Moonlight` without relying on VNC.
3. If the user wants a same-session extra desktop area on X11 and has no fake HDMI:
   use `VKMS`, then stream or clip that monitor region.
4. If the user can accept an independent desktop:
   use `TigerVNC + AVNC`.
5. If the user says "我看到的是另一个桌面，不是当前桌面":
   stop treating VNC as the primary answer and move back to `Sunshine + Moonlight` or `VKMS`.

## Bundled Scripts

Baseline and app install:

- `scripts/adb_tablet_display_info.sh`
- `scripts/sunshine_moonlight_status.sh`
- `scripts/second_screen_status.sh`
- `scripts/install_moonlight_apk.sh`
- `scripts/install_avnc_apk.sh`
- `scripts/start_second_screen_stream.sh`
- `scripts/stop_second_screen_stream.sh`

VKMS virtual monitor:

- `scripts/enable_vkms_virtual_monitor.sh`
- `scripts/disable_vkms_virtual_monitor.sh`
- `scripts/vkms_virtual_monitor_status.sh`
- `scripts/start_x11vnc_virtual_monitor.sh`
- `scripts/x11vnc_virtual_monitor_status.sh`

Independent tablet workspace:

- `scripts/setup_tablet_workspace.sh`
- `scripts/start_tablet_workspace.sh`
- `scripts/stop_tablet_workspace.sh`
- `scripts/tablet_workspace_status.sh`
- `scripts/run_in_tablet_workspace.sh`

## Standard Workflow

### 1. Baseline checks

Run:

```bash
scripts/adb_tablet_display_info.sh
scripts/sunshine_moonlight_status.sh
```

Confirm:

- the tablet is `device`, not `unauthorized`
- Android package state for Moonlight or AVNC is visible
- the Ubuntu display layout is visible in `xrandr`
- Sunshine service and web UI state are visible when current-desktop sharing is in scope

### 2. Current desktop sharing with Sunshine and Moonlight

Use this when the user wants the tablet to show the current desktop they are already using.

If the user wants a usable extra monitor rather than a mirror, prefer the validated VKMS path:

```bash
scripts/start_second_screen_stream.sh 2560x1600 --launch-moonlight
```

Expected success signals:

- `Virtual-1-1 connected 2560x1600+3440+0` or similar in `xrandr`
- Sunshine is `active` and its log says it is streaming `Virtual-*`
- Android focus is `com.limelight/.Game`
- `adb exec-out screencap -p` shows the streamed virtual desktop

Recommended steps:

1. For reboot recovery or one-command bring-up, start with:

```bash
scripts/start_second_screen_stream.sh
```

2. Install Moonlight with `scripts/install_moonlight_apk.sh` if needed.
3. Ensure Sunshine is active.
4. Pair Moonlight with Sunshine using the PIN shown on the tablet.
5. Verify Android focus and Sunshine logs with `scripts/sunshine_moonlight_status.sh`.
6. If visual proof is needed, capture a tablet screenshot with:

```bash
adb exec-out screencap -p > /tmp/tablet_verify.png
```

Use this path when the user says "当前屏幕共享" or rejects VNC because it opened a different desktop.

To stop the recovery path cleanly:

```bash
scripts/stop_second_screen_stream.sh
```

### 3. Same-session virtual monitor on X11 without fake HDMI

Use this when the host is on X11 and the user wants something closer to a real extra monitor.

Steps:

1. Enable the monitor:

```bash
scripts/enable_vkms_virtual_monitor.sh
```

2. Inspect the result:

```bash
scripts/vkms_virtual_monitor_status.sh
```

3. Move windows onto the new `Virtual-*` output.
4. Prefer Sunshine if it can target that output cleanly.
5. If Sunshine transport is flaky, start clipped VNC transport for just that region:

```bash
scripts/start_x11vnc_virtual_monitor.sh
scripts/x11vnc_virtual_monitor_status.sh
```

This path gives same-session window movement semantics, but it is still not identical to a hardware monitor sink.

### 4. Independent fallback workspace with TigerVNC and AVNC

Use this when the user accepts "a separate desktop dedicated to the tablet".

Steps:

```bash
scripts/setup_tablet_workspace.sh
scripts/start_tablet_workspace.sh
scripts/install_avnc_apk.sh
scripts/tablet_workspace_status.sh
```

Launch tablet-only apps into that workspace with:

```bash
scripts/run_in_tablet_workspace.sh xfce4-terminal
```

Be explicit that this creates another desktop session, not the current one.

## Resolution Guidance

- Read the tablet's real size and density from `scripts/adb_tablet_display_info.sh`.
- Treat the tablet resolution as a target, not a guarantee that the host display path can expose that mode.
- If `xrandr --output ... --mode ...` fails with `Configure crtc failed`, the current GPU/connector path likely cannot drive that mode.
- For Sunshine streaming, prefer stable host modes such as `2560x1600` or `1920x1080` when exact tablet-native modes are unreliable.

## Common Pitfalls

- Ubuntu 24 package mismatches can break Sunshine; prefer the official Ubuntu 24.04 package when needed.
- Moonlight installed but not paired still looks "working" until stream launch fails.
- Moonlight may show "NVIDIA GameStream terminated" when Sunshine is inactive; restart Sunshine before treating pairing as broken.
- `TigerVNC` succeeding does not mean the user got current-desktop sharing.
- `x11vnc --clip` is a fallback transport; if it exits, do not confuse that with failure of the Sunshine/Moonlight route.
- Some Android text-entry fields reject reliable `adb shell input`; ask the user to enter PINs manually on-device when needed.
- `VKMS` requires X11-style display handling; if the system is not in a compatible session, route back to Sunshine-only sharing or the independent workspace fallback.

## Completion Checklist

- Tablet is visible in `adb devices -l`
- The selected path is stated clearly as one of:
  - software simulated second screen via `VKMS + Sunshine + Moonlight`
  - current desktop share
  - same-session virtual monitor
  - independent tablet workspace
- The corresponding status script shows the expected service, display, and package state
- The user is told any remaining boundary, especially that VNC workspace and Sunshine current-desktop sharing are different results
