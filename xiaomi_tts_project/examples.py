#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米音箱TTS使用示例集合
包含各种实际应用场景的示例代码
"""

import asyncio
import datetime
from xiaomi_tts_websocket import XiaomiTTS, xiaomi_tts_speak, xiaomi_tts_broadcast


# 配置你的token
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmYTA4OGExZWMwZDk0NmIxOTgzYWI5NzAyM2QwMzEwNSIsImlhdCI6MTc2MDAyMjQzMCwiZXhwIjoyMDc1MzgyNDMwfQ.3WO5wh6gsZhgvmurS6HG9vRnsijhIVZ2nuw9SjlV9b4"


async def example_1_basic_tts():
    """示例1: 基础TTS播报"""
    print("=== 示例1: 基础TTS播报 ===")

    # 简单播报
    await xiaomi_tts_speak(
        "欢迎使用小米音箱语音播报系统",
        room="function_room",
        token=TOKEN
    )


async def example_2_weather_broadcast():
    """示例2: 天气播报"""
    print("=== 示例2: 天气播报 ===")

    # 模拟天气数据
    weather_info = {
        "condition": "晴天",
        "temperature": 25,
        "humidity": 60
    }

    message = f"早上好，今天天气{weather_info['condition']}，温度{weather_info['temperature']}度，湿度{weather_info['humidity']}%，记得多喝水哦！"

    await xiaomi_tts_speak(message, "bedroom", token=TOKEN)


async def example_3_time_reminder():
    """示例3: 时间提醒"""
    print("=== 示例3: 时间提醒 ===")

    now = datetime.datetime.now()
    hour = now.hour

    if 6 <= hour < 12:
        greeting = "早上好"
        reminder = "新的一天开始了，加油！"
    elif 12 <= hour < 18:
        greeting = "下午好"
        reminder = "工作累了记得休息一下。"
    elif 18 <= hour < 22:
        greeting = "晚上好"
        reminder = "晚餐后记得散散步。"
    else:
        greeting = "夜深了"
        reminder = "该休息了，晚安。"

    message = f"{greeting}，现在是{hour}点，{reminder}"

    await xiaomi_tts_speak(message, "function_room", token=TOKEN)


async def example_4_security_alert():
    """示例4: 安全提醒"""
    print("=== 示例4: 安全提醒 ===")

    # 模拟安全事件
    security_messages = [
        "检测到门未关闭，请检查门窗",
        "有异常活动检测，请注意安全",
        "燃气传感器报警，请立即检查",
        "烟雾检测器报警，请紧急处理"
    ]

    # 向所有房间广播安全提醒
    await xiaomi_tts_broadcast(
        security_messages[1],  # 使用第二个消息作为示例
        rooms=["function_room", "living_room", "bedroom"],
        token=TOKEN
    )


async def example_5_home_automation():
    """示例5: 智能家居场景联动"""
    print("=== 示例5: 智能家居场景联动 ===")

    tts = XiaomiTTS(token=TOKEN)
    await tts.connect()

    # 场景1: 起床场景
    await tts.speak("早上7点了，新的一天开始了", "bedroom")
    await asyncio.sleep(3)
    await tts.speak("咖啡机已启动，早餐准备中", "kitchen")
    await asyncio.sleep(3)
    await tts.speak("窗帘正在打开，天气不错", "function_room")

    await asyncio.sleep(5)

    # 场景2: 离家场景
    await tts.speak("离家模式已启动", "living_room")
    await asyncio.sleep(2)
    await tts.speak("所有设备已关闭，安防系统已启用", "function_room")

    await tts.close()


async def example_6_medication_reminder():
    """示例6: 用药提醒"""
    print("=== 示例6: 用药提醒 ===")

    medication_reminders = [
        ("爷爷", "降压药", "bedroom"),
        ("奶奶", "心脏病药", "bedroom"),
        ("爸爸", "维生素", "function_room")
    ]

    for person, medicine, room in medication_reminders:
        message = f"提醒{person}，该吃{medicine}了"
        await xiaomi_tts_speak(message, room, token=TOKEN)
        await asyncio.sleep(3)


async def example_7_energy_saving():
    """示例7: 节能提醒"""
    print("=== 示例7: 节能提醒 ===")

    # 模拟能耗数据
    energy_tips = [
        "客厅灯光已开启2小时，建议关闭不必要的灯光",
        "空调温度设置合理，继续保持",
        "检测到待机设备较多，建议关闭",
        "今日用电量正常，继续保持节约习惯"
    ]

    for tip in energy_tips:
        await xiaomi_tts_speak(tip, "function_room", token=TOKEN)
        await asyncio.sleep(4)


async def example_8_welcome_home():
    """示例8: 欢迎回家"""
    print("=== 示例8: 欢迎回家 ===")

    welcome_messages = [
        ("欢迎回家！", "living_room"),
        ("今天辛苦了", "function_room"),
        ("放松一下吧，音乐已为您准备好", "living_room"),
        ("需要我帮您做什么吗？", "function_room")
    ]

    for message, room in welcome_messages:
        await xiaomi_tts_speak(message, room, token=TOKEN)
        await asyncio.sleep(3)


async def example_9_emergency_broadcast():
    """示例9: 紧急广播"""
    print("=== 示例9: 紧急广播 ===")

    emergency_message = "紧急通知：请所有人员立即到客厅集合，有重要事项宣布"

    # 向所有房间广播紧急消息
    await xiaomi_tts_broadcast(
        emergency_message,
        rooms=["bedroom", "kitchen", "function_room", "living_room"],
        token=TOKEN
    )


async def example_10_morning_routine():
    """示例10: 晨间例行播报"""
    print("=== 示例10: 晨间例行播报 ===")

    tts = XiaomiTTS(token=TOKEN)
    await tts.connect()

    # 7:00 起床提醒
    await tts.speak("早上7点，该起床了", "bedroom")
    await asyncio.sleep(5)

    # 7:05 天气播报
    await tts.speak("今天晴天，温度25度，适合外出", "bedroom")
    await asyncio.sleep(5)

    # 7:10 今日提醒
    await tts.speak("记得今天上午10点有会议", "function_room")
    await asyncio.sleep(5)

    # 7:15 出门提醒
    await tts.speak("出门记得带钥匙和手机", "living_room")

    await tts.close()


async def run_all_examples():
    """运行所有示例（谨慎使用，会播报很多消息）"""
    print("⚠️  准备运行所有示例，这将播报很多消息...")
    print("确认继续吗？(y/n)")

    # 注释掉实际运行，避免过多播报
    # user_input = input().strip().lower()
    # if user_input != 'y':
    #     print("已取消")
    #     return

    examples = [
        example_1_basic_tts,
        example_2_weather_broadcast,
        example_3_time_reminder,
        example_4_security_alert,
        example_5_home_automation,
        example_6_medication_reminder,
        example_7_energy_saving,
        example_8_welcome_home,
        example_9_emergency_broadcast,
        example_10_morning_routine
    ]

    for i, example in enumerate(examples, 1):
        print(f"\n运行示例 {i}...")
        await example()
        await asyncio.sleep(5)  # 示例间间隔


if __name__ == "__main__":
    print("小米音箱TTS使用示例")
    print("可用的示例:")
    print("1. 基础TTS播报")
    print("2. 天气播报")
    print("3. 时间提醒")
    print("4. 安全提醒")
    print("5. 智能家居场景联动")
    print("6. 用药提醒")
    print("7. 节能提醒")
    print("8. 欢迎回家")
    print("9. 紧急广播")
    print("10. 晨间例行播报")
    print("11. 运行所有示例")

    try:
        choice = input("\n请选择要运行的示例 (1-11): ").strip()

        if choice == "1":
            asyncio.run(example_1_basic_tts())
        elif choice == "2":
            asyncio.run(example_2_weather_broadcast())
        elif choice == "3":
            asyncio.run(example_3_time_reminder())
        elif choice == "4":
            asyncio.run(example_4_security_alert())
        elif choice == "5":
            asyncio.run(example_5_home_automation())
        elif choice == "6":
            asyncio.run(example_6_medication_reminder())
        elif choice == "7":
            asyncio.run(example_7_energy_saving())
        elif choice == "8":
            asyncio.run(example_8_welcome_home())
        elif choice == "9":
            asyncio.run(example_9_emergency_broadcast())
        elif choice == "10":
            asyncio.run(example_10_morning_routine())
        elif choice == "11":
            asyncio.run(run_all_examples())
        else:
            print("无效选择")

    except KeyboardInterrupt:
        print("\n已取消")
    except Exception as e:
        print(f"运行错误: {e}")