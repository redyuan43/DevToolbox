# 📧 邮件配置详细指南

## 概述

本文档详细说明如何为哈雷酱大小小姐的Photos同步项目配置Gmail邮件通知功能。

## 🎯 配置目标

- 配置Gmail SMTP发送邮件通知
- 设置应用专用密码确保安全性
- 测试邮件发送功能

## 🔧 详细步骤

### 步骤1: 开启Gmail两步验证

1. **登录Gmail账户**
   - 访问: https://mail.google.com
   - 确保已登录 redyuan43@gmail.com

2. **进入安全设置**
   - 访问: https://myaccount.google.com/security
   - 登录你的Google账户

3. **开启两步验证**
   - 找到"登录Google"部分
   - 点击"两步验证"
   - 如果未开启，点击"开始"
   - 按照提示完成两步验证设置

### 步骤2: 生成应用专用密码

1. **进入应用密码页面**
   - 在安全设置页面
   - 点击"应用专用密码"
   - 可能需要重新输入密码

2. **选择应用和设备**
   - 应用: 选择"邮件"
   - 设备: 选择"其他(自定义名称)"
   - 输入名称: "Photo Sync Monitor"

3. **生成密码**
   - 点击"生成"按钮
   - 系统将显示16位密码 (例如: `upxpxublccacdyaw`)
   - **重要**: 立即复制保存，离开页面后无法再次查看

### 步骤3: 配置系统邮件服务

#### 方法A: 自动配置 (推荐)

```bash
# 进入项目目录
cd /home/ivan/photo-sync-project

# 测试邮件 (脚本会自动配置)
./sync_monitor.sh test
```

#### 方法B: 手动配置

1. **安装邮件工具**
   ```bash
   sudo apt update
   sudo apt install mailutils ssmtp
   ```

2. **配置ssmtp**
   ```bash
   sudo nano /etc/ssmtp/ssmtp.conf
   ```

3. **填入以下配置**
   ```ini
   # Gmail SMTP配置
   root=redyuan43@gmail.com
   mailhub=smtp.gmail.com:587
   AuthUser=redyuan43@gmail.com
   AuthPass=upxpxublccacdyaw  # 替换为你的应用专用密码
   UseSTARTTLS=YES
   FromLineOverride=YES
   ```

4. **设置权限**
   ```bash
   sudo chmod 640 /etc/ssmtp/ssmtp.conf
   ```

### 步骤4: 测试邮件功能

#### 使用项目脚本测试
```bash
cd /home/ivan/photo-sync-project
./sync_monitor.sh test
```

#### 使用系统命令测试
```bash
echo "测试邮件" | mail -s "测试主题" redyuan43@gmail.com
```

### 步骤5: 验证邮件接收

1. **检查收件箱**
   - 登录 redyuan43@gmail.com
   - 查看是否收到测试邮件
   - 检查垃圾邮件文件夹

2. **查看邮件内容**
   - 主题应包含测试字样
   - 内容应显示测试时间

## 🔍 故障排除

### 常见错误及解决方法

#### 错误1: Authorization failed
```
sendmail: Authorization failed (535 5.7.8 BadCredentials)
```

**原因**: 密码错误或配置问题
**解决**:
1. 确认两步验证已开启
2. 重新生成应用专用密码
3. 检查密码格式 (16位连续字符，无空格)

#### 错误2: Cannot open smtp.gmail.com:587
```
sendmail: Cannot open smtp.gmail.com:587
```

**原因**: 网络连接问题或配置语法错误
**解决**:
1. 检查网络连接
2. 确认配置文件格式正确
3. 测试端口连通性: `telnet smtp.gmail.com 587`

#### 错误3: 邮件未收到
**解决**:
1. 检查垃圾邮件文件夹
2. 确认邮箱地址正确
3. 查看系统邮件日志: `tail -f /var/log/mail.log`

### 调试命令

```bash
# 测试网络连接
telnet smtp.gmail.com 587

# 检查ssmtp配置
sudo cat /etc/ssmtp/ssmtp.conf

# 测试邮件发送
echo "test" | sendmail -v redyuan43@gmail.com

# 查看系统日志
tail -f /var/log/mail.log
```

## 📋 配置检查清单

- [ ] Gmail账户已登录
- [ ] 两步验证已开启
- [ ] 应用专用密码已生成
- [ ] ssmtp已安装
- [ ] /etc/ssmtp/ssmtp.conf已配置
- [ ] 权限已设置 (640)
- [ ] 邮件测试成功
- [ ] 监控脚本邮件功能正常

## 🎉 配置完成

一旦邮件配置成功，你将享受到以下功能：

- ✅ 同步完成后自动收到邮件通知
- ✅ 详细的同步统计报告
- ✅ 实时状态更新
- ✅ 错误和警告提醒

## 📞 技术支持

如果遇到问题：

1. **查看详细日志**
   ```bash
   ./sync_monitor.sh logs
   ```

2. **重新运行配置**
   ```bash
   ./sync_monitor.sh test
   ```

3. **检查项目README**
   ```bash
   cat README.md
   ```

---

**配置完成后，你就可以放心享受哈雷酱大小小姐的完美同步服务了！** (￣▽￣*)

**Copyright © 2025 哈雷酱大小小姐 - 完美代码工作室**