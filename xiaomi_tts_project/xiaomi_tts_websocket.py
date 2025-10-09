#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米音箱LX06 TTS语音播报 WebSocket API实现
作者: Claude Code
版本: 1.0
创建时间: 2025-10-09

功能说明：
- 通过WebSocket API控制小米音箱LX06进行TTS语音播报
- 支持多房间独立控制
- 已验证可用的完整实现

设备支持：
- 型号: xiaomi.wifispeaker.lx06
- 集成: xiaomi_home官方插件
- 实体: notify.xiaomi_cn_XXXXXX_lx06_play_text_a_5_1

使用示例：
    tts = XiaomiTTS()
    await tts.speak("你好，这是测试消息", "function_room")

    或者直接调用：
    await xiaomi_tts_speak("欢迎回家")
"""

import asyncio
import json
import websockets
from typing import Optional, Dict, List


class XiaomiTTS:
    """小米音箱TTS控制类"""

    def __init__(self, ha_url: str = "192.168.100.212:8123", token: str = None):
        """
        初始化小米音箱TTS控制器

        Args:
            ha_url: Home Assistant地址，格式为 IP:PORT
            token: Home Assistant访问令牌
        """
        self.ha_url = ha_url
        self.ws_url = f"ws://{ha_url}/api/websocket"
        self.token = token
        self.websocket = None
        self.msg_id = 1

        # 房间实体映射（根据你的实际配置调整）
        self.room_entities = {
            "function_room": "notify.xiaomi_cn_604014890_lx06_play_text_a_5_1",    # 多功能房
            "kitchen": "notify.xiaomi_cn_604013123_lx06_play_text_a_5_1",          # 厨房
            "bedroom": "notify.xiaomi_cn_604006500_lx06_play_text_a_5_1",          # 主卧
            "living_room": "notify.xiaomi_cn_545160028_lx06_play_text_a_5_1",       # 客厅
            "bathroom": "notify.xiaomi_cn_545159901_lx06_play_text_a_5_1",         # 客卫
            "children_room": "notify.xiaomi_cn_545159927_lx06_play_text_a_5_1",     # 儿童房
            "master_bathroom": "notify.xiaomi_cn_570126005_lx06_play_text_a_5_1"    # 主卫
        }

    async def connect(self) -> bool:
        """建立WebSocket连接并认证"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            print("✅ WebSocket连接成功")

            # 等待认证要求
            auth_required = await self.websocket.recv()
            auth_result = json.loads(auth_required)

            if auth_result.get('type') == 'auth_required':
                print("📋 收到认证要求，发送认证信息...")

                # 发送认证
                auth_payload = {
                    'type': 'auth',
                    'access_token': self.token
                }

                await self.websocket.send(json.dumps(auth_payload))
                auth_response = await self.websocket.recv()
                auth_result = json.loads(auth_response)

                if auth_result.get('type') == 'auth_ok':
                    print("✅ 认证成功")
                    return True
                else:
                    print(f"❌ 认证失败: {auth_result}")
                    return False
            else:
                print(f"❌ 未收到认证要求: {auth_result}")
                return False

        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    async def speak(self, message: str, room: str = "function_room", entity_id: str = None) -> bool:
        """
        TTS语音播报

        Args:
            message: 要播报的文本内容
            room: 房间名称（预定义房间）
            entity_id: 直接指定实体ID（优先于room参数）

        Returns:
            bool: 播报是否成功
        """
        if not self.websocket:
            if not await self.connect():
                return False

        # 确定目标实体
        target_entity = entity_id or self.room_entities.get(room)
        if not target_entity:
            print(f"❌ 未找到房间实体: {room}")
            return False

        try:
            # 构建TTS调用载荷
            tts_payload = {
                'id': self.msg_id,
                'type': 'call_service',
                'domain': 'notify',
                'service': 'send_message',
                'target': {
                    'entity_id': target_entity
                },
                'service_data': {
                    'message': message
                }
            }

            print(f"📢 发送TTS指令到{room}: {message}")
            await self.websocket.send(json.dumps(tts_payload))

            # 等待响应
            response = await self.websocket.recv()
            result = json.loads(response)

            self.msg_id += 1

            # 检查结果
            if result.get('type') == 'result':
                if result.get('success', False):
                    print(f"🎉 {room}房间TTS播报成功！")
                    return True
                else:
                    error_msg = result.get('error', {}).get('message', '未知错误')
                    print(f"❌ {room}房间TTS调用失败: {error_msg}")
                    return False
            else:
                print(f"❌ 意外的响应类型: {result.get('type')}")
                return False

        except Exception as e:
            print(f"❌ TTS播报异常: {e}")
            return False

    async def broadcast(self, message: str, rooms: List[str] = None) -> Dict[str, bool]:
        """
        向多个房间广播消息

        Args:
            message: 要播报的文本内容
            rooms: 房间列表，默认为所有房间

        Returns:
            Dict[str, bool]: 各房间播报结果
        """
        if rooms is None:
            rooms = list(self.room_entities.keys())

        results = {}
        print(f"📢 开始向{len(rooms)}个房间广播: {message}")

        for room in rooms:
            success = await self.speak(message, room)
            results[room] = success
            # 短暂延迟避免冲突
            await asyncio.sleep(0.5)

        success_count = sum(results.values())
        print(f"📊 广播完成: {success_count}/{len(rooms)}个房间成功")
        return results

    async def close(self):
        """关闭WebSocket连接"""
        if self.websocket:
            await self.websocket.close()
            print("📡 WebSocket连接已关闭")


# 便捷函数
async def xiaomi_tts_speak(message: str, room: str = "function_room",
                          ha_url: str = "192.168.100.212:8123",
                          token: str = None) -> bool:
    """
    简化的TTS播报函数

    Args:
        message: 要播报的文本内容
        room: 房间名称
        ha_url: Home Assistant地址
        token: 访问令牌

    Returns:
        bool: 播报是否成功
    """
    if not token:
        raise ValueError("请提供有效的Home Assistant访问令牌")

    tts = XiaomiTTS(ha_url, token)
    try:
        success = await tts.speak(message, room)
        return success
    finally:
        await tts.close()


async def xiaomi_tts_broadcast(message: str, rooms: List[str] = None,
                              ha_url: str = "192.168.100.212:8123",
                              token: str = None) -> Dict[str, bool]:
    """
    简化的多房间广播函数

    Args:
        message: 要播报的文本内容
        rooms: 房间列表
        ha_url: Home Assistant地址
        token: 访问令牌

    Returns:
        Dict[str, bool]: 各房间播报结果
    """
    if not token:
        raise ValueError("请提供有效的Home Assistant访问令牌")

    tts = XiaomiTTS(ha_url, token)
    try:
        results = await tts.broadcast(message, rooms)
        return results
    finally:
        await tts.close()


# 使用示例
async def demo():
    """演示各种TTS功能"""

    # 配置你的token
    TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmYTA4OGExZWMwZDk0NmIxOTgzYWI5NzAyM2QwMzEwNSIsImlhdCI6MTc2MDAyMjQzMCwiZXhwIjoyMDc1MzgyNDMwfQ.3WO5wh6gsZhgvmurS6HG9vRnsijhIVZ2nuw9SjlV9b4"

    # 示例1: 简单播报
    print("=== 示例1: 单房间播报 ===")
    await xiaomi_tts_speak("晚上10点了，调低音量，祝您晚安", "function_room", token=TOKEN)

    await asyncio.sleep(2)

    # 示例2: 多房间广播
    print("\n=== 示例2: 多房间广播 ===")
    results = await xiaomi_tts_broadcast(
        "紧急通知：请检查门窗安全",
        rooms=["function_room", "kitchen", "bedroom"],
        token=TOKEN
    )
    print(f"广播结果: {results}")

    await asyncio.sleep(2)

    # 示例3: 使用类进行复杂控制
    print("\n=== 示例3: 使用TTS类 ===")
    tts = XiaomiTTS(token=TOKEN)
    await tts.connect()

    # 连续播报
    messages = [
        ("早上好", "bedroom"),
        ("早餐准备好了", "kitchen"),
        ("美好的一天开始了", "function_room")
    ]

    for message, room in messages:
        await tts.speak(message, room)
        await asyncio.sleep(3)

    await tts.close()


if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo())