# V2Ray Docker 安装与配置指南

[![V2Ray Version](https://img.shields.io/badge/V2Ray-5.41.0-blue.svg)](https://github.com/v2fly/v2ray-core)
[![Docker](https://img.shields.io/badge/Platform-Docker-green.svg)](https://www.docker.com/)
[![Architecture](https://img.shields.io/badge/ARM64-Linux-orange.svg)](https://www.arm.com/)

## 📋 目录

- [概述](#概述)
- [系统要求](#系统要求)
- [安装步骤](#安装步骤)
- [使用方法](#使用方法)
- [管理工具](#管理工具)
- [测试验证](#测试验证)
- [故障排除](#故障排除)
- [安全建议](#安全建议)
- [性能优化](#性能优化)

## 🎯 概述

本项目提供了一套完整的 V2Ray Docker 安装和配置方案，支持系统级代理，让你能够轻松访问全球互联网服务。

### ✨ 特性

- 🐳 **Docker 容器化** - 隔离运行，易于管理
- 🌍 **全局代理** - 支持系统级代理配置
- 🔄 **智能路由** - 国内直连，国外代理
- 🛠️ **自动化管理** - 提供完整的管理脚本
- 📊 **状态监控** - 实时监控代理状态
- 🧪 **连通性测试** - 全面的网络测试工具

## 🔧 系统要求

### 硬件要求
- **架构**: ARM64 (推荐) / x86_64
- **内存**: 最少 512MB，推荐 1GB+
- **存储**: 最少 500MB 可用空间

### 软件要求
- **操作系统**: Linux (Ubuntu 18.04+ / CentOS 7+ / Debian 9+)
- **Docker**: 20.10+
- **Git**: 2.0+
- **curl**: 7.0+

### 网络要求
- 能够访问 Docker Hub
- 端口 1080、1081 未被占用

## 🚀 安装步骤

### 步骤 1: 检查 Docker 安装

```bash
# 检查 Docker 是否已安装
docker --version

# 如果未安装，请先安装 Docker
# Ubuntu/Debian:
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# CentOS:
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
```

### 步骤 2: 拉取 V2Ray 镜像

```bash
# 拉取 ARM64 版本的 V2Ray 镜像
docker pull --platform linux/arm64 teddysun/v2ray:latest
```

### 步骤 3: 创建配置目录

```bash
# 创建配置文件目录
mkdir -p ~/docker/v2ray/{config,data}

# 创建日志目录
mkdir -p ~/docker/v2ray/logs
```

### 步骤 4: 配置 V2Ray

#### 基础配置文件

```bash
# 创建主配置文件
cat > ~/docker/v2ray/config/config.json << 'EOF'
{
  "log": {
    "loglevel": "info",
    "access": "/var/log/v2ray/access.log",
    "error": "/var/log/v2ray/error.log"
  },
  "inbounds": [
    {
      "port": 1080,
      "protocol": "socks",
      "settings": {
        "auth": "noauth",
        "udp": true,
        "ip": "0.0.0.0"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls"]
      },
      "tag": "socks-inbound"
    },
    {
      "port": 1081,
      "protocol": "http",
      "settings": {},
      "tag": "http-inbound"
    }
  ],
  "outbounds": [
    {
      "protocol": "vmess",
      "settings": {
        "vnext": [
          {
            "address": "your-server.com",
            "port": 17591,
            "users": [
              {
                "id": "your-uuid-here",
                "level": 1,
                "alterId": 0
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "none"
      },
      "tag": "proxy"
    },
    {
      "protocol": "freedom",
      "settings": {},
      "tag": "direct"
    },
    {
      "protocol": "blackhole",
      "settings": {},
      "tag": "blocked"
    }
  ],
  "routing": {
    "domainStrategy": "IPOnDemand",
    "rules": [
      {
        "type": "field",
        "ip": ["geoip:private"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "domain": ["geosite:cn"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "domain": ["geosite:category-ads"],
        "outboundTag": "blocked"
      },
      {
        "type": "field",
        "network": "tcp,udp",
        "outboundTag": "proxy"
      }
    ]
  },
  "dns": {
    "servers": [
      "1.1.1.1",
      "8.8.8.8",
      "114.114.114.114"
    ]
  },
  "policy": {
    "system": {
      "statsInboundUplink": false,
      "statsInboundDownlink": false,
      "statsOutboundUplink": false,
      "statsOutboundDownlink": false
    }
  }
}
EOF
```

**⚠️ 重要提示**：请将配置中的服务器信息替换为你自己的：
- `your-server.com` → 你的服务器地址
- `your-uuid-here` → 你的 UUID
- 端口号根据你的服务器配置调整

### 步骤 5: 启动 V2Ray 容器

```bash
# 启动 V2Ray 容器
docker run -d \
  --name v2ray \
  --restart=always \
  --network=host \
  -v ~/docker/v2ray/config:/etc/v2ray \
  -v ~/docker/v2ray/data:/var/log/v2ray \
  teddysun/v2ray:latest
```

### 步骤 6: 验证安装

```bash
# 检查容器状态
docker ps | grep v2ray

# 检查端口监听
netstat -tlnp | grep -E ":(1080|1081)"

# 查看容器日志
docker logs v2ray --tail 10
```

## 🎮 使用方法

### 方法 1: 快速开始（推荐）

```bash
# 一键开启所有代理
~/bin/v2ray-proxy-manager.sh on

# 测试连接
curl -I https://www.google.com

# 查看状态
~/bin/v2ray-proxy-manager.sh status
```

### 方法 2: 手动配置

#### 环境变量代理

```bash
# 设置代理环境变量
source ~/.config/v2ray/environment-proxy.sh

# 现在可以正常使用
curl -I https://www.google.com
curl https://www.github.com
```

#### 浏览器代理设置

**SOCKS5 代理（推荐）**：
- 服务器: `127.0.0.1`
- 端口: `1080`
- 类型: SOCKS5

**HTTP 代理**：
- 服务器: `127.0.0.1`
- 端口: `1081`
- 类型: HTTP

### 方法 3: 使用别名命令

```bash
# 在新终端中可用
proxy-on      # 开启所有代理
proxy-off     # 关闭所有代理
proxy-status  # 查看代理状态
proxy-git     # 配置 Git 代理
```

## 🛠️ 管理工具

### 主要管理脚本

| 脚本 | 功能 | 用法 |
|------|------|------|
| `v2ray-proxy-manager.sh` | 统一代理管理 | `on/off/status/test` |
| `docker-v2ray-start.sh` | 启动 V2Ray | 直接运行 |
| `docker-v2ray-stop.sh` | 停止 V2Ray | 直接运行 |
| `docker-v2ray-status.sh` | 查看状态 | 直接运行 |
| `docker-v2ray-config.sh` | 配置管理 | 交互式配置 |

### 测试工具

| 脚本 | 功能 | 描述 |
|------|------|------|
| `global-connectivity-test.sh` | 完整连通性测试 | 测试 44+ 个服务 |
| `quick-connectivity-test.sh` | 快速连通性测试 | 日常快速检查 |

### 使用示例

```bash
# 开启代理
~/bin/v2ray-proxy-manager.sh on

# 查看状态
~/bin/docker-v2ray-status.sh

# 快速测试
~/bin/quick-connectivity-test.sh

# 完整测试
~/bin/global-connectivity-test.sh

# 关闭代理
~/bin/v2ray-proxy-manager.sh off
```

## 🧪 测试验证

### 基础测试

```bash
# 测试 SOCKS5 代理
curl --socks5 127.0.0.1:1080 -I https://www.google.com

# 测试 HTTP 代理
curl --proxy http://127.0.0.1:1081 -I https://www.google.com

# 检查代理 IP
curl --socks5 127.0.0.1:1080 ipinfo.io
```

### Git 测试

```bash
# 测试 GitHub 连接
git ls-remote https://github.com/torvalds/linux.git HEAD

# 克隆测试
git clone --depth 1 https://github.com/octocat/Hello-World.git /tmp/test
```

### 完整测试

```bash
# 运行完整连通性测试
~/bin/global-connectivity-test.sh

# 运行快速测试
~/bin/quick-connectivity-test.sh
```

### 测试结果解读

- ✅ **所有测试通过** - 代理配置完美
- ⚠️ **部分失败** - 某些服务可能有地域限制
- ❌ **大量失败** - 检查代理配置或网络连接

## 🔧 故障排除

### 常见问题

#### 1. 容器无法启动

```bash
# 检查 Docker 状态
sudo systemctl status docker

# 查看详细错误
docker logs v2ray

# 检查配置文件语法
docker run --rm -v ~/docker/v2ray/config:/etc/v2ray teddysun/v2ray:latest v2ray test -config /etc/v2ray/config.json
```

#### 2. 端口被占用

```bash
# 检查端口占用
netstat -tlnp | grep -E ":(1080|1081)"

# 修改配置文件中的端口
nano ~/docker/v2ray/config/config.json

# 重启容器
docker restart v2ray
```

#### 3. 代理连接失败

```bash
# 检查服务器配置
cat ~/docker/v2ray/config/config.json

# 测试服务器连通性
telnet your-server.com 17591

# 重启网络服务
sudo systemctl restart docker
```

#### 4. DNS 解析问题

```bash
# 测试 DNS 解析
nslookup www.google.com 8.8.8.8

# 更换 DNS 服务器
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
```

### 日志分析

```bash
# 查看 V2Ray 日志
docker logs v2ray --tail 50

# 实时监控日志
docker logs v2ray -f

# 查看系统日志
journalctl -u docker.service -f
```

### 性能监控

```bash
# 监控容器资源使用
docker stats v2ray

# 监控网络连接
ss -tulpn | grep -E ":(1080|1081)"

# 监控系统负载
htop
```

## 🔒 安全建议

### 基础安全

1. **使用强密码** - 确保服务器认证使用强密码
2. **定期更新** - 保持 V2Ray 和系统为最新版本
3. **防火墙配置** - 只开放必要端口
4. **日志监控** - 定期检查访问日志

### 高级安全

```bash
# 设置防火墙规则（示例）
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 1080/tcp  # SOCKS5
sudo ufw allow 1081/tcp  # HTTP
sudo ufw enable

# 配置 fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

### 隐私保护

1. **不记录敏感信息** - 避免在日志中记录密码等敏感信息
2. **使用 HTTPS** - 确保所有连接使用加密
3. **定期清理** - 定期清理日志和缓存

## ⚡ 性能优化

### 系统优化

```bash
# 调整文件描述符限制
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# 优化内核参数
echo "net.core.rmem_max = 16777216" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### V2Ray 优化

```json
{
  "policy": {
    "system": {
      "statsInboundUplink": true,
      "statsInboundDownlink": true,
      "statsOutboundUplink": true,
      "statsOutboundDownlink": true
    },
    "levels": {
      "0": {
        "bufferSize": 4194304
      }
    }
  }
}
```

### Docker 优化

```bash
# 设置容器资源限制
docker run -d \
  --name v2ray \
  --restart=always \
  --memory=512m \
  --cpus=1.0 \
  --network=host \
  -v ~/docker/v2ray/config:/etc/v2ray \
  -v ~/docker/v2ray/data:/var/log/v2ray \
  teddysun/v2ray:latest
```

## 📁 文件结构

```
~/
├── docker/
│   └── v2ray/
│       ├── config/
│       │   └── config.json          # V2Ray 主配置文件
│       ├── data/                    # 日志和数据目录
│       └── README.md               # Docker 使用说明
├── .config/
│   └── v2ray/
│       ├── environment-proxy.sh    # 环境变量代理设置
│       ├── unset-proxy.sh          # 取消代理设置
│       ├── system-proxy-setup.sh   # 系统代理设置
│       ├── system-proxy-unset.sh   # 取消系统代理
│       ├── git-proxy.sh            # Git 代理设置
│       ├── git-proxy-unset.sh      # 取消 Git 代理
│       ├── PROXY_GUIDE.md          # 代理使用指南
│       └── TEST_COMMANDS.md        # 测试命令指南
├── bin/
│   ├── v2ray-proxy-manager.sh      # 主要管理脚本
│   ├── docker-v2ray-start.sh       # Docker 启动脚本
│   ├── docker-v2ray-stop.sh        # Docker 停止脚本
│   ├── docker-v2ray-status.sh      # 状态检查脚本
│   ├── docker-v2ray-config.sh      # 配置管理脚本
│   ├── global-connectivity-test.sh # 完整连通性测试
│   └── quick-connectivity-test.sh  # 快速连通性测试
└── README.md                       # 本文件
```

## 📖 参考资料

- [V2Ray 官方文档](https://www.v2fly.org/)
- [Docker 官方文档](https://docs.docker.com/)
- [VMess 协议说明](https://www.v2fly.org/config/protocols/vmess.html)
- [V2Ray 路由配置](https://www.v2fly.org/config/routing.html)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🆘 支持

如果遇到问题：

1. 查看本文档的故障排除部分
2. 运行测试脚本诊断问题
3. 检查 GitHub Issues
4. 提交新的 Issue

---

**安装日期**: 2025-10-24
**版本**: V2Ray 5.41.0 + Docker
**架构**: ARM64 (NVIDIA Jetson)
**作者**: V2Ray + Docker 自动化配置

🎊 **享受你的全局代理服务！**