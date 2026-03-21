#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import threading
import sys
import io
from contextlib import redirect_stdout
import time

# 导入现有的扫描器模块
import network_scanner
import fast_network_scanner

app = Flask(__name__)
CORS(app)

# 全局变量存储扫描状态
scan_status = {
    'running': False,
    'type': '',
    'output': '',
    'complete': False
}

class OutputCapture:
    def __init__(self):
        self.output = ""

    def write(self, text):
        self.output += text
        # 实时更新全局状态
        scan_status['output'] = self.output
        return len(text)

    def flush(self):
        pass

def capture_scan_output(scan_func, *args):
    """捕获扫描函数的输出"""
    global scan_status

    # 创建自定义输出捕获器
    output_capture = OutputCapture()

    # 重定向stdout到我们的捕获器
    original_stdout = sys.stdout
    sys.stdout = output_capture

    try:
        scan_func(*args)
        scan_status['complete'] = True
    except Exception as e:
        print(f"\n错误: {str(e)}")
        scan_status['complete'] = True
    finally:
        # 恢复原始stdout
        sys.stdout = original_stdout
        scan_status['running'] = False

def run_normal_scan(network, username, password):
    """运行普通扫描"""
    global scan_status
    scan_status['running'] = True
    scan_status['type'] = 'normal'
    scan_status['output'] = '正在启动普通扫描...\n'
    scan_status['complete'] = False

    # 在新线程中运行扫描
    thread = threading.Thread(
        target=capture_scan_output,
        args=(network_scanner.scan_network, network, username, password)
    )
    thread.daemon = True
    thread.start()

def run_fast_scan(network, username, password):
    """运行快速扫描"""
    global scan_status
    scan_status['running'] = True
    scan_status['type'] = 'fast'
    scan_status['output'] = '正在启动快速扫描（ARP优化版）...\n'
    scan_status['complete'] = False

    # 在新线程中运行扫描
    thread = threading.Thread(
        target=capture_scan_output,
        args=(fast_network_scanner.fast_scan_network, network, username, password)
    )
    thread.daemon = True
    thread.start()

@app.route('/')
def index():
    return render_template('scan.html')

@app.route('/api/scan/normal', methods=['POST'])
def normal_scan():
    """普通扫描API"""
    if scan_status['running']:
        return jsonify({'error': '扫描正在进行中'}), 400

    data = request.json
    network = data.get('network', '192.168.100.0/24')
    username = data.get('username', '')
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '请提供用户名和密码'}), 400

    run_normal_scan(network, username, password)

    return jsonify({'message': '普通扫描已开始', 'type': 'normal'})

@app.route('/api/scan/fast', methods=['POST'])
def fast_scan():
    """快速扫描API"""
    if scan_status['running']:
        return jsonify({'error': '扫描正在进行中'}), 400

    data = request.json
    network = data.get('network', '192.168.100.0/24')
    username = data.get('username', '')
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '请提供用户名和密码'}), 400

    run_fast_scan(network, username, password)

    return jsonify({'message': '快速扫描已开始', 'type': 'fast'})

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取扫描状态"""
    return jsonify(scan_status)

@app.route('/api/stop', methods=['POST'])
def stop_scan():
    """停止扫描"""
    scan_status['running'] = False
    scan_status['complete'] = True
    return jsonify({'message': '扫描已停止'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)