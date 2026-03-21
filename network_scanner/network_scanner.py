#!/usr/bin/env python3
import ipaddress
import socket
import paramiko
import concurrent.futures
import sys
import argparse
from datetime import datetime
import time

def get_local_network():
    """获取本地网络信息"""
    # 扫描 192.168.100.0/24 网段
    local_ip = "192.168.100.1"  # 假设的本地IP
    network = "192.168.100.0/24"  # /24 子网 (192.168.100.0 - 192.168.100.255)
    return local_ip, network

def is_host_alive(ip, timeout=1):
    """检查主机是否在线（通过socket连接测试）"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((str(ip), 22))  # 测试SSH端口
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
            str(ip),
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
    except paramiko.SSHException as e:
        return False, f"SSH错误: {str(e)}"
    except socket.timeout:
        return False, "连接超时"
    except Exception as e:
        return False, f"错误: {str(e)}"

def scan_network(network_str, username, password):
    """扫描网络中的所有IP"""
    print(f"开始扫描网络: {network_str}")
    print(f"使用账号: {username}, 密码: {'*' * len(password)}")
    print("-" * 60)

    network = ipaddress.ip_network(network_str)
    total_ips = network.num_addresses
    print(f"总共需要扫描 {total_ips} 个IP地址")
    print("-" * 60)

    # 第一步：并发扫描开放SSH端口的主机
    print("\n第一步：扫描SSH端口开放的主机...")
    alive_hosts = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(is_host_alive, ip): ip for ip in network.hosts()}

        for future in concurrent.futures.as_completed(futures):
            ip = futures[future]
            try:
                if future.result():
                    alive_hosts.append(ip)
                    print(f"✓ 发现SSH端口开放: {ip}")
            except Exception:
                pass

    print(f"\n发现 {len(alive_hosts)} 个开放SSH端口的主机")
    print("-" * 60)
    
    # 第二步：尝试SSH连接
    if alive_hosts:
        print("\n第二步：尝试SSH连接...")
        successful_connections = []

        for ip in alive_hosts:
            print(f"尝试连接 {ip}...", end=" ")
            success, info = try_ssh_connection(ip, username, password)

            if success:
                print(f"✓ 成功! 主机名: {info}")
                successful_connections.append((ip, info))
            else:
                print(f"✗ 失败 ({info})")
        
        # 显示结果总结
        print("\n" + "=" * 60)
        print("扫描完成！")
        print("=" * 60)
        
        if successful_connections:
            print(f"\n成功连接的设备 ({len(successful_connections)} 个):")
            for ip, hostname in successful_connections:
                print(f"  • {ip} - 主机名: {hostname}")
        else:
            print("\n没有找到可以用提供的账号密码连接的设备")
    else:
        print("\n没有发现开放SSH端口的主机")

def main():
    parser = argparse.ArgumentParser(description='网络SSH扫描工具')
    parser.add_argument('-u', '--username', type=str, required=True,
                        help='SSH登录用户名')
    parser.add_argument('-p', '--password', type=str, required=True,
                        help='SSH登录密码')
    parser.add_argument('-n', '--network', type=str, default='192.168.100.0/24',
                        help='要扫描的网络段 (默认: 192.168.100.0/24)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("网络SSH扫描工具")
    print("=" * 60)
    
    try:
        local_ip, _ = get_local_network()
        network = args.network
        print(f"本地IP地址: {local_ip}")
        print(f"扫描网络段: {network}")
        print()
        
        start_time = datetime.now()
        scan_network(network, args.username, args.password)
        
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"\n总耗时: {duration}")
        
    except KeyboardInterrupt:
        print("\n\n扫描被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
