好，我直接给你一套**“可落地的连接方案”**，从插线到能看到画面，一步步来，不讲虚的。

---

# ✅ 最终目标

```text
Ubuntu（Sunshine） ⇄ USB线 ⇄ Android（Moonlight）
```

实现：
👉 安卓平板当“副屏”（通过视频流）

---

# 🧩 一、物理连接

1️⃣ 用 USB 线连接：

```text
Ubuntu电脑 ⇄ 安卓平板
```

---

# 🧩 二、把 USB 变成“网线”（关键步骤）

在安卓平板：

```text
设置 → 网络共享 → USB网络共享（USB tethering） → 打开
```

---

在 Ubuntu 检查：

```bash
ip a
```

你应该看到：

```text
usb0
```

以及一个 IP，比如：

```text
192.168.42.129
```

👉 记住这个 IP（后面用）

---

# 🧩 三、Ubuntu 安装 Sunshine

👉 Sunshine

### 安装：

```bash
wget https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-22.04-amd64.deb
sudo apt install ./sunshine-ubuntu-22.04-amd64.deb
```

---

### 启动：

```bash
systemctl --user start sunshine
```

---

### 打开配置页面：

浏览器访问：

```text
http://localhost:47990
```

设置账号密码

---

# 🧩 四、安卓安装客户端

👉 Moonlight Game Streaming

---

# 🧩 五、建立连接（重点）

打开 Moonlight：

1️⃣ 点击 “Add PC / 手动添加”
2️⃣ 输入 Ubuntu 的 USB IP：

```text
192.168.42.xxx
```

3️⃣ 点击连接
4️⃣ Ubuntu 上会弹出配对码
5️⃣ 输入完成配对

---

# 🧩 六、测试连接

连接后：

👉 选择：

```text
Desktop
```

你应该看到：

```text
Ubuntu桌面 → 出现在安卓平板上
```

---

# 🧩 七（升级）：只推“副屏”（强烈建议）

## 1️⃣ 创建虚拟显示器（推荐方式）

👉 最简单：

👉 买一个 **HDMI 假头（dummy plug）**

插上后：

```bash
xrandr
```

会看到第二个屏幕：

```text
HDMI-2 connected
```

---

## 2️⃣ 设置副屏布局

```bash
xrandr --output HDMI-2 --right-of HDMI-1
```

---

## 3️⃣ 在 Sunshine 中选择这个屏幕

设置：

```text
Capture Display → HDMI-2
```

👉 这样：

```text
主屏 → 你用
副屏 → 推给平板
```

---

# 🧩 八、性能调优（直接抄）

在 Sunshine 设置里：

```text
分辨率：1920x1080
FPS：60
码率：15~25 Mbps（USB够用）
编码：
  NVIDIA → NVENC
  Intel/AMD → VAAPI
```

---

# 🧩 九、完整链路（你现在的系统）

```text
[Ubuntu]
  ├─ 虚拟副屏（HDMI假头）
  ├─ Sunshine（编码）
        ↓
  USB网络（usb0）
        ↓
[Android]
  └─ Moonlight（解码显示）
```

---

# 🚨 常见问题（直接帮你排坑）

### ❌ Moonlight 找不到设备

👉 用手动 IP：

```text
192.168.42.xxx
```

---

### ❌ 黑屏

原因：

* 没有显示器（👉 用 HDMI假头）
* Wayland 问题

👉 解决：

```text
登录时选择：Ubuntu on Xorg
```

---

### ❌ 卡顿

👉 调整：

```text
码率 ↓
分辨率 ↓
```

---

# 🔥 一句话总结

> **USB tethering = 有线网络
> Sunshine = 视频服务器
> Moonlight = 副屏显示器**

---

# 🚀 如果你下一步要升级

我可以帮你直接做：

* ✅ 自动识别 USB 插入 → 自动启动 Sunshine
* ✅ 自动创建虚拟副屏
* ✅ 平板一插即用

👉 这一步做完，你就已经有一个**AI 多屏控制台系统**了。

