# Chrome DevTools WSL2 配置指南

## 概述
本文档详细介绍如何在 WSL2 环境中配置 Chrome 浏览器的调试接口，使其能够与 MCP Chrome DevTools 工具配合使用，实现远程浏览器控制和自动化操作。

## 环境要求
- Windows 10/11 with WSL2
- Chrome 浏览器 (安装在 Windows 主机上)
- Claude Code 运行在 WSL2 环境中

## 安装配置步骤

### 1. Chrome 启动脚本配置

创建 Chrome 调试启动脚本：

```bash
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
        echo "1. 在打开的Chrome浏览器中登录您的账号"
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
```

### 2. 脚本使用方法

1. 将上述脚本保存为 `start-chrome-with-profile.sh`
2. 赋予执行权限：
   ```bash
   chmod +x start-chrome-with-profile.sh
   ```
3. 运行脚本：
   ```bash
   ./start-chrome-with-profile.sh
   ```

### 3. 验证安装

检查 Chrome 调试接口是否正常工作：

```bash
# 检查调试端口状态
netstat -an | grep :9222

# 测试调试接口响应
curl -s http://localhost:9222/json/version

# 获取当前打开的标签页
curl -s http://localhost:9222/json | jq '.[0:3]'
```

## Claude Code MCP 安装

### 自动安装（推荐）

使用 Claude Code 的内置 MCP 安装命令：

```bash
claude mcp add chrome-devtools npx chrome-devtools-mcp@latest
```

### 手动配置

如需手动配置，编辑 `~/.claude.json` 文件，在 `mcpServers` 部分添加：

```json
"chrome-devtools": {
  "type": "stdio",
  "command": "npx",
  "args": [
    "chrome-devtools-mcp@latest",
    "--browserUrl",
    "http://127.0.0.1:9222"
  ],
  "env": {}
}
```

### 验证安装

安装完成后，重启 Claude Code 并验证 MCP 工具是否可用：

```
mcp__chrome-devtools__new_page
```

## MCP Chrome DevTools 使用方法

### 基本操作

1. **打开新页面**
   ```javascript
   mcp__chrome-devtools__new_page
   url: "https://example.com"
   ```

2. **获取页面快照**
   ```javascript
   mcp__chrome-devtools__take_snapshot
   ```

3. **点击元素**
   ```javascript
   mcp__chrome-devtools__click
   uid: "element_uid_from_snapshot"
   ```

4. **填写表单**
   ```javascript
   mcp__chrome-devtools__fill
   uid: "input_uid"
   value: "text_to_fill"
   ```

5. **执行 JavaScript**
   ```javascript
   mcp__chrome-devtools__evaluate_script
   function: "() => { return document.title; }"
   ```

### 常见使用场景

#### 1. 网页自动化操作
- 自动登录网站
- 填写表单
- 点击按钮
- 获取页面信息

#### 2. 网站测试
- 功能测试
- 界面交互测试
- 数据提取

#### 3. 信息收集
- 获取页面内容
- 提取特定数据
- 监控网站变化

## 故障排除

### 常见问题及解决方案

1. **端口被占用**
   ```bash
   # 查看占用端口的进程
   netstat -tulpn | grep :9222

   # 关闭占用进程
   pkill chrome
   ```

2. **MCP 连接失败**
   - 确保 Chrome 调试端口正在运行
   - 检查防火墙设置
   - 验证端口号配置正确 (默认 9222)

3. **权限问题**
   ```bash
   # 确保脚本有执行权限
   chmod +x start-chrome-with-profile.sh
   ```

### 调试命令

```bash
# 检查 Chrome 进程
ps aux | grep chrome

# 检查端口监听状态
ss -tlnp | grep :9222

# 测试调试接口
curl -s http://localhost:9222/json | jq '.'
```

## 安全注意事项

1. **端口安全**
   - 调试端口仅在本地监听 (127.0.0.1)
   - 不要将调试端口暴露到公网

2. **数据隔离**
   - 使用独立的配置文件目录
   - 避免与日常使用的 Chrome 配置混淆

3. **进程管理**
   - 使用完毕后及时关闭 Chrome 进程
   - 避免资源占用过多

## 扩展功能

### 自定义配置

可以修改脚本中的配置参数：

```bash
# 自定义端口
PORT=9223

# 自定义配置目录
PROFILE_DIR="C:\CustomChromeProfile"

# 添加其他 Chrome 启动参数
--disable-web-security \
--disable-features=VizDisplayCompositor
```

### 批量操作

可以结合脚本实现批量操作：

```bash
# 批量打开多个页面
for url in "https://site1.com" "https://site2.com"; do
    # 使用 MCP 工具打开页面
    echo "Opening $url"
done
```

## 总结

通过本配置方案，可以实现：
- WSL2 环境下控制 Windows Chrome 浏览器
- 保持用户登录状态和浏览器配置
- 支持完整的浏览器自动化操作
- 适用于各种网页自动化场景

该方案特别适合需要在 Linux 环境中进行 Web 自动化测试、数据采集或其他浏览器相关任务的场景。