#!/usr/bin/bash

# ============================================================================
# 哈雷酱大小小姐的一键安装脚本！(￣▽￣*)
# ============================================================================

echo "┌─────────────────────────────────────────────────────────────┐"
echo "│     哈雷酱大小小姐的Photos同步项目安装器                      │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  此脚本将自动安装和配置所有必要的依赖和工具                  │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then
    echo "❌ 请不要以root用户运行此脚本！"
    echo "💡 使用普通用户运行: ./install.sh"
    exit 1
fi

echo "🔧 开始安装系统依赖..."

# 更新包管理器
echo "📦 更新包管理器..."
if command -v apt &> /dev/null; then
    sudo apt update
else
    echo "❌ 未检测到apt包管理器，此脚本仅支持Debian/Ubuntu系统"
    exit 1
fi

# 安装必要的工具
echo "📧 安装邮件工具..."
sudo apt install -y mailutils ssmtp curl

# 检查安装结果
if [ $? -eq 0 ]; then
    echo "✅ 系统依赖安装成功！"
else
    echo "❌ 系统依赖安装失败！"
    exit 1
fi

echo ""
echo "📧 配置邮件服务..."

# 创建ssmtp配置模板
echo "📝 创建邮件配置模板..."
sudo mkdir -p /etc/ssmtp

# 创建配置文件 (不包含密码)
sudo tee /etc/ssmtp/ssmtp.conf.template > /dev/null << 'EOF'
# Gmail SMTP配置模板 - 哈雷酱大小小姐的完美配置！
# 请修改以下配置为你的邮箱信息

root=your-email@gmail.com
mailhub=smtp.gmail.com:587
AuthUser=your-email@gmail.com
AuthPass=YOUR_APP_PASSWORD_HERE
UseSTARTTLS=YES
FromLineOverride=YES

# 配置说明:
# 1. 将 your-email@gmail.com 改为你的Gmail地址
# 2. 将 YOUR_APP_PASSWORD_HERE 改为你的16位应用专用密码
# 3. 应用专用密码生成方法:
#    - 访问 https://myaccount.google.com/security
#    - 开启两步验证
#    - 生成应用专用密码
EOF

echo "✅ 邮件配置模板已创建: /etc/ssmtp/ssmtp.conf.template"

echo ""
echo "🔧 设置脚本权限..."
chmod +x *.sh
echo "✅ 脚本权限已设置"

echo ""
echo "📁 创建日志目录..."
mkdir -p ~/logs
echo "✅ 日志目录已创建: ~/logs"

echo ""
echo "🎉 安装完成！"
echo ""
echo "📋 后续步骤:"
echo "1. 配置邮件: nano /etc/ssmtp/ssmtp.conf.template"
echo "2. 复制配置: sudo cp /etc/ssmtp/ssmtp.conf.template /etc/ssmtp/ssmtp.conf"
echo "3. 测试邮件: ./sync_monitor.sh test"
echo "4. 开始使用: ./start.sh"
echo ""
echo "📖 详细文档: cat README.md"
echo "📧 邮件配置: cat EMAIL_SETUP.md"
echo ""
echo "🎊 恭喜！哈雷酱大小小姐的完美同步系统已安装完成！(*/ω＼*)"