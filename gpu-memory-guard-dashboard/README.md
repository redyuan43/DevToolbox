# GPU Memory Guard Dashboard

本地 Web 页面，用于查看 `spark`、`edge`、`AMD`、`ivan` 上的 `gpu-memory-guard.service` 状态。

## 启动

```bash
cd /home/dgx/github/DevToolbox/gpu-memory-guard-dashboard
./start.sh
```

默认地址：

```text
http://127.0.0.1:8765
```

## 页面内容

- systemd 状态：`active` / `enabled`
- 系统内存占用
- NVIDIA / AMD GPU 内存占用
- 守护进程启动时间、PID、阈值
- 最近 24 小时触发处理记录：`victim`、`SIGTERM`、`SIGKILL`
- 最近 24 小时白名单保护记录：`skip protected`

## 配置

```bash
GPU_GUARD_DASHBOARD_PORT=8766 ./start.sh
GPU_GUARD_DASHBOARD_HOST=0.0.0.0 ./start.sh
```

## 守护服务脚本

`daemon/` 目录保存了当前部署到各机器的 root systemd 守护脚本：

- `daemon/gpu-memory-guard.py`
- `daemon/install-gpu-memory-guard.sh`

单机安装：

```bash
cd /home/dgx/github/DevToolbox/gpu-memory-guard-dashboard
./daemon/install-gpu-memory-guard.sh
```

验证：

```bash
python3 -m py_compile daemon/gpu-memory-guard.py
bash -n daemon/install-gpu-memory-guard.sh
python3 -m unittest tests/test_gpu_memory_guard.py -v
```
