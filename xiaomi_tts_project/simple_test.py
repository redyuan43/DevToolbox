#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米音箱TTS简单测试脚本
快速验证TTS功能是否正常
"""

import asyncio
import json
import websockets


async def quick_test():
    """快速TTS测试"""

    # 配置信息
    ws_url = "ws://192.168.100.212:8123/api/websocket"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmYTA4OGExZWMwZDk0NmIxOTgzYWI5NzAyM2QwMzEwNSIsImlhdCI6MTc2MDAyMjQzMCwiZXhwIjoyMDc1MzgyNDMwfQ.3WO5wh6gsZhgvmurS6HG9vRnsijhIVZ2nuw9SjlV9b4"
    entity_id = "notify.xiaomi_cn_604014890_lx06_play_text_a_5_1"  # 多功能房
    message = "测试消息：小米音箱TTS功能正常"

    print("🚀 开始小米音箱TTS测试...")

    try:
        # 建立WebSocket连接
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket连接成功")

            # 认证流程
            auth_required = await websocket.recv()
            auth_payload = {
                'type': 'auth',
                'access_token': token
            }
            await websocket.send(json.dumps(auth_payload))
            auth_response = await websocket.recv()
            auth_result = json.loads(auth_response)

            if auth_result.get('type') != 'auth_ok':
                print(f"❌ 认证失败: {auth_result}")
                return False

            print("✅ 认证成功")

            # 发送TTS指令
            tts_payload = {
                'id': 1,
                'type': 'call_service',
                'domain': 'notify',
                'service': 'send_message',
                'target': {
                    'entity_id': entity_id
                },
                'service_data': {
                    'message': message
                }
            }

            print(f"📢 播报消息: {message}")
            await websocket.send(json.dumps(tts_payload))

            # 等待响应
            response = await websocket.recv()
            result = json.loads(response)

            if result.get('type') == 'result' and result.get('success'):
                print("🎉 TTS测试成功！多功能房音箱应该正在播报消息。")
                return True
            else:
                print(f"❌ TTS调用失败: {result}")
                return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(quick_test())

    if success:
        print("\n✅ 测试完成 - TTS功能正常")
    else:
        print("\n❌ 测试失败 - 请检查配置")