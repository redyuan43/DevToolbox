# 网络SSH扫描器

一个快速扫描局域网内SSH设备的工具，支持命令行和Web界面两种使用方式。

## 功能特点

- 快速扫描指定网段的设备
- 检测SSH端口开放状态
- 尝试SSH登录验证
- 支持命令行和Web界面
- 使用ARP表优化扫描速度

## 安装

1. 克隆或下载项目代码

2. 安装Python依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

### 方法1：命令行扫描

#### 基础版扫描器
```bash
python network_scanner.py -u 用户名 -p 密码 [-n 网段]

# 示例
python network_scanner.py -u admin -p password123
python network_scanner.py -u root -p root -n 192.168.1.0/24
```

#### 快速版扫描器（ARP优化）
```bash
python fast_network_scanner.py -u 用户名 -p 密码 [-n 网段]

# 示例
python fast_network_scanner.py -u admin -p password123
python fast_network_scanner.py -u root -p root -n 10.0.0.0/24
```

参数说明：
- `-u, --username`: SSH登录用户名（必需）
- `-p, --password`: SSH登录密码（必需）
- `-n, --network`: 要扫描的网络段，CIDR格式（默认: 192.168.100.0/24）

### 方法2：Web界面

1. 启动Web服务：
```bash
python web_scanner.py
```

2. 打开浏览器访问：
```
http://localhost:5000
```

3. 在Web界面中输入：
   - 网络段（如 192.168.1.0/24）
   - SSH用户名
   - SSH密码

4. 点击"开始扫描"按钮

## 文件说明

- `network_scanner.py` - 基础版命令行扫描器
- `fast_network_scanner.py` - 快速版命令行扫描器（使用ARP表优化）
- `web_scanner.py` - Flask Web应用服务器
- `templates/index.html` - Web界面HTML模板
- `requirements.txt` - Python依赖包列表

## 注意事项

1. 需要管理员/root权限来执行ping和读取ARP表
2. 确保目标设备开启了SSH服务（默认端口22）
3. 扫描大网段时可能需要较长时间
4. 请仅在您有权限的网络中使用此工具

## 依赖要求

- Python 3.6+
- paramiko - SSH连接库
- Flask - Web框架
- flask-cors - 跨域支持

## 安全提示

- 请勿在未授权的网络中使用此工具
- 建议使用强密码保护SSH服务
- 扫描活动可能被网络监控系统检测到