# DevToolbox - 开发工具库

个人收集的各种开发脚本、工具和配置文件集合。

## 目录结构

```
DevToolbox/
├── README.md                    # 本文件
├── chrome-automation/           # Chrome 自动化工具
│   └── start-chrome-with-profile.sh
├── docs/                       # 文档集合
│   └── Chrome_DevTools_WSL2_Setup_Guide.md
└── configs/                    # 配置文件模板
```

## 工具分类

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

### 📚 文档 (docs/)

#### Chrome_DevTools_WSL2_Setup_Guide.md
- **内容**: 完整的 Chrome DevTools + WSL2 配置指南
- **包含**: 安装步骤、使用方法、故障排除、安全注意事项
- **适用**: Claude Code MCP 集成、Web 自动化

### ⚙️ 配置文件 (configs/)
*待添加更多配置模板*

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

## 扩展计划

### 计划添加的工具
- [ ] 数据库连接脚本
- [ ] API 测试工具
- [ ] 日志分析脚本
- [ ] 系统监控工具
- [ ] 代码生成模板

### 配置模板计划
- [ ] Docker 配置模板
- [ ] Nginx 配置模板
- [ ] Git 钩子脚本
- [ ] VS Code 配置模板

## 贡献指南

### 添加新工具
1. 在相应目录下添加脚本/配置
2. 更新本 README 文档
3. 添加使用说明和示例

### 目录命名规范
- 使用小写字母和连字符
- 按功能分类组织
- 保持目录结构清晰

## 版本历史

### v1.0.0 (2025-09-27)
- 初始版本
- 添加 Chrome 自动化工具
- 添加 Chrome DevTools WSL2 配置指南

## 许可证

个人使用工具库，仅供学习和开发使用。

## 联系信息

维护者: Ivan
创建时间: 2025-09-27
最后更新: 2025-09-27