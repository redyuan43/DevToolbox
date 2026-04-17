#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="${repo_root}/artifacts/moonlight"
mkdir -p "${out_dir}"

api_url="https://api.github.com/repos/moonlight-stream/moonlight-android/releases/latest"

echo "Fetching latest Moonlight Android release metadata..."
readarray -t release_info < <(
  python3 - <<'PY'
import json, urllib.request

url = "https://api.github.com/repos/moonlight-stream/moonlight-android/releases/latest"
with urllib.request.urlopen(url, timeout=20) as response:
    data = json.load(response)

print(data["tag_name"])
for asset in data.get("assets", []):
    if asset["name"] == "app-nonRoot-release.apk":
        print(asset["browser_download_url"])
        break
else:
    raise SystemExit("app-nonRoot-release.apk not found in latest release")
PY
)

tag="${release_info[0]}"
apk_url="${release_info[1]}"
apk_path="${out_dir}/moonlight-${tag}-nonroot.apk"

if [[ ! -f "${apk_path}" ]]; then
  echo "Downloading ${tag} to ${apk_path}..."
  curl -L --fail --output "${apk_path}" "${apk_url}"
else
  echo "APK already present at ${apk_path}"
fi

echo "Checking for an attached Android device..."
device_count="$(adb devices | awk 'NR>1 && $2=="device" {count++} END {print count+0}')"
if [[ "${device_count}" -lt 1 ]]; then
  echo "No authorized Android devices found. Connect the tablet and accept USB debugging, then rerun."
  exit 1
fi

echo "Installing Moonlight on the connected tablet..."
adb install -r "${apk_path}"
echo "Moonlight install complete: ${apk_path}"
