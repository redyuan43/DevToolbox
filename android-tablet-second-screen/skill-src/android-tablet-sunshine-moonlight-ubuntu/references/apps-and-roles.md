# Apps And Roles

This reference records the concrete apps used in the validated Ubuntu 24.x plus Android tablet workflow.

## Recommended Primary Path

### Ubuntu host app

- App: `Sunshine`
- Role: host-side low-latency desktop streaming server
- Why it is used:
  - shares the current Ubuntu desktop
  - can target the same live session, including a `VKMS` virtual monitor
  - exposes a local Web UI and logs for pairing and verification

Typical host checks:

```bash
systemctl --user status sunshine --no-pager
curl -kSs -o /dev/null -w '%{http_code}\n' https://127.0.0.1:47990
journalctl --user -u sunshine -n 80 --no-pager
```

### Android tablet app

- App: `Moonlight`
- Android package: `com.limelight`
- Role: Android streaming client for Sunshine
- Why it is used:
  - shows the current Ubuntu desktop on the tablet
  - works well for "当前屏幕共享"
  - is the correct answer when the user rejects VNC because it opened a different desktop

Typical tablet checks:

```bash
adb shell cmd package resolve-activity --brief com.limelight
adb shell dumpsys window | tr -d '\000' | rg 'mCurrentFocus|mFocusedApp'
adb exec-out screencap -p > /tmp/tablet_verify.png
```

## Secondary Fallback Path

### Ubuntu host app

- App: `TigerVNC` / `Xvnc`
- Role: create an independent remote desktop session
- Why it may still be used:
  - stable fallback when no hardware-backed real extra display exists
  - useful for a dedicated tablet-only workspace

Important limitation:

- this is not the current Ubuntu desktop
- this is not a true OS-level extra monitor

### Android tablet app

- App: `AVNC`
- Android package: `com.gaurav.avnc`
- Role: Android VNC client for the independent VNC desktop

Important limitation:

- if the user wants the current screen mirrored or shared, AVNC is the wrong primary path

## Same-Session Extra Desktop Area

### Ubuntu host stack

- Stack: `VKMS + xrandr`
- Role: add a `Virtual-*` output into the current X11 desktop
- Why it is used:
  - allows window movement into a virtual side display
  - gets closer to second-monitor semantics than `TigerVNC`

Transport options:

- `Sunshine + Moonlight` when the virtual output can be streamed cleanly
- `x11vnc --clip` when the user only needs the virtual region transported to Android

## Decision Summary

- Current desktop on tablet:
  use `Sunshine` + `Moonlight`
- Same-session extra desktop area:
  use `VKMS`, then choose `Sunshine` or clipped `x11vnc` as transport
- Independent extra remote workspace:
  use `TigerVNC` + `AVNC`
- True hardware-style extended monitor:
  may require dummy HDMI, DisplayLink, or other display-sink support outside this skill
