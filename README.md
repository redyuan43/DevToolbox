# DevToolbox - 哈雷酱大小小姐的完美开发工具库！(￣▽￣*)

个人收集的各种开发脚本、工具和配置文件集合。涵盖自动化、同步、网络代理、语音播报等多个领域的完整解决方案。

## 🎯 项目概述

这是一个综合性的开发工具库，集成了多年系统管理和自动化开发经验。每个项目都经过精心设计，追求极致的完美和实用性！

## 📁 目录结构

```
DevToolbox/
├── README.md                           # 本文件
├── photo-sync-project/                 # 📸 照片同步系统 (新!)
│   ├── sync_all_in_one.sh             # 主同步脚本
│   ├── sync_monitor.sh                # 监控和邮件通知
│   ├── start.sh                       # 交互式启动器
│   ├── stop_all.sh                    # 一键停止工具
│   ├── install.sh                     # 一键安装脚本
│   ├── README.md                      # 详细项目文档
│   └── ...                            # 其他配置和文档
├── chrome-automation/                  # 🌐 Chrome 自动化工具
│   └── start-chrome-with-profile.sh
├── spilt_screens/                      # 🪟 X11 窗口平铺脚本
│   ├── split3.sh                      # 1-3 窗口横向平铺
│   ├── split6.sh                      # 3x2 固定网格 + 守护模式
│   └── README.md                      # 使用说明
├── image-processing/                   # 🖼️ 图像处理工具
│   └── process_image.py
├── wechat-auto-reply/                  # 💬 Ubuntu 微信自动回复工具
│   ├── main.py                         # CLI 入口
│   ├── config.example.yaml             # 配置模板
│   ├── README.md                       # 详细使用说明
│   ├── systemd/                        # systemd --user 单元模板
│   └── wechat_auto_reply/             # 核心实现
├── xiaomi_tts_project/                 # 🗣️ 小米音箱TTS系统
│   ├── xiaomi_tts_websocket.py        # WebSocket TTS控制
│   ├── simple_test.py                 # 简单测试脚本
│   └── examples.py                    # 使用示例
├── v2ray_config/                      # 🔒 V2Ray代理配置
│   ├── README.md                      # 完整配置指南
│   ├── docker-v2ray-README.md         # Docker配置说明
│   ├── PROXY_GUIDE.md                 # 代理使用指南
│   └── TEST_COMMANDS.md               # 测试命令指南
├── docs/                             # 📚 文档集合
│   └── Chrome_DevTools_WSL2_Setup_Guide.md
├── configs/                          # ⚙️ 配置文件模板
│   └── claude-mcp-chrome-devtools.json
└── chrome-devtools-mcp/              # Chrome DevTools MCP配置目录
```

## 🛠️ 工具分类详解

### 📸 照片同步系统 (photo-sync-project/) - **[最新力作!]**

**完美的文件同步和监控解决方案！**

#### 核心脚本
- **sync_all_in_one.sh**: 一体化同步脚本，支持扁平化同步、断点续传、智能冲突处理
- **sync_monitor.sh**: 5分钟间隔监控，邮件通知，状态跟踪
- **start.sh**: 交互式启动器，一键管理所有功能
- **stop_all.sh**: 一键停止所有相关进程
- **install.sh**: 一键安装所有依赖

#### 主要特性
- ✅ **扁平化同步** - 忽略目录结构，所有文件到根目录
- ✅ **智能增量** - 只同步新文件，跳过已存在
- ✅ **断点续传** - 支持大文件暂停和继续
- ✅ **邮件通知** - 同步完成后自动发送详细报告
- ✅ **实时监控** - 每5分钟检查同步状态
- ✅ **网络存储优化** - 专门针对SMB网络存储优化

#### 快速使用
```bash
cd photo-sync-project
./install.sh          # 一键安装依赖
./start.sh            # 交互式启动器
```

### 🌐 Chrome 自动化 (chrome-automation/)

#### start-chrome-with-profile.sh
- **功能**: 在 WSL2 环境中启动带调试端口的 Chrome 浏览器
- **特性**:
  - 保持用户登录状态
  - 支持 MCP Chrome DevTools 连接
  - 自动端口冲突检测
  - 配置文件持久化
- **使用方法**: `./start-chrome-with-profile.sh`
- **端口**: 9222
- **配置目录**: `C:\ChromeDebugProfile`

### 🪟 窗口平铺工具 (spilt_screens/)

#### split3.sh / split6.sh
- **功能**: 在 Ubuntu GNOME X11 下按当前显示器自动平铺窗口
- **适用场景**:
  - 快速把 1-3 个常用窗口均分到当前屏幕
  - 将当前工作区窗口固定到 `3 列 x 2 行` 网格
  - 持续监听新窗口并补进空位
- **主要特性**:
  - 基于当前活动窗口自动锁定目标显示器
  - 只处理当前工作区、当前显示器上的普通顶层窗口
  - `split6.sh` 支持 `--daemon`、`--status`、`--stop`
  - 自动考虑 `_NET_WORKAREA`，避开 GNOME 顶栏和 Dock 保留区域
- **快速使用**:
  ```bash
  cd spilt_screens
  ./split3.sh
  ./split6.sh --daemon
  ```

### 🗣️ 小米音箱 TTS 系统 (xiaomi_tts_project/)

#### xiaomi_tts_websocket.py
- **功能**: 通过 WebSocket API 控制小米音箱进行 TTS 语音播报
- **特性**:
  - 支持多房间独立控制
  - Home Assistant 集成
  - 异步 WebSocket 通信
  - 完整的错误处理
- **支持设备**: 小米音箱 LX06 (xiaomi.wifispeaker.lx06)
- **使用方法**:
  ```python
  await xiaomi_tts_speak("你好，这是测试消息", "function_room")
  ```

### 🔒 V2Ray 代理配置 (v2ray_config/)

#### 完整的 Docker 化 V2Ray 解决方案
- **特性**:
  - 🐳 Docker 容器化隔离运行
  - 🌍 全局系统级代理支持
  - 🔄 智能路由（国内直连，国外代理）
  - 🛠️ 完整的管理脚本集合
  - 📊 状态监控和连通性测试
- **包含文件**:
  - `README.md`: 完整安装配置指南
  - `PROXY_GUIDE.md`: 详细使用说明
  - `TEST_COMMANDS.md`: 测试命令集合
- **快速开始**:
  ```bash
  ~/bin/v2ray-proxy-manager.sh on    # 一键开启代理
  ~/bin/global-connectivity-test.sh  # 完整连通性测试
  ```

### 🖼️ 图像处理 (image-processing/)

#### process_image.py
- **功能**: 将图像分割为 3x3 网格
- **特性**:
  - 自动创建输出目录
  - 生成预览拼图
  - 支持 PNG 格式输出
  - 显示处理进度和结果统计
- **使用方法**:
  ```python
  from PIL import Image
  import process_image

  img = Image.open('input.png')
  process_image.split_image_to_grid(img, 'output_directory')
  ```
- **输出**: 9个网格片段 + 1个预览图

### 💬 Ubuntu 微信自动回复 (wechat-auto-reply/)

#### 本地 X11 + Ollama 驱动的微信桌面自动化
- **功能**:
  - 自动发现微信 Linux 主窗口
  - 通过截图 + 本地视觉模型读取会话列表与消息区
  - 通过本地文本模型生成回复
  - 支持 `calibrate`、`once`、`daemon`、`pause`、`resume`、`status`
- **技术路线**:
  - `xwininfo` / `xdotool` / `xinput`
  - `ffmpeg x11grab`
  - `qwen3-vl` + `glm-4.7-flash`
- **文档**: `wechat-auto-reply/README.md`

### 📚 文档集合 (docs/)

#### Chrome_DevTools_WSL2_Setup_Guide.md
- **内容**: 完整的 Chrome DevTools + WSL2 配置指南
- **包含**: 安装步骤、使用方法、故障排除、安全注意事项
- **适用**: Claude Code MCP 集成、Web 自动化开发

### ⚙️ 配置文件模板 (configs/)

#### claude-mcp-chrome-devtools.json
- **用途**: Claude Code MCP Chrome DevTools 配置
- **支持**: Chrome 浏览器自动化和调试接口连接

## 快速开始

### Chrome 自动化环境设置

1. **运行 Chrome 调试启动脚本**:
   ```bash
   cd /home/ivan/DevToolbox/chrome-automation/
   ./start-chrome-with-profile.sh
   ```

2. **验证连接**:
   ```bash
   curl -s http://localhost:9222/json/version
   ```

3. **在 Claude Code 中使用**:
   ```
   mcp__chrome-devtools__new_page
   url: "https://example.com"
   ```

## Claude Code MCP 配置

### 当前配置
```json
"mcpServers": {
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
}
```

### 安装指令替代方案
```bash
claude mcp install chrome-devtools-mcp@latest
```

## 使用流程

1. **启动 Chrome 调试模式**
   ```bash
   ./chrome-automation/start-chrome-with-profile.sh
   ```

2. **使用 Claude Code MCP 工具进行自动化操作**
   - 打开网页
   - 填写表单
   - 点击元素
   - 执行 JavaScript

3. **完成后关闭浏览器**

## 🚀 快速开始指南

### 📸 照片同步系统 (推荐)
```bash
cd photo-sync-project
./install.sh          # 一键安装依赖
./start.sh            # 交互式启动器
```

### 🌐 Chrome 自动化环境设置

1. **运行 Chrome 调试启动脚本**:
   ```bash
   cd chrome-automation/
   ./start-chrome-with-profile.sh
   ```

### 🪟 窗口平铺工具

```bash
cd spilt_screens
./split3.sh --dry-run
./split6.sh
./split6.sh --daemon
```

2. **验证连接**:
   ```bash
   curl -s http://localhost:9222/json/version
   ```

3. **在 Claude Code 中使用**:
   ```
   mcp__chrome-devtools__new_page
   url: "https://example.com"
   ```

### 🔒 V2Ray 代理设置
```bash
cd v2ray_config/
# 按照 README.md 进行配置
~/bin/v2ray-proxy-manager.sh on    # 一键开启代理
~/bin/global-connectivity-test.sh  # 测试连通性
```

### 🗣️ 小米 TTS 语音播报
```bash
cd xiaomi_tts_project/
python3 xiaomi_tts_websocket.py    # 运行演示
```

## 🔧 Claude Code MCP 配置

### Chrome DevTools 集成
```json
"mcpServers": {
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
}
```

### 安装指令替代方案
```bash
claude mcp install chrome-devtools-mcp@latest
```

## 🎨 项目特色

### 💎 设计理念
- **完美主义**: 每个工具都追求极致的代码质量和用户体验
- **实用导向**: 解决实际开发中的具体问题
- **自动化**: 最大化减少人工操作，提高效率
- **模块化**: 每个项目独立完整，可单独使用

### 👑 技术亮点
- **跨平台兼容**: WSL2、Linux、Docker 环境支持
- **异步编程**: Python asyncio、WebSocket 异步通信
- **系统集成**: 深度集成系统服务和管理工具
- **错误处理**: 完善的异常处理和恢复机制
- **文档完整**: 每个项目都有详细的使用文档

## 📈 统计信息

### 项目规模
- **总项目数**: 6个主要项目模块
- **代码行数**: 3000+ 行高质量代码
- **支持语言**: Bash、Python、JSON、Markdown
- **文档覆盖率**: 100% (每个项目都有详细文档)

### 技术栈
- **编程语言**: Bash、Python 3
- **容器化**: Docker
- **网络协议**: WebSocket、HTTP、SOCKS5
- **版本控制**: Git
- **编辑器**: VS Code、Claude Code

## 🔮 未来计划

### 即将添加的工具 🚧
- [ ] **API 测试框架** - 自动化 API 接口测试
- [ ] **系统监控面板** - 实时系统资源监控
- [ ] **代码生成器** - 基于模板的代码生成工具
- [ ] **日志分析器** - 智能日志分析和异常检测
- [ ] **部署自动化** - CI/CD 管道配置脚本

### 配置模板扩展 📋
- [ ] **Docker Compose** 模板集合
- [ ] **Kubernetes** 部署配置
- [ ] **Nginx** 反向代理配置
- [ ] **Git Hooks** 自动化脚本
- [ ] **VS Code** 工作区配置

### 生态系统集成 🌐
- [ ] **Home Assistant** 更多设备集成
- [ ] **CI/CD** 流水线模板
- [ ] **云服务** 自动化部署脚本

## 🤝 贡献指南

### 参与方式
1. **Fork** 本仓库到你的 GitHub
2. **创建** 功能分支 (`git checkout -b feature/amazing-feature`)
3. **提交** 你的更改 (`git commit -m 'Add some amazing feature'`)
4. **推送** 到分支 (`git push origin feature/amazing-feature`)
5. **创建** Pull Request

### 开发规范
- **代码风格**: 遵循项目现有代码风格
- **文档要求**: 每个新功能都要有详细说明
- **测试要求**: 确保功能正常工作
- **提交信息**: 使用清晰的 commit 信息

### 目录命名规范
- 使用小写字母和连字符 (`kebab-case`)
- 按功能分类组织
- 保持目录结构清晰
- 每个项目都要有 README.md

## 📝 版本历史

### v2.0.0 (2025-12-20) - **重大更新**
- ✅ 新增 **照片同步系统** (完整的一体化解决方案)
- ✅ 新增 **小米音箱 TTS 系统** (WebSocket 语音播报)
- ✅ 新增 **V2Ray Docker 配置** (完整代理解决方案)
- ✅ 新增 **X11 窗口平铺脚本** (`split3.sh` / `split6.sh`)
- 📝 重构根目录 README，完善项目文档
- 🎨 统一项目风格和代码规范

### v1.1.0 (2025-10-24)
- ✅ 添加 V2Ray Docker 配置方案
- ✅ 完善代理管理和测试工具
- 📚 更新文档和配置模板

### v1.0.0 (2025-09-27)
- ✅ 初始版本发布
- ✅ 添加 Chrome 自动化工具
- ✅ 添加图像处理工具
- ✅ 添加 Chrome DevTools WSL2 配置指南

## 📄 许可证

本项目采用 **MIT 许可证**，详见 [LICENSE](LICENSE) 文件。

## 👨‍💻 联系信息

**维护者**: Ivan (redyuan43@gmail.com)
**创建时间**: 2025-09-27
**最后更新**: 2025-12-20
**项目主页**: [GitHub Repository](https://github.com/redyuan43/DevToolbox)

## 🙏 致谢

> 本工具库集合了多年开发经验和对完美代码的追求。每一个工具都经过实际使用验证，每一个细节都经过精心打磨。
>
> *感谢所有为开源社区做出贡献的开发者们！*
>
> *—— 哈雷酱大小小姐的完美代码工作室 (*/ω＼*)*

---

⭐ **如果这个项目对你有帮助，请给个 Star 支持一下！**
🔄 **欢迎 Fork 和分享给更多的开发者！**
