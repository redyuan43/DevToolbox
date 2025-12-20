# 🚀 项目分享说明

## 📦 如何分享给其他AI

### 快速部署方法

1. **分享项目文件**
   ```
   将整个 /home/ivan/photo-sync-project/ 文件夹分享给其他AI
   ```

2. **让其他AI执行以下命令**
   ```bash
   cd photo-sync-project

   # 一键安装依赖
   ./install.sh

   # 配置邮件 (会提示输入应用专用密码)
   ./config_template.sh

   # 测试邮件功能
   ./sync_monitor.sh test

   # 开始使用
   ./start.sh
   ```

3. **或者手动配置**
   ```bash
   # 安装依赖
   sudo apt install mailutils ssmtp

   # 配置邮件 (参考EMAIL_SETUP.md)
   nano /etc/ssmtp/ssmtp.conf

   # 测试邮件
   ./sync_monitor.sh test
   ```

## 🔧 自定义配置

其他AI可以根据需要修改：

- **邮箱地址**: 编辑 `sync_monitor.sh` 中的 `EMAIL_TO` 变量
- **同步目录**: 编辑 `sync_all_in_one.sh` 中的 `SOURCE_DIR` 和 `TARGET_DIR`
- **监控间隔**: 编辑 `sync_monitor.sh` 中的 `CHECK_INTERVAL`

## 📚 必读文档

- `README.md` - 完整项目说明
- `EMAIL_SETUP.md` - 邮件配置详细指南
- `PROJECT_INFO.txt` - 项目快速概览

## ⚠️ 重要提醒

- **不要直接使用包含密码的配置文件**
- **应用专用密码需要用户自己生成**
- **确保Gmail账户已开启两步验证**

---

**这就是哈雷酱大小小姐的完美分享方案！** (￣▽￣*)