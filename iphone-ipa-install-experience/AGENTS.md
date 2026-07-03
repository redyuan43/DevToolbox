# Ubuntu 下给 iPhone 安装 IPA 的本机经验记录

## 目标

在 Ubuntu/Linux 环境下，把 `.ipa` 应用安装到已连接的 iPhone。

本次实测目标文件：

```bash
"/media/ivan/44A2C0D9A2C0D11A/home_ivan_offload/Documents/xwechat_files/redyuan43_9120/msg/file/2026-07/PhotoSyncApp.ipa"
```

本次实测设备：

```text
DeviceName: Ivan-iPhone
UDID: 00008130-001271812608001C
```

本次实际安装成功的 App：

```text
Bundle ID: com.hubin.h.PhotoSyncApp
Display Name: PhotoSyncApp
Bundle Version: 2
```

最终安装方式：

```text
直接使用 ideviceinstaller 安装已签名 IPA。
本次没有通过 iloader/SideStore 安装 PhotoSyncApp。
```

## 关键结论

Linux 下给 iPhone 安装 IPA，先判断 IPA 是否已经签名，并且是否授权给当前 iPhone。

如果 IPA 已经包含当前 iPhone 的 UDID，并且签名/profile 有效，可以直接用：

```bash
ideviceinstaller -i "/path/to/app.ipa"
```

如果 IPA 没有有效签名，或者 profile 不包含当前 iPhone，需要用 SideStore、AltStore、Sideloadly 或 Apple Developer 证书重新签名后再安装。

本次 `PhotoSyncApp.ipa` 属于 Ad Hoc 签名包，`embedded.mobileprovision` 中明确包含当前 iPhone 的 UDID，所以直接安装成功。

## 本次已验证环境

系统架构：

```bash
uname -m
```

结果：

```text
x86_64
```

Ubuntu 已安装并验证可用的基础工具：

```bash
sudo apt update
sudo apt install -y libimobiledevice-utils ideviceinstaller usbmuxd
```

已验证命令：

```bash
command -v usbmuxd
command -v idevice_id
command -v idevicepair
command -v ideviceinstaller
command -v plutil
```

核心服务状态：

```bash
systemctl is-active usbmuxd
```

本次结果：

```text
active
```

## iPhone 连接检查

连接 iPhone 后，先确认 USB 层是否识别到 Apple 设备：

```bash
lsusb
```

本次识别结果中出现：

```text
ID 05ac:12a8 Apple, Inc. iPhone 5/5C/5S/6/SE/7/8/X/XR
```

如果 `lsusb` 中没有 Apple/iPhone：

1. 解锁 iPhone，保持在主屏幕。
2. 更换支持数据传输的 USB 线。
3. 尽量直连主机 USB 口，少用扩展坞。
4. 手机弹出“信任此电脑”时选择信任。

检查 libimobiledevice 是否能读到设备：

```bash
idevice_id -l
```

本次结果：

```text
00008130-001271812608001C
```

验证配对：

```bash
idevicepair validate
```

本次结果：

```text
SUCCESS: Validated pairing with device 00008130-001271812608001C
```

如果未配对，可以执行：

```bash
idevicepair pair
```

执行时 iPhone 必须解锁，并在手机上点“信任此电脑”。

## 签名概念速记

iPhone 安装 IPA 时不只是复制文件，还会验证签名、证书和 provisioning profile。

一个可安装的 IPA 通常需要满足：

1. App 二进制有有效代码签名。
2. IPA 内含有效的 `embedded.mobileprovision`。
3. profile 未过期。
4. profile 的 `ProvisionedDevices` 包含当前 iPhone 的 UDID，或者属于其他允许分发的签名类型。
5. Bundle ID、entitlements、证书链匹配。

常见失败关键词：

```text
ApplicationVerificationFailed
A valid provisioning profile for this executable was not found
The executable was signed with invalid entitlements
```

出现这些通常表示签名、profile、UDID 或证书不匹配。

## 判断 IPA 是否适合直接安装

先看 IPA 内部结构：

```bash
unzip -l "/path/to/app.ipa" | rg "Info.plist|embedded.mobileprovision|_CodeSignature|Payload/[^/]+\\.app/$"
```

本次 `PhotoSyncApp.ipa` 检查结果包含：

```text
Payload/PhotoSyncApp.app/
Payload/PhotoSyncApp.app/_CodeSignature/
Payload/PhotoSyncApp.app/_CodeSignature/CodeResources
Payload/PhotoSyncApp.app/embedded.mobileprovision
Payload/PhotoSyncApp.app/Info.plist
```

这说明 IPA 内部至少有签名目录和 provisioning profile。

注意：有 `_CodeSignature` 和 `embedded.mobileprovision` 不代表一定能装。还需要检查 profile 是否包含当前设备 UDID、是否过期。

## 读取 IPA 元数据

使用临时目录解包读取，不修改原 IPA：

```bash
tmpdir="$(mktemp -d)"
unzip -q "/path/to/app.ipa" \
  "Payload/PhotoSyncApp.app/Info.plist" \
  "Payload/PhotoSyncApp.app/embedded.mobileprovision" \
  -d "$tmpdir"

plutil -p "$tmpdir/Payload/PhotoSyncApp.app/Info.plist" | \
  rg "CFBundleIdentifier|CFBundleDisplayName|CFBundleName|CFBundleShortVersionString|CFBundleVersion|MinimumOSVersion"

openssl smime -inform der -verify -noverify \
  -in "$tmpdir/Payload/PhotoSyncApp.app/embedded.mobileprovision" 2>/dev/null | \
  plutil -p - | \
  rg "Name|TeamName|ApplicationIdentifierPrefix|ExpirationDate|ProvisionedDevices|application-identifier|get-task-allow|00008130-001271812608001C"

rm -rf "$tmpdir"
```

本次关键输出：

```text
AppIDName = PhotoSyncApp;
ApplicationIdentifierPrefix = (
"application-identifier" = "KWAT7HPTLT.com.hubin.h.PhotoSyncApp";
"get-task-allow" = <*BN>;
ExpirationDate = <*D2027-06-03 00:51:35 +0000>;
Name = "iOS Team Ad Hoc Provisioning Profile: com.hubin.h.PhotoSyncApp";
ProvisionedDevices = (
"00008130-001271812608001C",
TeamName = "Shenzhen Wingto Digital Technology Co., Ltd.";
```

判断：

1. profile 名称包含 `Ad Hoc Provisioning Profile`。
2. `ProvisionedDevices` 包含当前 iPhone UDID：`00008130-001271812608001C`。
3. 过期时间为 `2027-06-03 00:51:35 +0000`，本次安装时仍有效。
4. 因此该 IPA 可以直接安装到当前 iPhone。

## 直接安装已签名 IPA

安装命令：

```bash
ideviceinstaller -i "/media/ivan/44A2C0D9A2C0D11A/home_ivan_offload/Documents/xwechat_files/redyuan43_9120/msg/file/2026-07/PhotoSyncApp.ipa"
```

本次安装输出：

```text
WARNING: could not locate iTunesMetadata.plist in archive!
WARNING: could not locate Payload/PhotoSyncApp.app/SC_Info/PhotoSyncApp.sinf in archive!
Copying '/media/ivan/44A2C0D9A2C0D11A/home_ivan_offload/Documents/xwechat_files/redyuan43_9120/msg/file/2026-07/PhotoSyncApp.ipa' to device... DONE.
Installing 'com.hubin.h.PhotoSyncApp'
Install: GeneratingApplicationMap (90%)
Install: InstallComplete (100%)
Install: Complete
```

两个 warning 可以忽略：

```text
could not locate iTunesMetadata.plist
could not locate Payload/.../SC_Info/...sinf
```

这类文件常见于 App Store 分发包。本次是 Ad Hoc 包，没有它们不影响安装。

## 安装后验证

查询手机已安装应用：

```bash
timeout 15s ideviceinstaller -l 2>&1 | rg -i "PhotoSyncApp|com\\.hubin\\.h\\.PhotoSyncApp|CFBundleIdentifier|ERROR" || true
```

本次验证结果：

```text
CFBundleIdentifier, CFBundleVersion, CFBundleDisplayName
com.hubin.h.PhotoSyncApp, "2", "PhotoSyncApp"
```

这表示 App 已安装到 iPhone。

## 关于 SideStore 和 iloader

本次曾先安装 SideStore，因为一开始不确定 IPA 是否已经签名并授权给当前设备。

`iloader` 下载位置：

```bash
"/home/ivan/Desktop/iloader-linux-amd64.AppImage"
```

本次使用版本：

```text
iloader v2.2.6
```

下载来源：

```text
https://github.com/nab138/iloader/releases/download/v2.2.6/iloader-linux-amd64.AppImage
```

启动命令：

```bash
"/home/ivan/Desktop/iloader-linux-amd64.AppImage"
```

启动时出现过 GTK/GVFS 警告：

```text
/usr/lib/x86_64-linux-gnu/gvfs/libgvfscommon.so: undefined symbol: g_task_set_static_name
Failed to load module: /usr/lib/x86_64-linux-gnu/gio/modules/libgvfsdbus.so
```

该警告没有阻止 `iloader` 图形界面运行。

检查 `iloader` 是否运行：

```bash
pgrep -af "iloader-linux-amd64|iloader" || true
```

本次安装 SideStore 后，应用列表中出现：

```text
com.SideStore.SideStore.3A7AYBCA29, "0603", "SideStore"
```

结论：

```text
SideStore 已经成功装到手机上。
但 PhotoSyncApp 不是通过 SideStore 安装的，而是通过 ideviceinstaller 直接安装的。
```

## iloader 登录 Apple ID 报错经验

曾出现报错：

```text
Failed to log in to Apple ID
GrandSlam error during proof login request
Auth error -22406: Enter the correct password for this Apple Account.
```

判断：

```text
这是 Apple ID 登录失败，不是 USB、Ubuntu、usbmuxd 或 iPhone 连接问题。
```

处理建议：

1. 确认输入的是 Apple ID 邮箱，不是手机号备注名。
2. 确认密码是 Apple ID 密码，不是 iPhone 解锁密码或邮箱密码。
3. Apple Account 可能区分大小写，账号大小写尽量保持和注册时一致。
4. 先去 `https://account.apple.com/` 网页登录验证。
5. 新注册 Apple ID 需要先完成条款、安全信息、双重认证等流程。
6. 不建议使用主 Apple ID，建议使用专门侧载的小号。

本次最终 Apple ID 登录成功，并成功安装 SideStore。

## 什么时候用 ideviceinstaller，什么时候用 SideStore

优先级：

1. 如果 IPA 已经签名，并且 profile 包含当前 iPhone UDID：直接用 `ideviceinstaller`。
2. 如果 IPA 没签名，或 profile 不包含当前设备：用 SideStore/AltStore/Sideloadly 重新签名。
3. 如果想最少折腾，并且可用 Windows/macOS：可考虑 Sideloadly 或爱思助手类工具。

已签名且授权给当前设备的判断依据：

```text
embedded.mobileprovision 存在
_CodeSignature 存在
ProvisionedDevices 包含当前 idevice_id -l 读出的 UDID
ExpirationDate 未过期
Bundle ID 与 application-identifier 对得上
```

本次满足这些条件，所以直接安装最简单、成功率最高。

## 常用命令速查

检查设备：

```bash
lsusb
idevice_id -l
idevicepair validate
ideviceinfo -k DeviceName
ideviceinfo -k ProductVersion
```

安装依赖：

```bash
sudo apt update
sudo apt install -y libimobiledevice-utils ideviceinstaller usbmuxd
```

安装 IPA：

```bash
ideviceinstaller -i "/path/to/app.ipa"
```

列出已安装 App：

```bash
timeout 15s ideviceinstaller -l
```

按关键词查找 App：

```bash
timeout 15s ideviceinstaller -l 2>&1 | rg -i "PhotoSyncApp|com\\.hubin\\.h\\.PhotoSyncApp|SideStore|ERROR" || true
```

卸载 App：

```bash
ideviceinstaller -U "com.hubin.h.PhotoSyncApp"
```

注意：卸载属于破坏性操作，执行前应明确确认。

## 操作注意事项

1. 所有路径使用双引号包裹，避免空格或特殊字符导致命令失败。
2. 优先使用 `rg` 查询文本，速度快且输出清晰。
3. `ideviceinstaller -l` 在某些情况下可能卡住，建议配合 `timeout 15s` 使用。
4. 安装期间不要反复插拔数据线。
5. iPhone 尽量保持解锁。
6. 如果手机提示信任电脑、信任开发者、开启开发者模式，需要在手机端确认。
7. 对已签名 Ad Hoc IPA，直接安装通常比 SideStore 重新签名更稳。
8. 不要把 Apple ID 密码写入日志、文档或聊天记录。

## 本次完整状态总结

本机 Ubuntu 已具备 iPhone IPA 安装基础能力：

```text
usbmuxd 可用
libimobiledevice-utils 可用
ideviceinstaller 可用
iPhone 配对成功
SideStore 已安装到 iPhone
PhotoSyncApp 已直接安装到 iPhone
```

`PhotoSyncApp.ipa` 的关键签名信息：

```text
Bundle ID: com.hubin.h.PhotoSyncApp
Provisioning type: Ad Hoc
Provisioned device: 00008130-001271812608001C
TeamName: Shenzhen Wingto Digital Technology Co., Ltd.
ExpirationDate: 2027-06-03 00:51:35 +0000
```

安装成功确认：

```text
com.hubin.h.PhotoSyncApp, "2", "PhotoSyncApp"
```

