#!/usr/bin/bash

# ============================================================================
# 哈雷酱大小小姐的redyuan43@gmail.com专用配置脚本
# ============================================================================

echo "🔧 配置邮件服务 for redyuan43@gmail.com..."

# 读取用户输入的应用专用密码
echo ""
echo "请输入你的Gmail应用专用密码 (16位字符):"
read -s -p "密码: " app_password
echo ""

if [ ${#app_password} -ne 16 ]; then
    echo "❌ 密码长度不正确！应用专用密码应该是16位字符"
    echo "💡 请访问 https://myaccount.google.com/security 重新生成"
    exit 1
fi

# 创建ssmtp配置文件
echo "📝 创建邮件配置..."
sudo tee /etc/ssmtp/ssmtp.conf > /dev/null << EOF
# Gmail SMTP配置 - 哈雷酱大小小姐的完美配置！
root=redyuan43@gmail.com
mailhub=smtp.gmail.com:587
AuthUser=redyuan43@gmail.com
AuthPass=$app_password
UseSTARTTLS=YES
FromLineOverride=YES
EOF

# 设置权限
sudo chmod 640 /etc/ssmtp/ssmtp.conf

echo "✅ 邮件配置完成！"

# 测试邮件发送
echo ""
echo "📧 测试邮件发送..."
if echo "这是一封测试邮件 - 哈雷酱大小小姐的完美脚本！" | mail -s "🎉 测试邮件" redyuan43@gmail.com; then
    echo "✅ 邮件发送成功！请检查收件箱"
else
    echo "❌ 邮件发送失败，请检查配置"
fi

echo ""
echo "🎊 配置完成！现在可以使用完整功能了："