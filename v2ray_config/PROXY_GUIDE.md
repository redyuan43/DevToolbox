# 系统代理配置指南

## 🎯 概述

本指南帮你配置系统级的 V2Ray 代理，让你的电脑所有连接都能走代理。

## 🚀 快速开始

### 1. 一键开启所有代理
```bash
~/bin/v2ray-proxy-manager.sh on
```

### 2. 一键关闭所有代理
```bash
~/bin/v2ray-proxy-manager.sh off
```

### 3. 查看代理状态
```bash
~/bin/v2ray-proxy-manager.sh status
```

### 4. 测试代理连接
```bash
~/bin/v2ray-proxy-manager.sh test
```

## 🔧 详细配置

### 环境变量代理

**设置代理环境变量：**
```bash
source ~/.config/v2ray/environment-proxy.sh
```

**取消代理环境变量：**
```bash
source ~/.config/v2ray/unset-proxy.sh
```

### Git 代理

**设置 Git 代理：**
```bash
source ~/.config/v2ray/git-proxy.sh
```

**取消 Git 代理：**
```bash
source ~/.config/v2ray/git-proxy-unset.sh
```

### Docker 代理

Docker 代理配置在 `~/.docker/config.json` 中，自动生效。

## 📱 终端快捷别名

在新终端中可使用以下快捷命令：

```bash
proxy-on      # 开启所有代理
proxy-off     # 关闭所有代理
proxy-status  # 查看代理状态
proxy-git     # 配置 Git 代理
proxy-env     # 设置环境变量代理
proxy-unset   # 取消环境变量代理
```

## 🌐 手动浏览器配置

如果系统代理配置不生效，可以手动配置浏览器：

### Chrome/Firefox
1. 设置 → 网络设置
2. 配置代理：
   - SOCKS5 代理：`127.0.0.1:1080`
   - HTTP 代理：`127.0.0.1:1081`

### SwitchyOmega 插件
- **情景模式**：代理服务器
- **代理协议**：SOCKS5
- **服务器**：127.0.0.1
- **端口**：1080

## 🔄 不同使用场景

### 1. 临时使用（推荐）
```bash
# 仅在当前终端生效
source ~/.config/v2ray/environment-proxy.sh

# 测试连接
curl https://www.google.com

# 运行需要代理的程序
./some-app
```

### 2. 永久使用
```bash
# 开启所有代理（包括 Git、Docker 等）
~/bin/v2ray-proxy-manager.sh on

# 新开终端会话自动生效
```

### 3. 选择性代理
```bash
# 仅 Git 走代理
~/bin/v2ray-proxy-manager.sh git

# 仅环境变量走代理
~/bin/v2ray-proxy-manager.sh env
```

## 🧪 测试代理是否工作

### 1. 测试命令行
```bash
# 检查 IP 地址
curl ipinfo.io

# 测试 Google 连接
curl -I https://www.google.com

# 测试 HTTPS 请求
curl https://httpbin.org/ip
```

### 2. 测试 Git
```bash
git ls-remote https://github.com/torvalds/linux.git HEAD
```

### 3. 测试 Docker
```bash
docker pull alpine:latest
```

## 📁 配置文件位置

- **主配置**: `~/docker/v2ray/config/config.json`
- **环境变量脚本**: `~/.config/v2ray/environment-proxy.sh`
- **Git 代理脚本**: `~/.config/v2ray/git-proxy.sh`
- **Docker 代理配置**: `~/.docker/config.json`
- **管理器脚本**: `~/bin/v2ray-proxy-manager.sh`

## 🔍 故障排除

### 代理不工作？
1. 检查 V2Ray 容器状态：
   ```bash
   ~/bin/docker-v2ray-status.sh
   ```

2. 重启 V2Ray 容器：
   ```bash
   docker restart v2ray
   ```

3. 检查代理配置：
   ```bash
   ~/bin/v2ray-proxy-manager.sh status
   ```

### 某些应用不走代理？
1. 检查应用是否有自己的代理设置
2. 尝试使用 HTTP 代理：`127.0.0.1:1081`
3. 重启应用让代理设置生效

### 速度慢？
1. 检查代理服务器连接质量
2. 尝试更换传输协议（TCP/WebSocket）
3. 检查本地网络连接

## 🎮 智能路由规则

当前配置的智能路由：
- **中国大陆 IP** → 直连
- **中国大陆域名** → 直连
- **本地网络** → 直连
- **其他所有流量** → 通过 V2Ray 代理

## 🛡️ 安全建议

1. **仅在可信网络使用代理**
2. **定期更新 V2Ray 版本**
3. **检查代理服务器证书**
4. **避免在不安全网络上输入敏感信息**

## 📞 技术支持

如遇问题：
1. 检查日志：`docker logs v2ray`
2. 查看状态：`~/bin/v2ray-proxy-manager.sh status`
3. 测试连接：`~/bin/v2ray-proxy-manager.sh test`

---

*配置版本: 1.0*
*更新日期: $(date +%Y-%m-%d)*
*V2Ray 版本: 5.41.0*

🎊 **享受你的全局代理服务！**