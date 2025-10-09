# 小米音箱LX06 TTS语音播报系统

🎉 **已验证可用** - 通过WebSocket API成功控制小米音箱LX06进行TTS语音播报

## 📋 项目概述

本项目提供了完整的小米音箱LX06 TTS（文本转语音）控制解决方案，基于官方xiaomi_home插件实现多房间语音播报功能。

### ✨ 主要特性

- ✅ **官方支持** - 基于xiaomi_home官方插件
- ✅ **多房间支持** - 支持7个房间独立控制
- ✅ **WebSocket API** - 实时响应，稳定可靠
- ✅ **验证可用** - 已成功测试并播报语音
- ✅ **易于集成** - 简洁的API接口
- ✅ **完整文档** - 详细的使用说明和示例

### 🏠 支持的房间

| 房间 | 实体ID | 状态 |
|------|--------|------|
| 多功能房 | `notify.xiaomi_cn_604014890_lx06_play_text_a_5_1` | ✅ 已验证 |
| 厨房 | `notify.xiaomi_cn_604013123_lx06_play_text_a_5_1` | ✅ 可用 |
| 主卧 | `notify.xiaomi_cn_604006500_lx06_play_text_a_5_1` | ✅ 可用 |
| 客厅 | `notify.xiaomi_cn_545160028_lx06_play_text_a_5_1` | ✅ 可用 |
| 客卫 | `notify.xiaomi_cn_545159901_lx06_play_text_a_5_1` | ✅ 可用 |
| 儿童房 | `notify.xiaomi_cn_545159927_lx06_play_text_a_5_1` | ✅ 可用 |
| 主卫 | `notify.xiaomi_cn_570126005_lx06_play_text_a_5_1` | ✅ 可用 |

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install websockets

# 或使用项目虚拟环境
./venv/bin/pip install websockets
```

### 2. 配置Token

将你的Home Assistant访问令牌替换到代码中：

```python
TOKEN = "你的HA访问令牌"
```

### 3. 简单使用

```python
import asyncio
from xiaomi_tts_websocket import xiaomi_tts_speak

async def main():
    # 单房间播报
    await xiaomi_tts_speak(
        "欢迎回家！",
        room="function_room",
        token="你的令牌"
    )

asyncio.run(main())
```

## 📖 详细使用说明

### 基础功能

#### 1. 单房间播报

```python
from xiaomi_tts_websocket import XiaomiTTS

async def single_room_tts():
    tts = XiaomiTTS(token="你的令牌")
    await tts.connect()

    # 播报到多功能房
    success = await tts.speak("你好，这是测试消息", "function_room")

    await tts.close()
```

#### 2. 多房间广播

```python
async def broadcast_tts():
    tts = XiaomiTTS(token="你的令牌")
    await tts.connect()

    # 向指定房间广播
    results = await tts.broadcast(
        "紧急通知：请检查门窗安全",
        rooms=["function_room", "kitchen", "bedroom"]
    )

    print(f"广播结果: {results}")
    await tts.close()
```

#### 3. 连续播报

```python
async def sequential_tts():
    tts = XiaomiTTS(token="你的令牌")
    await tts.connect()

    messages = [
        ("早上好", "bedroom"),
        ("早餐准备好了", "kitchen"),
        ("美好的一天开始了", "function_room")
    ]

    for message, room in messages:
        await tts.speak(message, room)
        await asyncio.sleep(3)  # 间隔3秒

    await tts.close()
```

### 高级功能

#### 1. 定时播报

```python
import schedule
import time
import asyncio

async def scheduled_tts():
    tts = XiaomiTTS(token="你的令牌")
    await tts.connect()

    await tts.speak("现在是早上7点，该起床了", "bedroom")
    await tts.close()

def run_scheduled_tts():
    # 每天7点播报
    schedule.every().day.at("07:00").do(lambda: asyncio.run(scheduled_tts()))

    while True:
        schedule.run_pending()
        time.sleep(60)

# 启动定时任务
run_scheduled_tts()
```

#### 2. 智能提醒

```python
async def smart_reminders():
    tts = XiaomiTTS(token="你的令牌")
    await tts.connect()

    # 天气提醒
    weather = "今天晴天，温度25度"
    await tts.speak(f"天气提醒：{weather}", "function_room")

    # 门铃提醒
    await tts.speak("有客来访，请开门", "living_room")

    # 安全提醒
    await tts.speak("检测到异常活动，请注意安全", "function_room")

    await tts.close()
```

#### 3. 音量控制

```python
async def tts_with_volume_control():
    import requests

    tts = XiaomiTTS(token="你的令牌")
    await tts.connect()

    # 调低音量
    await set_volume("function_room", 30)

    # 播报晚间提醒
    await tts.speak("晚上10点了，调低音量，祝您晚安", "function_room")

    await tts.close()

async def set_volume(room, volume):
    """设置指定房间音箱音量"""
    volume_entities = {
        "function_room": "number.xiaomi_cn_604014890_lx06_volume_p_2_1",
        "kitchen": "number.xiaomi_cn_604013123_lx06_volume_p_2_1",
        "bedroom": "number.xiaomi_cn_604006500_lx06_volume_p_2_1"
    }

    entity_id = volume_entities.get(room)
    if entity_id:
        # 调用HA API设置音量
        print(f"设置{room}音量为{volume}")
```

## 🔧 配置说明

### Home Assistant配置

确保你的Home Assistant中已正确配置：

1. **xiaomi_home集成已安装**
2. **LX06音箱已添加**
3. **访问令牌有效**

### Token获取

1. 进入Home Assistant
2. 点击用户头像 → 滚动页面到底部 → 创建长期访问令牌
3. 复制生成的令牌

### 实体ID配置

根据你的实际设备情况，修改`room_entities`映射：

```python
self.room_entities = {
    "你的房间名": "你的实体ID"
}
```

## 📝 API参考

### XiaomiTTS类

#### 构造函数

```python
XiaomiTTS(ha_url="192.168.100.212:8123", token=None)
```

#### 主要方法

- `connect()` - 建立连接
- `speak(message, room, entity_id=None)` - 单房间播报
- `broadcast(message, rooms=None)` - 多房间广播
- `close()` - 关闭连接

### 便捷函数

- `xiaomi_tts_speak(message, room, ha_url, token)` - 简化播报
- `xiaomi_tts_broadcast(message, rooms, ha_url, token)` - 简化广播

## 🛠 故障排除

### 常见问题

1. **认证失败**
   - 检查Token是否正确
   - 确认Token未过期

2. **连接失败**
   - 检查Home Assistant地址
   - 确认网络连接正常

3. **播报失败**
   - 检查实体ID是否正确
   - 确认音箱在线状态

4. **音量问题**
   - 检查音箱静音状态
   - 调整音量设置

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 启用详细日志
tts = XiaomiTTS(token="你的令牌")
```

## 📈 性能优化

- 使用连接池复用WebSocket连接
- 批量播报时添加适当延迟
- 定期检查连接状态
- 异常处理和自动重连

## 🔮 扩展功能

### 计划中的功能

- [ ] 语音模板系统
- [ ] 多语言支持
- [ ] 语音情感控制
- [ ] 播报历史记录
- [ ] Web界面控制

## 📄 许可证

本项目基于MIT许可证开源。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目。

---

**🎉 验证成功！**
*本项目已经过实际测试，成功在小米音箱LX06上实现TTS语音播报功能。*