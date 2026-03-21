# setup_ollama

这个目录包含两个脚本，用于将 Ollama 固定到指定 GPU，以及回滚该配置。

## 文件说明

### `set_ollama_gpu_to_v100.sh`

- 作用：为 `ollama.service` 写入 systemd drop-in 配置，设置 `CUDA_VISIBLE_DEVICES`
- 默认目标：`GPU-4c63c711-9570-75db-760d-c6679c760754`（本机的 Tesla V100）
- 实现方式：创建 `/etc/systemd/system/ollama.service.d/10-gpu-selection.conf`
- 生效动作：执行 `systemctl daemon-reload` 和 `systemctl restart ollama`

用法：

```bash
./set_ollama_gpu_to_v100.sh
```

如果你后续想改成别的 GPU，可以把目标 GPU UUID 作为第一个参数传入：

```bash
./set_ollama_gpu_to_v100.sh "GPU-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### `rollback_ollama_gpu_selection.sh`

- 作用：删除上述 drop-in 配置文件，恢复 Ollama 默认的 GPU 可见性
- 删除文件：`/etc/systemd/system/ollama.service.d/10-gpu-selection.conf`
- 生效动作：执行 `systemctl daemon-reload` 和 `systemctl restart ollama`

用法：

```bash
./rollback_ollama_gpu_selection.sh
```

## 验证方式

应用脚本后，可用下面的命令检查 Ollama 是否只使用目标 GPU：

```bash
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
```

如果配置正确，`/usr/local/bin/ollama` 应只出现在目标 GPU UUID 上。
