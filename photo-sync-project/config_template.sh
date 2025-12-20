#!/usr/bin/bash

# ============================================================================
# 哈雷酱大小小姐的通用邮件配置脚本模板
# ============================================================================

# 默认邮箱配置 (可以修改)
EMAIL_TO="redyuan43@gmail.com"

echo "🔧 配置邮件服务..."
echo "当前配置邮箱: $EMAIL_TO"

# 读取用户输入
echo ""
read -p "请输入邮箱地址 (默认: $EMAIL_TO): " user_email
if [ -n "$user_email" ]; then
    EMAIL_TO="$user_email"
fi

read -s -p "请输入Gmail应用专用密码 (16位字符): " app_password
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
root=$EMAIL_TO
mailhub=smtp.gmail.com:587
AuthUser=$EMAIL_TO
AuthPass=$app_password
UseSTARTTLS=YES
FromLineOverride=YES
EOF

# 设置权限
sudo chmod 640 /etc/ssmtp/ssmtp.conf

# 更新监控脚本中的邮箱
echo "🔄 更新监控脚本配置..."
sed -i "s/EMAIL_TO=\".*\"/EMAIL_TO=\"$EMAIL_TO\"/" sync_monitor.sh

echo "✅ 邮件配置完成！"

# 测试邮件发送
echo ""
echo "📧 测试邮件发送..."
if echo "这是一封测试邮件 - 哈雷酱大小小姐的完美脚本！" | mail -s "🎉 测试邮件" "$EMAIL_TO"; then
    echo "✅ 邮件发送成功！请检查收件箱 $EMAIL_TO"
else
    echo "❌ 邮件发送失败，请检查配置"
fi

echo ""
echo "🎊 配置完成！邮箱: $EMAIL_TO"