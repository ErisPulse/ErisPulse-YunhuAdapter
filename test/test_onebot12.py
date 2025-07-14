# onebot_test.py
# ErisPulse OneBot12 协议测试脚本
import asyncio
from ErisPulse import sdk

# 测试配置
test_user_id = "5197892"        # 设为None则不测试私聊功能
test_group_id = "853732258"     # 设为None则不测试群聊功能

async def test_onebot_message_events():
    """测试OneBot12消息事件监听"""
    @sdk.adapter.on("message")
    async def handle_onebot_message(event):
        sdk.logger.info("\n" + "="*50)
        sdk.logger.info("收到OneBot12格式消息事件:")
        sdk.logger.info(f"消息ID: {event.get('message_id')}")
        sdk.logger.info(f"消息类型: {event.get('detail_type')}")
        sdk.logger.info(f"发送者ID: {event.get('user_id')}")
        sdk.logger.info(f"群组ID: {event.get('group_id', '无(私聊)')}")
        sdk.logger.info(f"消息内容: {event.get('message')}")
        sdk.logger.info(f"原始事件: {event}")
        sdk.logger.info("="*50 + "\n")

#         # 发送消息以测试
#         if test_user_id:
#             Send = sdk.adapter.yunhu.Send.To("user", test_user_id)

#             send_result = await Send.Markdown(f"""
# 收到OneBot事件测试消息\n
# 内容：{event.get('message')}
# 消息ID：{event.get('message_id')}
# 群组ID：{event.get('group_id', '无(私聊)')}
# 发送者ID：{event.get('user_id', '无')}
# """)

#         if test_group_id:
#             Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
#             send_result = await Send.Markdown(f"""
# 收到OneBot事件测试消息\n
# 内容：{event.get('message')}
# 消息ID：{event.get('message_id')}
# 群组ID：{event.get('group_id', '无(私聊)')}
# 发送者ID：{event.get('user_id', '无')}
# """)
async def test_onebot_notice_events():
    """测试OneBot12通知事件监听"""
    @sdk.adapter.on("notice")
    async def handle_onebot_notice(event):
        sdk.logger.info("\n" + "="*50)
        sdk.logger.info("收到OneBot12格式通知事件:")
        sdk.logger.info(f"通知类型: {event.get('detail_type')}")
        sdk.logger.info(f"用户ID: {event.get('user_id')}")
        sdk.logger.info(f"群组ID: {event.get('group_id', '无')}")
        sdk.logger.info(f"操作者ID: {event.get('operator_id', '无')}")
        sdk.logger.info(f"原始事件: {event}")
        sdk.logger.info("="*50 + "\n")
        
#         if test_group_id:
#             Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
#             result = await Send.Markdown(f"""
# 收到OneBot12格式通知事件\n
# **通知类型**: {event.get('detail_type')}
# **用户ID**: {event.get('user_id')}
# **群组ID**: {event.get('group_id', '无')}
# **操作者ID**: {event.get('operator_id', '无')}
# **原始事件**: {event}
# """)
#         if test_user_id:
#             Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
#             result = await Send.Markdown(f"""
# 收到OneBot12格式通知事件\n
# **通知类型**: {event.get('detail_type')}
# **用户ID**: {event.get('user_id')}
# **群组ID**: {event.get('group_id', '无')}
# **操作者ID**: {event.get('operator_id', '无')}
# **原始事件**: {event}
# """)
async def test_onebot_button_events():
    """测试OneBot12按钮事件监听"""
    @sdk.adapter.on("button_click")
    async def handle_onebot_button(event):
        sdk.logger.info("\n" + "="*50)
        sdk.logger.info("收到OneBot12格式按钮事件:")
        sdk.logger.info(f"消息ID: {event.get('message_id')}")
        sdk.logger.info(f"用户ID: {event.get('user_id')}")
        sdk.logger.info(f"按钮值: {event.get('data', {}).get('value')}")
        sdk.logger.info(f"原始事件: {event}")
        sdk.logger.info("="*50 + "\n")

#         if test_user_id:
#             Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
#             result = await Send.Markdown(f"""
# 收到OneBot12格式按钮事件\n
# **消息ID**: {event.get('message_id')}
# **用户ID**: {event.get('user_id')}
# **按钮值**: {event.get('data', {}).get('value')}
# **原始事件**: {event}
# """)
#         if test_group_id:
#             Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
#             result = await Send.Markdown(f"""
# 收到OneBot12格式按钮事件\n
# **消息ID**: {event.get('message_id')}
# **用户ID**: {event.get('user_id')}
# **按钮值**: {event.get('data', {}).get('value')}
# **原始事件**: {event}
# """)
    # 发送带按钮的消息以测试
    if test_user_id or test_group_id:
        buttons = [{
            "text": "测试按钮",
            "actionType": 3,  # 汇报类按钮
            "value": "test_button_value"
        }]
        
        if test_user_id:
            Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
            await Send.Text("点击下方按钮测试OneBot12按钮事件", buttons=buttons)
            
        if test_group_id:
            Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
            await Send.Text("点击下方按钮测试OneBot12按钮事件", buttons=buttons)

async def test_onebot_all_events():
    """测试OneBot12所有事件监听"""
    
    @sdk.adapter.on("*")  # 监听所有OneBot12事件
    async def handle_all_onebot_events(event):
        sdk.logger.info("\n" + "="*50)
        sdk.logger.info("收到OneBot12格式事件(所有类型):")
        sdk.logger.info(f"事件类型: {event.get('type')}")
        sdk.logger.info(f"详细类型: {event.get('detail_type')}")
        sdk.logger.info(f"子类型: {event.get('sub_type', '无')}")
        sdk.logger.info(f"平台: {event.get('platform')}")
        sdk.logger.info(f"原始事件: {event}")
        sdk.logger.info("="*50 + "\n")
        
        import json
        formatted_event = json.dumps(event, indent=2, ensure_ascii=False)
        raw_event = event.get(f"{event.get('platform')}_raw", event)
        raw_event = json.dumps(raw_event, indent=2, ensure_ascii=False)
        
        if test_user_id:
            Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
            result = await Send.Markdown(f"""
```json
{formatted_event}
```
""")
        if test_group_id: 
            Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
            result = await Send.Markdown(f"""
原始事件:
```json
{raw_event}
```
转换后
```json
{formatted_event}
```
""")

async def main():
    try:
        sdk.init()
        await sdk.adapter.startup()
        await asyncio.sleep(1)  # 等待适配器初始化
        
        # await sdk.AnyMsgSync.start()

        # 注册并测试OneBot12事件处理器
        # await test_onebot_message_events()
        # await test_onebot_notice_events()
        # await test_onebot_button_events()
        await test_onebot_all_events()
        sdk.logger.info("OneBot12测试已启动，请手动触发各种事件进行测试...")
        sdk.logger.info("1. 发送私聊/群聊消息测试message事件")
        sdk.logger.info("2. 点击按钮测试button_click事件")
        sdk.logger.info("3. 关注/取消关注机器人测试notice.friend_*事件")
        sdk.logger.info("4. 加入/退出群组测试notice.group_member_*事件")
        
        # 保持运行以接收事件
        await asyncio.Event().wait()
        
    except Exception as e:
        sdk.logger.error(f"OneBot12测试过程中出错: {str(e)}", exc_info=True)
    except KeyboardInterrupt:
        sdk.logger.info("正在停止OneBot12测试程序")
    finally:
        await sdk.adapter.shutdown()

if __name__ == "__main__":
    asyncio.run(main())