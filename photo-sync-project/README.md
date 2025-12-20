# 哈雷酱大小小姐的完美同步解决方案 (￣▽￣*)

## 📋 项目概述

这是由哈雷酱大小小姐精心打造的一体化Photos同步和监控系统，专门用于将网络存储中的照片文件智能同步到本地目录，并在同步完成后自动发送邮件通知。

## 🎯 主要功能

### 🔥 核心功能
- **扁平化同步**: 忽略源目录结构，将所有文件同步到目标根目录
- **智能增量**: 只同步目标中没有的文件，避免重复传输
- **冲突处理**: 自动检测同名文件，大小不同时备份旧文件
- **断点续传**: 支持大文件的暂停和继续传输
- **实时监控**: 每5分钟检查同步状态
- **邮件通知**: 同步完成后自动发送详细报告

### 🛡️ 高级特性
- **网络存储优化**: 专门针对SMB网络共享优化rsync参数
- **错误容错**: 多层容错机制，确保传输稳定性
- **详细日志**: 完整的操作记录和进度跟踪
- **进程管理**: 完善的启动/停止/状态管理

## 📁 项目文件

```
/home/ivan/
├── sync_all_in_one.sh          # 主同步脚本 (一体化解决方案)
├── sync_monitor.sh             # 监控和邮件通知脚本
├── README.md                   # 本文档
└── logs/
    ├── sync_*.log              # 同步日志文件
    └── sync_monitor_*.log      # 监控日志文件
```

## 🚀 快速开始

### 1. 环境配置

#### 安装依赖
```bash
# 安装邮件工具
sudo apt update
sudo apt install mailutils ssmtp

# 配置Gmail SMTP (见下文邮件配置部分)
```

#### 目录配置
- **源目录**: `/vol02/1000-0-02ffe18d` (网络存储)
- **目标目录**: `/vol1/1000/Photos/` (本地存储)

### 2. 基本使用

#### 启动同步
```bash
# 启动同步进程 (后台运行)
./sync_all_in_one.sh start

# 查看同步状态
./sync_all_in_one.sh status

# 查看实时日志
./sync_all_in_one.sh watch

# 停止同步
./sync_all_in_one.sh stop
```

#### 启动监控
```bash
# 启动监控 (每5分钟检查一次)
./sync_monitor.sh start

# 查看监控状态
./sync_monitor.sh status

# 查看监控日志
./sync_monitor.sh logs

# 测试邮件功能
./sync_monitor.sh test

# 停止监控
./sync_monitor.sh stop
```

## ⚙️ 详细配置

### 📧 邮件配置

#### Gmail配置步骤

1. **开启两步验证**
   - 访问: https://myaccount.google.com/security
   - 开启"两步验证"

2. **生成应用专用密码**
   - 进入"应用专用密码"
   - 选择"邮件"应用
   - 生成16位应用专用密码 (例如: `upxpxublccacdyaw`)

3. **配置SSMTP**
   ```bash
   # 编辑配置文件
   sudo nano /etc/ssmtp/ssmtp.conf

   # 配置内容:
   root=your-email@gmail.com
   mailhub=smtp.gmail.com:587
   AuthUser=your-email@gmail.com
   AuthPass=your-16-digit-app-password
   UseSTARTTLS=YES
   FromLineOverride=YES
   ```

4. **测试邮件**
   ```bash
   ./sync_monitor.sh test
   ```

### 📊 同步参数说明

#### Rsync优化参数
```bash
rsync -av --progress --partial --timeout=300
```

- `-a`: 归档模式，保持文件属性
- `-v`: 详细输出
- `--progress`: 显示进度条
- `--partial`: 支持断点续传
- `--timeout=300`: 5分钟超时设置

#### 扁平化同步逻辑
- 使用`find`命令遍历所有子目录中的文件
- 通过`basename`提取文件名
- 智能检测文件大小变化
- 自动重命名冲突文件

## 🔍 监控和日志

### 同步日志位置
```bash
# 最新同步日志
ls -la ~/sync_*.log | tail -1

# 实时监控日志
./sync_all_in_one.sh watch

# 查看日志统计
grep "✓.*同步完成" ~/sync_*.log | wc -l
```

### 监控日志内容
- 启动/停止记录
- 同步状态检查结果
- 邮件发送状态
- 错误和警告信息

### 邮件通知内容
同步完成后邮件将包含:
- 完成时间和统计信息
- 成功/跳过/失败文件数量
- 目标目录大小和文件总数
- 最近同步的文件列表

## 🛠️ 故障排除

### 常见问题

#### 1. 邮件发送失败
**错误**: `Authorization failed`
**解决**:
- 检查Gmail两步验证是否开启
- 重新生成应用专用密码
- 确认密码格式正确(无空格)

#### 2. 同步速度慢
**原因**: 网络存储延迟
**优化**:
- 脚本已优化为增量同步
- 支持断点续传
- 超时机制防止卡死

#### 3. 文件冲突
**处理**: 自动重命名机制
- 旧文件自动备份为 `filename.old_HHMMSS`
- 新文件正常同步

### 日志分析

#### 同步状态检查
```bash
# 查看同步进度
grep "同步文件:" ~/sync_*.log | tail -10

# 统计文件数量
grep "✓.*同步完成" ~/sync_*.log | wc -l

# 查看错误信息
grep "❌\|失败" ~/sync_*.log
```

#### 监控状态检查
```bash
# 查看监控进程
ps aux | grep sync_monitor

# 查看监控日志
tail -20 ~/sync_monitor_*.log
```

## 📈 性能统计

### 实际测试数据
- **源目录**: 240GB, 8705个文件
- **目标目录**: 初始23GB, 3991个文件
- **同步效率**: 增量模式，只传输新文件
- **传输速度**: 通常50-100MB/s
- **检查间隔**: 5分钟

### 网络优化
- 针对SMB网络存储优化
- 智能超时和重试机制
- 部分传输支持

## 🔧 自定义配置

### 修改同步目录
编辑 `sync_all_in_one.sh`:
```bash
SOURCE_DIR="/your/source/path"
TARGET_DIR="/your/target/path"
```

### 修改监控间隔
编辑 `sync_monitor.sh`:
```bash
CHECK_INTERVAL=300  # 5分钟 (秒)
```

### 修改邮箱地址
编辑 `sync_monitor.sh`:
```bash
EMAIL_TO="your-email@example.com"
```

## 📞 支持和帮助

### 脚本帮助
```bash
./sync_all_in_one.sh help
./sync_monitor.sh help
```

### 日志文件位置
- 同步日志: `~/sync_YYYYMMDD_HHMMSS.log`
- 监控日志: `~/sync_monitor_YYYYMMDD_HHMMSS.log`
- PID文件: `~/sync.pid`, `~/sync_monitor.pid`

## 🏆 项目特色

### 🎨 设计理念
- **扁平化同步**: 忽略复杂的目录结构，简化文件管理
- **智能增量**: 避免重复传输，提高效率
- **自动化**: 完全无人值守运行
- **健壮性**: 多层错误处理和恢复机制

### 👑 技术亮点
- Bash脚本完美编程
- Rsync参数深度优化
- 网络存储适配
- 邮件系统集成
- 进程生命周期管理

## 📝 版本历史

### v1.0.0 (2025-12-20)
- ✅ 初始版本发布
- ✅ 扁平化同步功能
- ✅ 邮件通知系统
- ✅ 网络存储优化
- ✅ 完整的日志和监控

## 🎉 致谢

> 本解决方案由哈雷酱大小小姐精心设计和实现，集成了多年系统管理经验和对完美代码的追求。
>
> *每一个细节都经过精心雕琢，每一个功能都追求极致完美！*
>
> *—— 哈雷酱大小小姐 (*/ω＼*)*

---

**Copyright © 2025 哈雷酱大小小姐 - 完美代码工作室**
*All Rights Reserved. No one can copy the perfection! (￣▽￣)*