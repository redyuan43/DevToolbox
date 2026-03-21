#!/usr/bin/env python3
from flask import Flask, render_template, Response, request, jsonify
import json
import ipaddress
import socket
import paramiko
import threading
import time
from datetime import datetime
import queue
import subprocess
import re
import platform
import concurrent.futures

app = Flask(__name__)

# 全局变量控制扫描状态
scan_thread = None
stop_scanning = False
scan_queue = queue.Queue()

def get_arp_devices():
    """获取ARP表中的设备"""
    devices = []
    
    try:
        system = platform.system()
        
        if system == "Linux":
            # 使用 ip neigh 获取ARP表
            result = subprocess.run(['ip', 'neigh'], capture_output=True, text=True, timeout=5)
            output = result.stdout
            
            for line in output.split('\n'):
                match = re.search(r'(\d+\.\d+\.\d+\.\d+).*lladdr\s+([0-9a-fA-F:]+)\s+(\w+)', line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2)
                    state = match.group(3)
                    if state in ['REACHABLE', 'STALE', 'DELAY', 'PROBE']:
                        devices.append({'ip': ip, 'mac': mac})
        elif system == "Windows":
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, shell=True, timeout=5)
            output = result.stdout
            
            for line in output.split('\n'):
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]+)', line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2).replace('-', ':')
                    devices.append({'ip': ip, 'mac': mac})
    except:
        pass
    
    return devices

def ping_sweep_fast(network):
    """快速ping扫描填充ARP表"""
    system = platform.system()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = []
        for ip in network.hosts():
            if system == "Linux":
                cmd = ['ping', '-c', '1', '-W', '0.1', str(ip)]
            elif system == "Windows":
                cmd = ['ping', '-n', '1', '-w', '100', str(ip)]
            else:
                cmd = ['ping', '-c', '1', str(ip)]
            
            future = executor.submit(subprocess.run, cmd, capture_output=True, timeout=0.2)
            futures.append((ip, future))
        
        # 不等待结果，只是触发ping
        for ip, future in futures:
            try:
                future.result()
            except:
                pass

def check_host_alive(ip, timeout=0.5):
    """检查主机是否在线（通过ping）"""
    system = platform.system()
    
    try:
        if system == "Linux":
            cmd = ['ping', '-c', '1', '-W', '1', ip]
        elif system == "Windows":
            cmd = ['ping', '-n', '1', '-w', '1000', ip]
        else:
            cmd = ['ping', '-c', '1', ip]
        
        result = subprocess.run(cmd, capture_output=True, timeout=2)
        return result.returncode == 0
    except:
        return False

def scan_network_task(network_str, username, password):
    """后台扫描任务 - 扫描所有可ping通的主机"""
    global stop_scanning
    
    try:
        network = ipaddress.ip_network(network_str)
        
        # 发送初始状态
        scan_queue.put({
            'type': 'progress',
            'progress': 0,
            'message': f'开始扫描网络: {network_str}',
            'stats': {'total_scanned': 0, 'alive_hosts': 0, 'ssh_hosts': 0}
        })
        
        # 第一步：快速ping扫描找出所有在线主机
        scan_queue.put({
            'type': 'progress',
            'progress': 5,
            'message': '正在进行ping扫描，查找在线主机...',
            'stats': {'total_scanned': 0, 'alive_hosts': 0, 'ssh_hosts': 0}
        })
        
        alive_hosts = []
        total_ips = sum(1 for _ in network.hosts())
        scanned = 0
        
        # 并发ping扫描
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(check_host_alive, str(ip)): str(ip) 
                      for ip in network.hosts()}
            
            for future in concurrent.futures.as_completed(futures):
                if stop_scanning:
                    break
                    
                ip = futures[future]
                scanned += 1
                
                try:
                    if future.result():
                        alive_hosts.append(ip)
                        scan_queue.put({
                            'type': 'host_found',
                            'ip': ip,
                            'alive_count': len(alive_hosts)
                        })
                except:
                    pass
                
                # 更新进度
                if scanned % 10 == 0 or scanned == total_ips:
                    progress = 5 + int((scanned / total_ips) * 25)  # 5-30%
                    scan_queue.put({
                        'type': 'progress',
                        'progress': progress,
                        'message': f'Ping扫描中... {scanned}/{total_ips}',
                        'stats': {'total_scanned': scanned, 'alive_hosts': len(alive_hosts), 'ssh_hosts': 0}
                    })
        
        if stop_scanning:
            scan_queue.put({'type': 'complete', 'duration': '扫描已停止'})
            return
        
        if not alive_hosts:
            scan_queue.put({
                'type': 'complete',
                'duration': '未发现在线主机'
            })
            return
        
        # 第二步：对所有在线主机进行端口扫描
        scan_queue.put({
            'type': 'progress',
            'progress': 30,
            'message': f'发现 {len(alive_hosts)} 个在线主机，开始扫描端口...',
            'stats': {'total_scanned': total_ips, 'alive_hosts': len(alive_hosts), 'ssh_hosts': 0}
        })
        
        ssh_capable_hosts = []
        
        for i, ip in enumerate(alive_hosts):
            if stop_scanning:
                break
            
            # 扫描端口
            open_ports = scan_ports(ip)
            
            # 检查是否有SSH端口
            has_ssh = any(p['port'] == 22 for p in open_ports)
            
            # 如果有SSH，尝试连接
            ssh_info = None
            if has_ssh:
                ssh_capable_hosts.append(ip)
                success, info = try_ssh_connection(ip, username, password)
                if success:
                    ssh_info = {
                        'connected': True,
                        'hostname': info['hostname'],
                        'os_info': info['os_info']
                    }
                else:
                    ssh_info = {
                        'connected': False,
                        'error': info
                    }
            
            # 发送主机扫描结果
            scan_queue.put({
                'type': 'host_scan_result',
                'ip': ip,
                'open_ports': open_ports,
                'has_ssh': has_ssh,
                'ssh_info': ssh_info,
                'ssh_count': len(ssh_capable_hosts)
            })
            
            # 更新进度
            progress = 30 + int(((i + 1) / len(alive_hosts)) * 70)  # 30-100%
            scan_queue.put({
                'type': 'progress',
                'progress': progress,
                'message': f'扫描端口... {i+1}/{len(alive_hosts)} 个主机',
                'stats': {'total_scanned': total_ips, 'alive_hosts': len(alive_hosts), 'ssh_hosts': len(ssh_capable_hosts)}
            })
        
        # 扫描完成
        scan_queue.put({
            'type': 'complete',
            'duration': '扫描完成',
            'summary': {
                'total_scanned': total_ips,
                'alive_hosts': len(alive_hosts),
                'ssh_hosts': len(ssh_capable_hosts)
            }
        })
        
    except Exception as e:
        scan_queue.put({
            'type': 'error',
            'message': str(e)
        })

def is_host_alive(ip, timeout=1):
    """检查主机是否在线"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, 22))
        sock.close()
        return result == 0
    except:
        return False

def scan_ports(ip, port_list=None, timeout=0.5):
    """扫描指定主机的常用端口"""
    if port_list is None:
        # 常用端口列表
        port_list = [
            (21, 'FTP'),
            (22, 'SSH'),
            (23, 'Telnet'),
            (25, 'SMTP'),
            (53, 'DNS'),
            (80, 'HTTP'),
            (110, 'POP3'),
            (143, 'IMAP'),
            (443, 'HTTPS'),
            (445, 'SMB'),
            (3306, 'MySQL'),
            (5432, 'PostgreSQL'),
            (6379, 'Redis'),
            (8080, 'HTTP-Proxy'),
            (8443, 'HTTPS-Alt'),
            (27017, 'MongoDB'),
            (3389, 'RDP'),
            (5900, 'VNC'),
        ]
    
    open_ports = []
    for port, service in port_list:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                open_ports.append({'port': port, 'service': service})
        except:
            pass
    return open_ports

def try_ssh_connection(ip, username, password, timeout=3):
    """尝试SSH连接并获取系统信息"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        client.connect(
            ip,
            port=22,
            username=username,
            password=password,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout
        )
        
        # 获取主机名
        stdin, stdout, stderr = client.exec_command("hostname", timeout=2)
        hostname = stdout.read().decode().strip()
        
        # 获取操作系统信息
        os_info = "Unknown"
        try:
            # 尝试获取Linux系统信息
            stdin, stdout, stderr = client.exec_command("cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'", timeout=2)
            os_output = stdout.read().decode().strip()
            if os_output:
                os_info = os_output
            else:
                # 尝试uname
                stdin, stdout, stderr = client.exec_command("uname -a", timeout=2)
                os_info = stdout.read().decode().strip()[:50]  # 限制长度
        except:
            pass
        
        client.close()
        return True, {'hostname': hostname, 'os_info': os_info}
    except paramiko.AuthenticationException:
        return False, "认证失败"
    except paramiko.SSHException as e:
        return False, f"SSH错误"
    except socket.timeout:
        return False, "连接超时"
    except Exception as e:
        return False, f"连接错误"

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/scan')
def scan():
    """启动扫描并返回Server-Sent Events流"""
    global scan_thread, stop_scanning, scan_queue
    
    network = request.args.get('network', '192.168.100.0/24')
    username = request.args.get('username', 'nano')
    password = request.args.get('password', 'nano')
    
    # 清空队列
    while not scan_queue.empty():
        scan_queue.get()
    
    # 重置停止标志
    stop_scanning = False
    
    # 启动扫描线程
    scan_thread = threading.Thread(
        target=scan_network_task,
        args=(network, username, password)
    )
    scan_thread.daemon = True
    scan_thread.start()
    
    def generate():
        """生成SSE事件流"""
        while True:
            try:
                # 从队列获取消息（超时1秒）
                message = scan_queue.get(timeout=1)
                yield f"data: {json.dumps(message)}\n\n"
                
                # 如果扫描完成，结束流
                if message.get('type') in ['complete', 'error']:
                    break
            except queue.Empty:
                # 发送心跳包保持连接
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                
                # 检查线程是否还在运行
                if scan_thread and not scan_thread.is_alive():
                    yield f"data: {json.dumps({'type': 'complete', 'duration': '扫描完成'})}\n\n"
                    break
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/stop', methods=['POST'])
def stop():
    """停止扫描"""
    global stop_scanning
    stop_scanning = True
    return jsonify({'status': 'stopped'})

if __name__ == '__main__':
    print("=" * 60)
    print("网络SSH扫描器 Web服务")
    print("=" * 60)
    print("访问地址: http://localhost:5000")
    print("或者: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)