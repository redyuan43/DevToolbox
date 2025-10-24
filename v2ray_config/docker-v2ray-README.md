# Docker V2Ray 安装使用指南

## 🎉 安装完成！

V2Ray 已成功通过 Docker 安装并运行在你的系统上。

### 📊 当前状态

- ✅ **V2Ray 版本**: 5.41.0
- ✅ **架构**: ARM64 (完美适配你的系统)
- ✅ **运行状态**: 正在运行
- ✅ **代理端口**: 1080 (SOCKS5), 1081 (HTTP)

## 🔧 快速使用

### 基础管理命令

```bash
# 查看状态
~/bin/docker-v2ray-status.sh

# 启动 V2Ray
~/bin/docker-v2ray-start.sh

# 停止 V2Ray
~/bin/docker-v2ray-stop.sh

# 配置管理
~/bin/docker-v2ray-config.sh
```

### Docker 原生命令

```bash
# 查看容器状态
docker ps | grep v2ray

# 查看日志
docker logs v2ray --tail 20 -f

# 重启容器
docker restart v2ray

# 进入容器
docker exec -it v2ray sh
```

## 🌐 代理配置

### SOCKS5 代理 (推荐)
- **地址**: `127.0.0.1`
- **端口**: `1080`
- **类型**: SOCKS5

### HTTP 代理
- **地址**: `127.0.0.1`
- **端口**: `1081`
- **类型**: HTTP

## 📱 使用方法

### 浏览器配置 (推荐使用插件)
1. **Firefox**: 安装 FoxyProxy 或 SwitchyOmega
2. **Chrome**: 安装 SwitchyOmega
3. **配置代理**: `127.0.0.1:1080` (SOCKS5)

### 系统代理设置
```bash
# 设置环境变量
export ALL_PROXY=socks5://127.0.0.1:1080
export HTTP_PROXY=socks5://127.0.0.1:1080
export HTTPS_PROXY=socks5://127.0.0.1:1080

# 取消代理设置
unset ALL_PROXY HTTP_PROXY HTTPS_PROXY
```

### 测试代理
```bash
# 测试 SOCKS5 代理
curl --socks5 127.0.0.1:1080 https://httpbin.org/ip

# 测试 HTTP 代理
curl --proxy http://127.0.0.1:1081 https://httpbin.org/ip

# 检查当前 IP
curl ipinfo.io
```

## 📁 文件结构

```
~/docker/v2ray/
├── config/
│   └── config.json          # V2Ray 主配置文件
├── data/                    # 日志文件目录
│   ├── access.log          # 访问日志
│   └── error.log           # 错误日志
└── README.md               # 本文档

~/bin/
├── docker-v2ray-start.sh   # 启动脚本
├── docker-v2ray-stop.sh    # 停止脚本
├── docker-v2ray-status.sh  # 状态检查脚本
└── docker-v2ray-config.sh  # 配置管理脚本
```

## ⚙️ 配置说明

当前配置为 **直连模式** (Direct Connection)，主要用于：
- 本地 SOCKS5/HTTP 代理
- 作为其他代理客户端的转发节点

### 配置远程服务器

如需连接到远程 V2Ray 服务器，修改配置文件：

```bash
# 方法1: 使用配置管理脚本
~/bin/docker-v2ray-config.sh

# 方法2: 直接编辑配置文件
nano ~/docker/v2ray/config/config.json
```

#### VMess 服务器配置示例
```json
{
  "outbounds": [
    {
      "protocol": "vmess",
      "settings": {
        "vnext": [
          {
            "address": "your-server.com",
            "port": 443,
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
        "network": "ws",
        "security": "tls",
        "wsSettings": {
          "path": "/your-path"
        }
      }
    }
  ]
}
```

## 🔍 故障排除

### 容器无法启动
```bash
# 查看详细错误
docker logs v2ray

# 检查配置文件语法
docker run --rm -v ~/docker/v2ray/config:/etc/v2ray teddysun/v2ray:latest v2ray test -config /etc/v2ray/config.json
```

### 端口冲突
```bash
# 检查端口占用
netstat -tlnp | grep -E ":(1080|1081)"
ss -tlnp | grep -E ":(1080|1081)"

# 修改配置文件中的端口号
nano ~/docker/v2ray/config/config.json
```

### 重置安装
```bash
# 停止并删除容器
docker stop v2ray && docker rm v2ray

# 重新创建容器
~/bin/docker-v2ray-start.sh
```

## 🚀 高级用法

### 自定义网络
```bash
# 创建自定义网络
docker network create v2ray-net

# 使用自定义网络启动
docker run -d \
  --name v2ray \
  --network v2ray-net \
  -p 1080:1080 \
  -p 1081:1081 \
  -v ~/docker/v2ray/config:/etc/v2ray \
  -v ~/docker/v2ray/data:/var/log/v2ray \
  teddysun/v2ray:latest
```

### 数据持久化
```bash
# 添加更多挂载点
docker run -d \
  --name v2ray \
  --network=host \
  -v ~/docker/v2ray/config:/etc/v2ray \
  -v ~/docker/v2ray/data:/var/log/v2ray \
  -v ~/docker/v2ray/logs:/app/logs \
  teddysun/v2ray:latest
```

## 📝 更新和维护

### 更新 V2Ray 镜像
```bash
# 拉取最新镜像
docker pull teddysun/v2ray:latest

# 重新创建容器
docker stop v2ray && docker rm v2ray
~/bin/docker-v2ray-start.sh
```

### 备份配置
```bash
# 备份整个配置目录
cp -r ~/docker/v2ray ~/docker/v2ray.backup.$(date +%Y%m%d)

# 只备份配置文件
cp ~/docker/v2ray/config/config.json ~/docker/v2ray.config.backup.$(date +%Y%m%d)
```

## 📞 参考资源

- [V2Ray 官方文档](https://www.v2fly.org/)
- [Docker V2Ray 镜像](https://hub.docker.com/r/teddysun/v2ray)
- [V2Ray 配置生成器](https://config.v2fly.org/)

---

*安装日期: $(date +%Y-%m-%d)*
*版本: V2Ray 5.41.0 + Docker*
*架构: ARM64 (NVIDIA Jetson)*

🎊 **享受你的 V2Ray 代理服务！**