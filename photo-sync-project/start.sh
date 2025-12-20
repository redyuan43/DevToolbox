#!/usr/bin/bash

# ============================================================================
# 哈雷酱大小小姐的便捷启动脚本！(￣▽￣*)
# ============================================================================

echo "┌─────────────────────────────────────────────────────────────┐"
echo "│     哈雷酱大小小姐的Photos同步项目启动器                      │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  项目文件：                                                 │"
echo "│  • sync_all_in_one.sh  - 主同步脚本                          │"
echo "│  • sync_monitor.sh    - 监控和邮件脚本                      │"
echo "│  • README.md          - 详细文档                            │"
echo "│  • start.sh           - 便捷启动器 (当前文件)               │"
echo "└─────────────────────────────────────────────────────────────┘"

echo ""
echo "请选择操作："
echo "1) 启动同步进程"
echo "2) 查看同步状态"
echo "3) 启动监控进程"
echo "4) 查看监控状态"
echo "5) 测试邮件功能"
echo "6) 停止所有进程"
echo "7) 查看项目文件"
echo "8) 查看README文档"
echo "9) 退出"
echo ""

read -p "请输入选项 (1-9): " choice

case $choice in
    1)
        echo "🚀 启动同步进程..."
        ./sync_all_in_one.sh start
        ;;
    2)
        echo "📊 查看同步状态..."
        ./sync_all_in_one.sh status
        ;;
    3)
        echo "🔍 启动监控进程..."
        ./sync_monitor.sh start
        ;;
    4)
        echo "📋 查看监控状态..."
        ./sync_monitor.sh status
        ;;
    5)
        echo "📧 测试邮件功能..."
        ./sync_monitor.sh test
        ;;
    6)
        echo "🛑 停止所有进程..."
        ./sync_all_in_one.sh stop
        ./sync_monitor.sh stop
        ;;
    7)
        echo "📁 项目文件列表："
        echo ""
        ls -la
        echo ""
        echo "📊 文件大小统计："
        du -sh *
        ;;
    8)
        echo "📖 查看README文档..."
        if command -v less &> /dev/null; then
            less README.md
        elif command -v more &> /dev/null; then
            more README.md
        else
            cat README.md
        fi
        ;;
    9)
        echo "👋 再见！感谢使用哈雷酱大小小姐的完美解决方案！(￣▽￣*)"
        exit 0
        ;;
    *)
        echo "❌ 无效选项，请重新运行脚本！"
        exit 1
        ;;
esac

echo ""
echo "✅ 操作完成！"
echo ""
echo "💡 提示："
echo "• 查看日志: ./sync_all_in_one.sh logs"
echo "• 实时监控: ./sync_all_in_one.sh watch"
echo "• 帮助信息: ./sync_all_in_one.sh help"
echo ""
echo "🎉 哈雷酱大小小姐祝你使用愉快！(*/ω＼*)"