#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="${repo_root}/artifacts/android"
mkdir -p "${out_dir}"

readarray -t release_info < <(
  python3 - <<'PY'
import json, urllib.request

url = "https://api.github.com/repos/gujjwal00/avnc/releases/latest"
with urllib.request.urlopen(url, timeout=20) as response:
    data = json.load(response)

print(data["tag_name"])
for asset in data.get("assets", []):
    if asset["name"].endswith(".apk"):
        print(asset["name"])
        print(asset["browser_download_url"])
        break
else:
    raise SystemExit("No APK found in latest AVNC release")
PY
)

tag="${release_info[0]}"
apk_name="${release_info[1]}"
apk_url="${release_info[2]}"
apk_path="${out_dir}/${apk_name}"

if [[ ! -f "${apk_path}" ]]; then
  curl -L --fail --output "${apk_path}" "${apk_url}"
fi

device_count="$(adb devices | awk 'NR>1 && $2=="device" {count++} END {print count+0}')"
if [[ "${device_count}" -lt 1 ]]; then
  echo "No authorized Android devices found." >&2
  exit 1
fi

adb install -r "${apk_path}"
echo "Installed AVNC ${tag}: ${apk_path}"
