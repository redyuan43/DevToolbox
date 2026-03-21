#!/bin/bash

echo "================================"
echo "网络SSH扫描器 - Web服务"
echo "================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查并安装依赖
echo "检查依赖..."
if ! python3 -c "import paramiko" 2>/dev/null; then
    echo "安装依赖包..."
    pip3 install -r requirements.txt || pip install -r requirements.txt
fi

echo ""
echo "启动Web服务..."
echo "访问地址: http://localhost:5000"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================"
echo ""

# 启动Flask应用
python3 web_scanner.py