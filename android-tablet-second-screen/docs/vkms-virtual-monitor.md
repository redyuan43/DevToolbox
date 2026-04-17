# VKMS Virtual Monitor On Ubuntu 24 X11

This machine is an AMD-only host using `amdgpu` on Ubuntu 24 and X11.

## What Works

- Loading `vkms` dynamically creates a new DRM device and a new X11 output.
- On this machine, that output appeared as `Virtual-1-1`.
- After `vkms` was loaded, `xrandr` exposed the virtual output as `connected`.
- The virtual output can be placed into the current desktop layout with:

```bash
xrandr --output Virtual-1-1 --mode 2560x1600 --right-of HDMI-A-0
```

This is not a separate VNC/XFCE session. It becomes part of the same X11 desktop space, so windows can be moved onto it.

## What This Solves

This gets much closer to "real second monitor semantics" than `TigerVNC + Xvnc` because:

- it is part of the current X11 desktop
- window movement between displays is possible
- it does not require a fake HDMI plug

## What Is Still Tricky

- Transporting only that virtual output to Android still needs a viewer path.
- Sunshine sees the `vkms` output and logs its DRM connector, but on Linux/AMD it may fall back to slower capture paths because `vkms` has no render node.
- A clipped current-desktop VNC path is still a useful fallback if Sunshine selection proves unreliable.

## Verified Local Evidence

- `modinfo amdgpu` shows `virtual_display` support, but it is load-time only.
- `modinfo vkms` is present on the running kernel.
- `sudo modprobe vkms enable_cursor=1` created:
  - `/sys/class/drm/card0-Virtual-1`
  - a second X11 provider
  - `Virtual-1-1` in `xrandr`
- `xrandr` successfully set `Virtual-1-1` to `2560x1600` to the right of `HDMI-A-0`.
- Sunshine restart logs showed it detected the `vkms` monitor and its connector.

## Scripts

- `scripts/enable_vkms_virtual_monitor.sh`
- `scripts/disable_vkms_virtual_monitor.sh`
- `scripts/vkms_virtual_monitor_status.sh`

## Recommended Use

1. Enable the virtual monitor.
2. Move windows onto `Virtual-1-1`.
3. Test whether Sunshine can stream that output cleanly.
4. If Sunshine is flaky, switch transport only, not display generation:
   keep `vkms` for the virtual monitor, and use a clipped current-desktop remote path for Android.
