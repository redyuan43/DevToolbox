# 全局连通性测试命令指南

## 🎯 测试命令概览

### 1. 快速测试（推荐日常使用）
```bash
# 快速检查代理状态和基础连接
~/bin/quick-connectivity-test.sh
```

### 2. 完整测试
```bash
# 全面测试各类服务的连通性
~/bin/global-connectivity-test.sh
```

### 3. 代理状态检查
```bash
# 检查 V2Ray 服务状态
~/bin/docker-v2ray-status.sh

# 检查代理配置
~/bin/v2ray-proxy-manager.sh status
```

## 🧪 手动测试命令

### 基础连接测试
```bash
# 测试 Google
curl --socks5 127.0.0.1:1080 -I https://www.google.com

# 测试 GitHub
curl --socks5 127.0.0.1:1080 -I https://github.com

# 测试 YouTube
curl --socks5 127.0.0.1:1080 -I https://www.youtube.com

# 测试 Twitter
curl --socks5 127.0.0.1:1080 -I https://twitter.com
```

### IP 地址检测
```bash
# 检查代理 IP 地址
curl --socks5 127.0.0.1:1080 ipinfo.io

# 检查地理位置信息
curl --socks5 127.0.0.1:1080 ipinfo.io/json

# 检查纯 IP
curl --socks5 127.0.0.1:1080 ipinfo.io/ip
```

### HTTP 代理测试
```bash
# 使用 HTTP 代理测试
curl --proxy http://127.0.0.1:1081 -I https://www.google.com

# 测试 HTTP 协议
curl --proxy http://127.0.0.1:1081 http://httpbin.org/ip
```

### 速度测试
```bash
# 测试连接速度（简单版）
time curl --socks5 127.0.0.1:1080 https://www.google.com -o /dev/null

# 详细速度测试
curl --socks5 127.0.0.1:1080 -w "
  DNS 解析时间: %{time_namelookup}s
  连接时间: %{time_connect}s
  TLS 握手时间: %{time_appconnect}s
  首字节时间: %{time_starttransfer}s
  总时间: %{time_total}s
  HTTP 状态: %{http_code}
" https://www.google.com -o /dev/null
```

### Git 连接测试
```bash
# 测试 GitHub 连接
git ls-remote https://github.com/torvalds/linux.git HEAD

# 测试 GitLab 连接
git ls-remote https://gitlab.com/gitlab-org/gitlab-foss.git HEAD

# 克隆测试（浅克隆）
git clone --depth 1 https://github.com/octocat/Hello-World.git /tmp/test-repo
```

### DNS 解析测试
```bash
# 使用公共 DNS 测试
nslookup www.google.com 8.8.8.8

# 使用代理 DNS 测试
host www.google.com 1.1.1.1

# 测试 DNS 解析速度
dig @8.8.8.8 www.google.com | grep "Query time"
```

### 流媒体测试
```bash
# YouTube API 测试
curl --socks5 127.0.0.1:1080 https://www.youtube.com/api

# Netflix 主页测试
curl --socks5 127.0.0.1:1080 -I https://www.netflix.com

# Spotify 测试
curl --socks5 127.0.0.1:1080 -I https://www.spotify.com
```

### 社交媒体测试
```bash
# Facebook 测试
curl --socks5 127.0.0.1:1080 -I https://www.facebook.com

# Twitter 测试
curl --socks5 127.0.0.1:1080 -I https://twitter.com

# Instagram 测试
curl --socks5 127.0.0.1:1080 -I https://www.instagram.com

# LinkedIn 测试
curl --socks5 127.0.0.1:1080 -I https://www.linkedin.com
```

### 新闻网站测试
```bash
# BBC 新闻
curl --socks5 127.0.0.1:1080 -I https://www.bbc.com/news

# CNN
curl --socks5 127.0.0.1:1080 -I https://www.cnn.com

# Wikipedia
curl --socks5 127.0.0.1:1080 -I https://en.wikipedia.org
```

## 🔍 问题诊断命令

### 网络连通性诊断
```bash
# 检查端口监听
netstat -tlnp | grep -E ":(1080|1081)"

# 检查 V2Ray 容器状态
docker ps | grep v2ray

# 查看 V2Ray 日志
docker logs v2ray --tail 20
```

### 代理配置诊断
```bash
# 检查环境变量
echo $http_proxy
echo $https_proxy
echo $ALL_PROXY

# 检查 Git 代理配置
git config --global --get-regexp proxy

# 检查系统代理（GNOME）
gsettings get org.gnome.system.proxy mode
gsettings get org.gnome.system.proxy.socks
```

### 性能监控
```bash
# 监控 V2Ray 容器资源使用
docker stats v2ray

# 监控网络连接
ss -tulpn | grep -E ":(1080|1081)"

# 监控 DNS 解析
tcpdump -i any port 53
```

## 📊 测试脚本使用说明

### 快速测试脚本特点
- ✅ 快速检查代理状态
- ✅ 基础服务连通性测试
- ✅ 简单的速度测试
- ✅ Git 连接验证
- ✅ 环境变量检查

### 完整测试脚本特点
- ✅ 6 大类服务测试
- ✅ 44+ 个网站测试
- ✅ 详细的测试报告
- ✅ 彩色输出显示
- ✅ 失败原因分析

## 🎮 推荐测试流程

### 日常快速检查
```bash
# 1. 快速状态检查
~/bin/quick-connectivity-test.sh

# 2. 如果有疑问，运行完整测试
~/bin/global-connectivity-test.sh

# 3. 检查代理配置
~/bin/v2ray-proxy-manager.sh status
```

### 深度问题排查
```bash
# 1. 检查容器状态
docker ps | grep v2ray
docker logs v2ray --tail 50

# 2. 检查网络连接
netstat -tlnp | grep -E ":(1080|1081)"

# 3. 手动测试关键服务
curl --socks5 127.0.0.1:1080 ipinfo.io
curl --socks5 127.0.0.1:1080 -I https://www.google.com

# 4. 检查配置文件
cat ~/docker/v2ray/config/config.json
```

## 💡 测试技巧

### 1. 使用 `-I` 参数进行快速检查
```bash
# 只获取 HTTP 头部，速度快
curl --socks5 127.0.0.1:1080 -I https://example.com
```

### 2. 使用 `--max-time` 避免长时间等待
```bash
# 设置超时时间
curl --socks5 127.0.0.1:1080 --max-time 10 https://example.com
```

### 3. 使用 `-w` 参数获取详细信息
```bash
# 获取详细的连接时间信息
curl --socks5 127.0.0.1:1080 -w "%{time_total}s" -o /dev/null https://example.com
```

### 4. 组合命令进行批量测试
```bash
# 批量测试多个网站
for site in google.com github.com youtube.com; do
    echo -n "$site: "
    curl --socks5 127.0.0.1:1080 --max-time 5 -I "https://$site" | head -1
done
```

---

*测试指南版本: 1.0*
*更新日期: $(date +%Y-%m-%d)*

🎯 **定期运行测试确保代理正常工作！**