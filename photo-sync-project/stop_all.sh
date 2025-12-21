#!/usr/bin/bash

# ============================================================================
# 哈雷酱大小小姐的通用停止所有脚本！(￣▽￣*)
# ============================================================================

echo "┌─────────────────────────────────────────────────────────────┐"
echo "│     哈雷酱大小小姐的一键停止所有同步脚本                      │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  此脚本将停止所有相关的同步和监控进程                        │"
echo "└─────────────────────────────────────────────────────────────┘"

echo ""
echo "🛑 开始停止所有相关进程..."

# 1. 停止sync_all_in_one.sh进程
echo "📦 停止同步进程..."
./sync_all_in_one.sh stop

# 2. 停止sync_monitor.sh进程
echo "🔍 停止监控进程..."
./sync_monitor.sh stop

# 3. 清理工作进程和PID文件
echo "🧹 清理相关工作进程..."
ps aux | grep -E "(find.*/vol0|rsync.*/vol1)" | awk '{print $2}' | xargs -r kill 2>/dev/null

echo "🗑️ 清理PID文件..."
find "$HOME" -name "*.pid" -type f -delete 2>/dev/null

# 4. 最终检查
echo ""
echo "🔍 最终检查..."
sleep 1

remaining_sync=$(ps aux | grep "[s]ync_all_in_one.sh" | wc -l)
remaining_monitor=$(ps aux | grep "[s]ync_monitor.sh" | wc -l)
total_remaining=$((remaining_sync + remaining_monitor))

if [ "$total_remaining" -eq 0 ]; then
    echo "🎉 (￣▽￣*) 所有进程已成功停止！"
else
    echo "⚠️ (｡•ˇ‸ˇ•｡) 仍有 $total_remaining 个进程在运行"
    if [ "$remaining_sync" -gt 0 ]; then
        echo "剩余同步进程: $remaining_sync"
        ps aux | grep "[s]ync_all_in_one.sh"
    fi
    if [ "$remaining_monitor" -gt 0 ]; then
        echo "剩余监控进程: $remaining_monitor"
        ps aux | grep "[s]ync_monitor.sh"
    fi
fi

echo ""
echo "✅ 一键停止完成！"
echo ""
echo "💡 提示："
echo "• 查看进程状态: ps aux | grep sync"
echo "• 启动同步: ./sync_all_in_one.sh start"
echo "• 启动监控: ./sync_monitor.sh start"
echo "• 启动所有: ./start.sh"
echo ""
echo "🎊 哈雷酱大小小姐的一键停止功能就是这么完美！(*/ω\*)"