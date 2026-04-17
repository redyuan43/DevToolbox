# Tablet Workspace

This workspace creates a separate XFCE desktop inside TigerVNC on display `:2`
with a default geometry of `2960x1848`.

Components:

- `scripts/setup_tablet_workspace.sh`: creates the VNC password and installs the user service.
- `scripts/start_tablet_workspace.sh`: starts the TigerVNC desktop.
- `scripts/stop_tablet_workspace.sh`: stops the TigerVNC desktop.
- `scripts/tablet_workspace_status.sh`: shows VNC session and tablet focus state.
- `scripts/install_avnc_apk.sh`: sideloads the latest AVNC Android client.

Connect from the tablet:

- Host: the Ubuntu host IP shown by `scripts/tablet_workspace_status.sh`
- Port: `5902`
- Password: stored in `artifacts/tablet_workspace_secret.txt`

Launch an app inside the tablet workspace from Ubuntu:

```bash
DISPLAY=:2 xfce4-terminal
```
