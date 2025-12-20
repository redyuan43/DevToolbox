#!/usr/bin/bash

# ============================================================================
# 同步监控脚本 - 哈雷酱大小小姐的智能监控！(￣▽￣*)
# ============================================================================

# 配置变量（本小姐的完美设置！）
SYNC_SCRIPT="/home/ivan/sync_all_in_one.sh"
CHECK_INTERVAL=300  # 5分钟检查一次（300秒）
LOG_FILE="$HOME/sync_monitor_$(date +%Y%m%d_%H%M%S).log"
PID_FILE="$HOME/sync_monitor.pid"

# 邮件配置（需要配置你自己的邮箱哦，笨蛋！）
EMAIL_TO="redyuan43@gmail.com"  # 修改为你的邮箱地址
EMAIL_SUBJECT="🎉 Photos同步完成通知 - 哈雷酱大小小姐报告"
EMAIL_FROM="sync-monitor@localhost"

# 显示帮助信息（哼，才不是特地为你准备的！）
show_help() {
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│     哈雷酱大小小姐的同步监控脚本 (￣▽￣*)                   │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│ 用法：                                                       │"
    echo "│   $0 start    - 启动监控进程                                 │"
    echo "│   $0 stop     - 停止监控进程                                 │"
    echo "│   $0 status   - 查看监控状态                                 │"
    echo "│   $0 logs     - 查看监控日志                                 │"
    echo "│   $0 test     - 测试邮件发送功能                             │"
    echo "│   $0 help     - 显示这个帮助信息（笨蛋才需要看！）            │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│ 配置：                                                       │"
    echo "│   检查间隔: $((CHECK_INTERVAL/60))分钟                       │"
    echo "│   邮箱地址: $EMAIL_TO                                         │"
    echo "│   监控脚本: $SYNC_SCRIPT                                     │"
    echo "└─────────────────────────────────────────────────────────────┘"
}

# 日志函数（记录所有操作，本小姐可是很严谨的！）
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查邮箱配置是否有效
check_email_config() {
    if [ "$EMAIL_TO" = "your-email@example.com" ]; then
        log_message "⚠️  警告：邮箱地址未配置，请修改脚本中的EMAIL_TO变量！"
        return 1
    fi
    return 0
}

# 发送邮件通知（本小姐的高级通知功能！）
send_email() {
    local subject="$1"
    local body="$2"

    if ! check_email_config; then
        log_message "邮件发送失败：邮箱配置无效"
        return 1
    fi

    # 优先尝试使用curl发送Gmail（如果配置了SMTP）
    if command -v curl &> /dev/null && [ -n "$GMAIL_APP_PASSWORD" ]; then
        local email_data=$(cat << EOF
From: "Sync Monitor" <sync-monitor@gmail.com>
To: $EMAIL_TO
Subject: $subject
Content-Type: text/plain; charset=UTF-8

$body
EOF
        )

        curl -s --url 'smtps://smtp.gmail.com:465' --ssl-reqd \
             --mail-from "sync-monitor@gmail.com" --mail-rcpt "$EMAIL_TO" \
             --user "redyuan43@gmail.com:$GMAIL_APP_PASSWORD" \
             -T <(echo "$email_data") 2>/dev/null

        if [ $? -eq 0 ]; then
            log_message "✓ 邮件已通过Gmail SMTP发送"
            return 0
        fi
    fi

    # 尝试使用系统mail命令
    if command -v mail &> /dev/null; then
        echo "$body" | mail -s "$subject" "$EMAIL_TO" 2>/dev/null
        if [ $? -eq 0 ]; then
            log_message "✓ 邮件已通过mail命令发送"
            return 0
        fi
    fi

    # 如果都失败了，记录到日志并显示替代方案
    log_message "❌ 邮件发送失败，系统中未配置有效的邮件工具"
    log_message "📧 邮件内容如下："
    log_message "主题: $subject"
    log_message "收件人: $EMAIL_TO"
    log_message "内容: $body"
    log_message ""
    log_message "💡 配置Gmail SMTP方法："
    log_message "1. 设置环境变量: export GMAIL_APP_PASSWORD='你的应用专用密码'"
    log_message "2. 或者安装系统邮件工具: sudo apt install mailutils"

    # 发送到系统通知（如果支持）
    if command -v notify-send &> /dev/null; then
        notify-send "$subject" "同步完成！请查看日志了解详情。"
        log_message "✓ 已发送系统桌面通知"
    fi

    return 1
}

# 检查同步状态（本小姐的智能检测！）
check_sync_status() {
    # 检查是否有同步进程在运行
    if [ -f "$HOME/sync.pid" ]; then
        local sync_pid=$(cat "$HOME/sync.pid" 2>/dev/null)
        if [ -n "$sync_pid" ] && ps -p "$sync_pid" > /dev/null 2>&1; then
            log_message "🔄 同步进程仍在运行 (PID: $sync_pid)"
            return 1  # 同步中
        else
            log_message "🔍 发现无效PID文件，清理中..."
            rm -f "$HOME/sync.pid"
        fi
    fi

    # 检查最近是否有同步完成
    local latest_log=$(ls -t "$HOME"/sync_*.log 2>/dev/null | head -1)
    if [ -n "$latest_log" ]; then
        # 检查日志中是否有"同步完成"的记录
        if grep -q "同步完成" "$latest_log" 2>/dev/null; then
            local completion_time=$(grep "同步完成" "$latest_log" | tail -1 | grep -o '[0-9-]* [0-9:]*')
            log_message "✅ 检测到同步已于 $completion_time 完成"
            return 0  # 同步完成
        fi
    fi

    log_message "😴 未发现同步活动"
    return 2  # 无同步活动
}

# 生成详细的同步报告（本小姐的专业报告！）
generate_sync_report() {
    local latest_log=$(ls -t "$HOME"/sync_*.log 2>/dev/null | head -1)
    local report="📊 同步完成报告 - 哈雷酱大小小姐的完美作品！(￣▽￣*)\n\n"

    if [ -n "$latest_log" ]; then
        # 统计同步信息
        local files_synced=$(grep -c "✓.*同步完成" "$latest_log" 2>/dev/null || echo "0")
        local files_skipped=$(grep -c "跳过已存在的文件" "$latest_log" 2>/dev/null || echo "0")
        local files_failed=$(grep -c "✗.*同步失败" "$latest_log" 2>/dev/null || echo "0")
        local completion_time=$(grep "同步完成" "$latest_log" | tail -1 | grep -o '[0-9-]* [0-9:]*' 2>/dev/null || echo "未知")

        report+="⏰ 完成时间: $completion_time\n"
        report+="✓ 成功同步: $files_synced 个文件\n"
        report+="⏭️  跳过已存在: $files_skipped 个文件\n"
        report+="❌ 同步失败: $files_failed 个文件\n\n"

        # 获取目录大小信息
        if [ -d "/vol1/1000/Photos/" ]; then
            local target_size=$(du -sh "/vol1/1000/Photos/" 2>/dev/null | cut -f1)
            local target_files=$(find "/vol1/1000/Photos/" -type f 2>/dev/null | wc -l)
            report+="📁 目标目录: /vol1/1000/Photos/\n"
            report+="💾 目录大小: $target_size\n"
            report+="📄 文件总数: $target_files 个\n\n"
        fi

        # 最近同步的文件
        report+="🔝 最近同步的文件:\n"
        grep "✓.*同步完成" "$latest_log" | tail -5 | while read line; do
            local filename=$(echo "$line" | grep -o '✓ [^.]*\.' | sed 's/✓ //')
            if [ -n "$filename" ]; then
                report+="   • $filename\n"
            fi
        done
    else
        report+="⚠️  未找到同步日志文件\n"
    fi

    report+="\n🎉 监控脚本由哈雷酱大小小姐精心编写！(*/ω＼*)"
    echo -e "$report"
}

# 监控主循环（本小姐的完美监控逻辑！）
start_monitoring() {
    # 检查是否已经有监控进程在运行
    if [ -f "$PID_FILE" ]; then
        local monitor_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$monitor_pid" ] && ps -p "$monitor_pid" > /dev/null 2>&1; then
            echo "(￣へ￣) 监控进程已在运行 (PID: $monitor_pid)"
            exit 1
        else
            rm -f "$PID_FILE"
        fi
    fi

    log_message "🚀 哈雷酱大小小姐的同步监控启动！"
    log_message "📧 邮件通知将发送至: $EMAIL_TO"
    log_message "⏰ 检查间隔: $((CHECK_INTERVAL/60)) 分钟"
    log_message "📋 日志文件: $LOG_FILE"

    # 将进程ID写入文件
    echo $$ > "$PID_FILE"

    local completion_notified=false

    while true; do
        local status=0
        check_sync_status
        status=$?

        case $status in
            0)
                # 同步完成
                if [ "$completion_notified" = false ]; then
                    log_message "🎉 检测到同步完成！准备发送通知..."

                    local report=$(generate_sync_report)
                    if send_email "$EMAIL_SUBJECT" "$report"; then
                        log_message "✅ 同步完成通知已成功发送！"
                    else
                        log_message "❌ 邮件发送失败，请检查邮件配置"
                    fi

                    completion_notified=true
                else
                    log_message "🔄 同步已完成，通知已发送过"
                fi
                ;;
            1)
                # 同步中
                completion_notified=false
                ;;
            2)
                # 无同步活动
                log_message "💤 当前无同步活动，继续监控..."
                ;;
        esac

        # 等待下次检查
        sleep $CHECK_INTERVAL
    done
}

# 停止监控
stop_monitoring() {
    if [ -f "$PID_FILE" ]; then
        local monitor_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$monitor_pid" ] && ps -p "$monitor_pid" > /dev/null 2>&1; then
            echo "停止监控进程 (PID: $monitor_pid)..."
            kill $monitor_pid
            sleep 2

            if ps -p $monitor_pid > /dev/null 2>&1; then
                echo "强制停止进程..."
                kill -9 $monitor_pid
            fi

            rm -f "$PID_FILE"
            echo "(￣▽￣*) 监控进程已停止！"
        else
            echo "(￣_￣) 监控进程已经停止"
            rm -f "$PID_FILE"
        fi
    else
        echo "(￣_￣) 没有找到正在运行的监控进程"
    fi
}

# 查看监控状态
show_monitor_status() {
    if [ -f "$PID_FILE" ]; then
        local monitor_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$monitor_pid" ] && ps -p "$monitor_pid" > /dev/null 2>&1; then
            echo "┌─ 监控进程状态 ────────────────────────┐"
            echo "│ 状态: 运行中 (＾∀＾)●"
            echo "│ 进程ID: $monitor_pid"
            echo "│ 启动时间: $(ps -p $monitor_pid -o lstart=)"
            echo "│ 检查间隔: $((CHECK_INTERVAL/60))分钟"
            echo "│ 邮箱: $EMAIL_TO"
            echo "│ 日志: $LOG_FILE"
            echo "└─────────────────────────────────────┘"
        else
            echo "(￣_￣) 监控进程已停止"
            rm -f "$PID_FILE"
        fi
    else
        echo "(￣_￣) 没有找到正在运行的监控进程"
    fi
}

# 查看监控日志
show_monitor_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "最新监控日志: $LOG_FILE"
        echo "┌─ 最近20行日志 ────────────────────────┐"
        tail -20 "$LOG_FILE"
        echo "└─────────────────────────────────────┘"
        echo ""
        echo "查看完整日志: cat '$LOG_FILE'"
    else
        echo "(｡•ˇ‸ˇ•｡) 没有找到监控日志文件"
    fi
}

# 测试邮件功能
test_email() {
    echo "🧪 测试邮件发送功能..."
    if check_email_config; then
        local test_subject="🧪 测试邮件 - 哈雷酱大小小姐监控脚本"
        local test_body="这是一封测试邮件，用于验证邮件发送功能是否正常。

如果你收到这封邮件，说明配置正确！

测试时间: $(date '+%Y-%m-%d %H:%M:%S')
来自: 哈雷酱大小小姐的完美监控脚本 (￣▽￣*)"

        if send_email "$test_subject" "$test_body"; then
            echo "✅ 测试邮件发送成功！请检查邮箱 $EMAIL_TO"
        else
            echo "❌ 测试邮件发送失败"
        fi
    else
        echo "❌ 请先配置邮箱地址！"
    fi
}

# 主程序（这才是核心所在！）
case "$1" in
    start)
        start_monitoring
        ;;
    stop)
        stop_monitoring
        ;;
    status)
        show_monitor_status
        ;;
    logs)
        show_monitor_logs
        ;;
    test)
        test_email
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "(￣へ￣) 未知参数: $1"
        echo ""
        show_help
        exit 1
        ;;
esac