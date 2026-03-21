#!/usr/bin/env python3
import subprocess
import re
import ipaddress
import socket
import paramiko
import concurrent.futures
import sys
import argparse
from datetime import datetime
import platform

def get_arp_table():
    """获取ARP表中的所有设备"""
    devices = []

    try:
        # 根据操作系统选择命令
        system = platform.system()

        if system == "Linux":
            # Linux系统使用 arp -n 或 ip neigh
            try:
                # 尝试使用 ip neigh（更现代的方式）
                result = subprocess.run(['ip', 'neigh'], capture_output=True, text=True, timeout=5)
                output = result.stdout

                # 解析 ip neigh 输出
                # 格式: 192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
                for line in output.split('\n'):
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+).*lladdr\s+([0-9a-fA-F:]+)\s+(\w+)', line)
                    if match:
                        ip = match.group(1)
                        mac = match.group(2)
                        state = match.group(3)
                        # 只添加可达的设备
                        if state in ['REACHABLE', 'STALE', 'DELAY', 'PROBE']:
                            devices.append({'ip': ip, 'mac': mac, 'state': state})
            except:
                # 如果 ip neigh 失败，尝试传统的 arp 命令
                result = subprocess.run(['arp', '-n'], capture_output=True, text=True, timeout=5)
                output = result.stdout

                # 解析 arp -n 输出
                for line in output.split('\n'):
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+).*\s+([0-9a-fA-F:]+)\s+', line)
                    if match:
                        ip = match.group(1)
                        mac = match.group(2)
                        devices.append({'ip': ip, 'mac': mac, 'state': 'UNKNOWN'})

        elif system == "Windows":
            # Windows系统使用 arp -a
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, shell=True, timeout=5)
            output = result.stdout

            # 解析 Windows arp -a 输出
            for line in output.split('\n'):
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]+)', line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2).replace('-', ':')
                    devices.append({'ip': ip, 'mac': mac, 'state': 'UNKNOWN'})

    except Exception as e:
        print(f"获取ARP表失败: {e}")

    return devices

def ping_sweep(network_str):
    """使用ping快速扫描网段，填充ARP表"""
    try:
        network = ipaddress.ip_network(network_str)
        system = platform.system()

        print(f"正在进行ping扫描以填充ARP表...")

        # 使用并发ping来快速填充ARP表
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = []
            for ip in network.hosts():
                if system == "Linux":
                    # Linux: ping 一次，超时0.1秒
                    cmd = ['ping', '-c', '1', '-W', '0.1', str(ip)]
                elif system == "Windows":
                    # Windows: ping 一次，超时100毫秒
                    cmd = ['ping', '-n', '1', '-w', '100', str(ip)]
                else:
                    cmd = ['ping', '-c', '1', str(ip)]

                future = executor.submit(subprocess.run, cmd,
                                       capture_output=True,
                                       timeout=0.2)
                futures.append(future)

            # 等待所有ping完成（不关心结果，只是为了填充ARP表）
            for future in futures:
                try:
                    future.result()
                except:
                    pass

    except Exception as e:
        print(f"Ping扫描出错: {e}")

def check_ssh_port(ip, timeout=0.5):
    """快速检查SSH端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, 22))
        sock.close()
        return result == 0
    except:
        return False

def try_ssh_connection(ip, username, password, timeout=3):
    """尝试SSH连接"""
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

        client.close()
        return True, hostname
    except paramiko.AuthenticationException:
        return False, "认证失败"
    except Exception as e:
        return False, f"连接失败: {str(e)}"

def fast_scan_network(network_str, username, password):
    """使用ARP表快速扫描网络"""
    print("=" * 60)
    print("快速网络SSH扫描（ARP优化版）")
    print("=" * 60)
    print(f"使用账号: {username}, 密码: {'*' * len(password)}")
    print("-" * 60)

    # 第一步：Ping扫描填充ARP表
    ping_sweep(network_str)

    # 第二步：获取ARP表
    print("\n从ARP表获取设备列表...")
    arp_devices = get_arp_table()

    if not arp_devices:
        print("ARP表为空，使用传统扫描方式...")
        return

    print(f"ARP表中发现 {len(arp_devices)} 个设备")
    print("-" * 60)

    # 过滤出目标网段的设备
    network = ipaddress.ip_network(network_str)
    target_devices = []
    for device in arp_devices:
        try:
            ip_obj = ipaddress.ip_address(device['ip'])
            if ip_obj in network:
                target_devices.append(device)
                print(f"  ✓ 发现设备: {device['ip']} (MAC: {device['mac']}) - {device['state']}")
        except:
            pass

    if not target_devices:
        print(f"在网段 {network_str} 中没有发现设备")
        return

    print(f"\n在目标网段发现 {len(target_devices)} 个设备")
    print("-" * 60)

    # 第三步：检查SSH端口
    print("\n检查SSH端口...")
    ssh_hosts = []

    for device in target_devices:
        ip = device['ip']
        if check_ssh_port(ip):
            ssh_hosts.append(ip)
            print(f"  ✓ SSH端口开放: {ip}")

    if not ssh_hosts:
        print("\n没有发现开放SSH端口的设备")
        return

    print(f"\n发现 {len(ssh_hosts)} 个开放SSH端口的设备")
    print("-" * 60)

    # 第四步：尝试SSH连接
    print("\n尝试SSH连接...")
    successful_connections = []

    for ip in ssh_hosts:
        print(f"  尝试连接 {ip}...", end=" ")
        success, info = try_ssh_connection(ip, username, password)

        if success:
            print(f"✓ 成功! 主机名: {info}")
            successful_connections.append((ip, info))
        else:
            print(f"✗ 失败 ({info})")

    # 显示结果
    print("\n" + "=" * 60)
    print("扫描完成！")
    print("=" * 60)

    if successful_connections:
        print(f"\n成功连接的设备 ({len(successful_connections)} 个):")
        for ip, hostname in successful_connections:
            print(f"  • {ip} - 主机名: {hostname}")
    else:
        print("\n没有找到可以用提供的账号密码连接的设备")

def main():
    parser = argparse.ArgumentParser(description='快速网络SSH扫描工具（ARP优化版）')
    parser.add_argument('-u', '--username', type=str, required=True,
                        help='SSH登录用户名')
    parser.add_argument('-p', '--password', type=str, required=True,
                        help='SSH登录密码')
    parser.add_argument('-n', '--network', type=str, default='192.168.100.0/24',
                        help='要扫描的网络段 (默认: 192.168.100.0/24)')

    args = parser.parse_args()

    print(f"扫描网段: {args.network}")
    print()

    start_time = datetime.now()
    fast_scan_network(args.network, args.username, args.password)

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\n总耗时: {duration}")

if __name__ == "__main__":
    main()