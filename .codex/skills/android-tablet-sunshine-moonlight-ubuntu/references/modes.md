# Display Modes For Android Tablet On Ubuntu

Use this reference when the user mixes up three different goals that sound similar but behave differently.

## 1. Current Desktop Share

Tooling:

- `Sunshine + Moonlight`

What it means:

- The tablet shows the Ubuntu desktop the user is already using.
- Mouse and windows belong to the same live host desktop.
- This is screen streaming, not a new Linux monitor object.

Best for:

- "把我当前桌面投到平板"
- "我希望看到现在这个屏幕"

## 2. Same-Session Virtual Monitor

Tooling:

- `VKMS + xrandr`
- optionally `Sunshine` or clipped `x11vnc` as transport

What it means:

- X11 gains a virtual output such as `Virtual-1-1`.
- Windows can be moved into that extra desktop area.
- This is closer to second-monitor semantics than a VNC desktop.

Boundary:

- It is still constrained by Linux graphics stack behavior.
- Transporting only that virtual output to Android may require experimentation.

Best for:

- "没有 fake HDMI 但我还是想多一个屏幕"
- "我想在同一个桌面里把窗口拖过去"

## 3. Independent Tablet Workspace

Tooling:

- `TigerVNC + AVNC`

What it means:

- A separate XFCE session runs on `:2`.
- It is stable and useful, but it is not the desktop the user is currently looking at on the host.

Best for:

- background dashboards
- dedicated tablet-only apps
- fallback when the user accepts "another desktop"

## 4. True Hardware-Style Extended Display

Typical requirements:

- dummy HDMI plug
- DisplayLink
- compositor- or hardware-specific display sink support

What it means:

- The OS treats the path more like a real monitor output target.

Important:

- `Sunshine + Moonlight` alone does not create this.
- `TigerVNC` does not create this.
- `VKMS` is the closest software-only approximation in this workspace, but not a perfect substitute for every workload.
