# Moonlight + VKMS Software Second Screen Runbook

Use this reference when the desired setup is:

- Android tablet is the client.
- Moonlight runs on Android.
- Ubuntu creates a local simulated output, usually `Virtual-1-1`.
- Sunshine streams that simulated output to Moonlight.

This is the preferred software-only "second screen" path validated in this workspace.

## Mental Model

`VKMS + xrandr` creates the extra same-session desktop area. `Sunshine` captures that virtual output. `Moonlight` displays it on the Android tablet.

This is not a separate VNC desktop and not a physical HDMI sink. It is close enough for moving windows to a tablet-visible area on X11.

## Bring-Up

Run baseline checks:

```bash
scripts/adb_tablet_display_info.sh
scripts/sunshine_moonlight_status.sh
```

If the tablet is authorized and Moonlight is installed, start the full path:

```bash
scripts/start_second_screen_stream.sh 2560x1600 --launch-moonlight
```

The script should:

- enable `vkms` if needed
- place `Virtual-1-1` to the right of the main output
- restart `sunshine`
- launch Moonlight on the Android device

For a different host or tablet, keep `2560x1600` as a stable first try. Fall back to `1920x1080` if the GPU or virtual output rejects the mode.

## Verified Success Signals

Check the host:

```bash
xrandr --query
systemctl --user is-active sunshine
journalctl --user -u sunshine -n 80 --no-pager
```

Expected evidence:

- `Screen 0` includes both the physical monitor and `Virtual-1-1`.
- `Virtual-1-1 connected 2560x1600+<main-width>+0` or similar.
- Sunshine is `active`.
- Sunshine logs include `Streaming display: Virtual-1-1`.

Check the tablet:

```bash
adb shell dumpsys window | rg -n 'mCurrentFocus|mFocusedApp'
adb exec-out screencap -p > /tmp/tablet_second_screen_verify.png
```

Expected evidence:

- Focus is `com.limelight/.Game`.
- The screenshot shows the streamed Ubuntu virtual desktop, not the Moonlight host list.

## Recovery Flow

If Moonlight shows the host but says GameStream is unavailable or terminated:

```bash
systemctl --user restart sunshine
adb shell monkey -p com.limelight -c android.intent.category.LAUNCHER 1
```

If the virtual output is present but not part of the desktop layout:

```bash
scripts/enable_vkms_virtual_monitor.sh 2560x1600
```

If Sunshine does not target the virtual display, inspect its current configuration and logs before changing VNC settings:

```bash
scripts/sunshine_moonlight_status.sh
journalctl --user -u sunshine -n 120 --no-pager
```

If Moonlight is unavailable or unsuitable, use `x11vnc --clip` only as a fallback transport for the same virtual region:

```bash
scripts/start_x11vnc_virtual_monitor.sh 2560x1600+3440+0
scripts/x11vnc_virtual_monitor_status.sh
```

Replace `3440` with the width of the primary monitor from `xrandr`.

## Stop

Stop the Sunshine recovery path:

```bash
scripts/stop_second_screen_stream.sh
```

If the virtual monitor should also disappear, run:

```bash
scripts/disable_vkms_virtual_monitor.sh
```

## Porting Notes For Another Device

- Require ADB authorization first; the tablet must show as `device`, not `unauthorized`.
- Install Moonlight on Android before trying to launch or pair.
- Pair Moonlight with Sunshine manually if PIN entry appears.
- Do not assume native tablet resolution is the best host mode; start with a known-good mode.
- Prefer X11 for this path. Wayland/compositor-specific behavior may require a different approach.
- Keep TigerVNC/AVNC separate in the user's mind: that creates another desktop, not the simulated same-session output.
