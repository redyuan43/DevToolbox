#!/usr/bin/bash

# ============================================================================
# 一体化文件同步脚本 - 哈雷酱大小小姐的完美作品！(´｡• ᵕ •｡`)
# ============================================================================

# 设置变量（这些配置对本小姐来说就像呼吸一样简单！）
SOURCE_DIR="/vol02/1000-0-02ffe18d"
TARGET_DIR="/vol1/1000/Photos/"
LOG_DIR="$HOME"
PID_FILE="$HOME/sync.pid"

# 显示帮助信息（哼，才不是特地为你准备的！）
show_help() {
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│     哈雷酱大小小姐的一体化同步脚本 (￣▽￣*)                   │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│ 用法：                                                       │"
    echo "│   $0 start    - 启动后台同步进程                             │"
    echo "│   $0 stop     - 停止正在运行的同步进程                        │"
    echo "│   $0 status   - 查看同步进程状态                             │"
    echo "│   $0 logs     - 查看最新的同步日志                           │"
    echo "│   $0 watch    - 实时监控同步日志                             │"
    echo "│   $0 help     - 显示这个帮助信息（笨蛋才需要看！）            │"
    echo "└─────────────────────────────────────────────────────────────┘"
}

# 检查目录是否存在（当然要检查了，本小姐可是很严谨的！）
check_directories() {
    if [ ! -d "$SOURCE_DIR" ]; then
        echo "(╯°□°）╯ 源目录不存在: $SOURCE_DIR"
        exit 1
    fi

    if [ ! -d "$TARGET_DIR" ]; then
        echo "(╯°□°）╯ 目标目录不存在: $TARGET_DIR"
        echo "本小姐帮你创建目标目录..."
        mkdir -p "$TARGET_DIR"
        echo "(￣▽￣)ﾉ 目标目录创建完成！"
    fi
}

# 启动同步进程（这才是主要功能呢！）
start_sync() {
    # 检查是否已经有进程在运行
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "(￣へ￣) 同步进程已在运行 (PID: $PID)"
            echo "使用 '$0 status' 查看状态"
            exit 1
        else
            # 清理无效的PID文件
            rm -f "$PID_FILE"
        fi
    fi

    # 检查目录
    check_directories

    # 创建日志文件
    LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d_%H%M%S).log"
    touch "$LOG_FILE"

    echo "启动后台同步进程..."
    echo "源目录: $SOURCE_DIR"
    echo "目标目录: $TARGET_DIR"
    echo "日志文件: $LOG_FILE"

    # 启动后台同步进程
    (
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ====== 哈雷酱大小小姐的同步开始啦！ ======" | tee -a "$LOG_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 源目录: $SOURCE_DIR" | tee -a "$LOG_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 目标目录: $TARGET_DIR" | tee -a "$LOG_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 进程ID: $$" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"

        # 将进程ID写入文件
        echo $$ > "$PID_FILE"

        # 扁平化同步参数说明（本小姐最终完美的配置！）
        # --partial: 保留部分传输的文件，支持断点续传
        # --timeout=300: 设置5分钟超时，避免长时间卡死
        # 注意：--contimeout只适用于rsync守护进程，本地同步不需要！
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 开始扁平化Photos同步（只同步文件，忽略目录结构）..." | tee -a "$LOG_FILE"

        # 扁平化同步模式：将所有子目录的文件同步到目标根目录
        # --find: 使用find模式查找文件，--no-relative保持扁平结构
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 扫描源目录中的所有文件..." | tee -a "$LOG_FILE"

        # 使用find + rsync的扁平化方式
        find "$SOURCE_DIR" -type f -print0 | while IFS= read -r -d '' source_file; do
            filename=$(basename "$source_file")
            target_file="$TARGET_DIR/$filename"

            # 检查目标是否已存在同名文件
            if [ -f "$target_file" ]; then
                # 比较文件大小，如果不同则重新同步
                source_size=$(stat -c%s "$source_file" 2>/dev/null || echo "0")
                target_size=$(stat -c%s "$target_file" 2>/dev/null || echo "0")

                if [ "$source_size" -eq "$target_size" ]; then
                    echo "$(date '+%Y-%m-%d %H:%M:%S') - 跳过已存在的文件: $filename (大小相同)" | tee -a "$LOG_FILE"
                    continue
                else
                    echo "$(date '+%Y-%m-%d %H:%M:%S') - 发现同名但大小不同的文件: $filename (源: ${source_size}B, 目标: ${target_size}B)" | tee -a "$LOG_FILE"
                    # 重命名目标文件以避免冲突
                    mv "$target_file" "${target_file}.old_$(date +%H%M%S)" 2>/dev/null
                fi
            fi

            echo "$(date '+%Y-%m-%d %H:%M:%S') - 同步文件: $filename" | tee -a "$LOG_FILE"

            # 使用rsync同步单个文件，支持断点续传（最终优化版本！）
            rsync -av --progress --partial \
                  --timeout=300 \
                  "$source_file" "$target_file" 2>&1 | tee -a "$LOG_FILE"

            if [ $? -eq 0 ]; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') - ✓ $filename 同步完成" | tee -a "$LOG_FILE"
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') - ✗ $filename 同步失败" | tee -a "$LOG_FILE"
            fi
        done

              # 扁平化同步已完成，统计结果
        echo "" | tee -a "$LOG_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 扁平化同步完成！" | tee -a "$LOG_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 所有子目录的文件都已同步到目标根目录 (￣▽￣*)" | tee -a "$LOG_FILE"
        FINAL_STATUS=0

        # 显示同步统计
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 同步统计信息：" | tee -a "$LOG_FILE"
        echo "源目录大小: $(du -sh "$SOURCE_DIR" 2>/dev/null || echo "无法计算")" | tee -a "$LOG_FILE"
        echo "目标目录大小: $(du -sh "$TARGET_DIR" 2>/dev/null || echo "无法计算")" | tee -a "$LOG_FILE"
        echo "文件数量统计: $(find "$TARGET_DIR" -type f 2>/dev/null | wc -l) 个文件" | tee -a "$LOG_FILE"

        echo "$(date '+%Y-%m-%d %H:%M:%S') - ====== 同步进程结束 ======" | tee -a "$LOG_FILE"

        # 清理PID文件
        rm -f "$PID_FILE"
    ) &

    # 获取刚刚启动的进程ID
    PID=$!

    echo ""
    echo "o(￣▽￣)ｄ 同步进程已启动！"
    echo "┌─ 进程信息 ────────────────────────────┐"
    echo "│ 进程ID: $PID"
    echo "│ 日志文件: $LOG_FILE"
    echo "│ 查看状态: $0 status"
    echo "│ 查看日志: $0 logs"
    echo "│ 监控日志: $0 watch"
    echo "│ 停止进程: $0 stop"
    echo "└─────────────────────────────────────┘"
}

# 停止同步进程
stop_sync() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "停止同步进程 (PID: $PID)..."
            kill $PID
            sleep 2

            # 如果进程还在，强制杀死
            if ps -p $PID > /dev/null 2>&1; then
                echo "强制停止进程..."
                kill -9 $PID
            fi

            rm -f "$PID_FILE"
            echo "(￣▽￣*) 同步进程已停止！"
        else
            echo "(￣_￣) 进程已经停止了"
            rm -f "$PID_FILE"
        fi
    else
        echo "(￣_￣) 没有找到正在运行的同步进程"
    fi
}

# 查看同步状态
show_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "┌─ 同步进程状态 ────────────────────────┐"
            echo "│ 状态: 运行中 (＾∀＾)●"
            echo "│ 进程ID: $PID"
            echo "│ 启动时间: $(ps -p $PID -o lstart=)"
            echo "│ CPU使用: $(ps -p $PID -o %cpu=)%"
            echo "│ 内存使用: $(ps -p $PID -o %mem=)%"
            echo "└─────────────────────────────────────┘"
        else
            echo "(￣_￣) 进程已停止"
            rm -f "$PID_FILE"
        fi
    else
        echo "(￣_￣) 没有找到正在运行的同步进程"
    fi
}

# 查看最新日志
show_logs() {
    LATEST_LOG=$(ls -t "$LOG_DIR"/sync_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "最新日志文件: $LATEST_LOG"
        echo "┌─ 最近20行日志 ────────────────────────┐"
        tail -20 "$LATEST_LOG"
        echo "└─────────────────────────────────────┘"
        echo ""
        echo "查看完整日志: cat '$LATEST_LOG'"
        echo "实时监控: $0 watch"
    else
        echo "(｡•ˇ‸ˇ•｡) 没有找到日志文件"
    fi
}

# 实时监控日志
watch_logs() {
    LATEST_LOG=$(ls -t "$LOG_DIR"/sync_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "实时监控日志文件: $LATEST_LOG"
        echo "按 Ctrl+C 退出监控"
        echo "┌─ 实时日志 ────────────────────────────┐"
        tail -f "$LATEST_LOG"
    else
        echo "(｡•ˇ‸ˇ•｡) 没有找到日志文件"
    fi
}

# 主程序（这才是灵魂所在！）
case "$1" in
    start)
        start_sync
        ;;
    stop)
        stop_sync
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    watch)
        watch_logs
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