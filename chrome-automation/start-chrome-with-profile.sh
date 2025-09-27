#!/bin/bash

# Chrome DevTools with User Profile Script
# 用于启动带有用户配置文件的Chrome，保持登录状态

# 配置参数
PORT=9222
PROFILE_DIR="C:\ChromeDebugProfile"
CHROME_PATH="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Chrome DevTools 启动器 (带用户配置)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查是否在WSL环境
if ! grep -qi microsoft /proc/version; then
    echo -e "${RED}错误: 未检测到WSL环境${NC}"
    echo "此脚本需要在WSL环境中运行"
    exit 1
fi

# 检查Chrome是否存在
if [ ! -f "$CHROME_PATH" ]; then
    echo -e "${RED}错误: 找不到Chrome${NC}"
    echo "请确保Chrome安装在: $CHROME_PATH"
    exit 1
fi

echo -e "${YELLOW}配置信息:${NC}"
echo "  调试端口: $PORT"
echo "  配置目录: $PROFILE_DIR"
echo ""

# 检查端口是否被占用
if netstat -an | grep -q ":$PORT "; then
    echo -e "${YELLOW}警告: 端口 $PORT 可能已被占用${NC}"
    echo "是否要继续? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

echo -e "${GREEN}正在启动Chrome...${NC}"

# 启动Chrome
"$CHROME_PATH" \
    --remote-debugging-port=$PORT \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-features=TranslateUI \
    --disable-ipc-flooding-protection &

# 等待Chrome启动
sleep 3

# 检查Chrome是否成功启动
if curl -s http://localhost:$PORT/json/version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Chrome已成功启动！${NC}"
    echo ""
    echo -e "${GREEN}使用说明:${NC}"
    echo "1. 调试接口: http://localhost:$PORT"
    echo "2. 查看所有页面: http://localhost:$PORT/json"
    echo ""

    # 检查是否是首次使用（配置目录是否存在）
    if [ ! -d "/mnt/c/ChromeDebugProfile" ]; then
        echo -e "${YELLOW}首次使用提示:${NC}"
        echo "1. 在打开的Chrome浏览器中登录您的B站账号"
        echo "2. 登录其他需要的网站账号"
        echo "3. 安装需要的浏览器扩展"
        echo "4. 这些设置会自动保存，下次启动时保持"
    else
        echo -e "${GREEN}提示: 使用已有配置文件，登录状态已保存${NC}"
    fi

    echo ""
    echo -e "${YELLOW}注意事项:${NC}"
    echo "- 关闭此Chrome窗口前，请保存好您的工作"
    echo "- 配置文件保存在: $PROFILE_DIR"
    echo "- 要完全退出，请关闭Chrome窗口"

else
    echo -e "${RED}错误: Chrome启动失败或调试端口未响应${NC}"
    echo "请检查："
    echo "1. 是否有其他Chrome实例正在运行"
    echo "2. Windows防火墙是否阻止了端口 $PORT"
    exit 1
fi

echo ""
echo -e "${GREEN}Chrome DevTools 已就绪！${NC}"