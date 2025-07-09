# main.py
# ErisPulse 主程序文件 - 全面测试脚本
import asyncio
import os
from ErisPulse import sdk

# 测试配置
test_user_id = "5197892"        # 设为None则不测试私聊功能
another_user_id = "5197892"

test_group_id = "635409929"     # 设为None则不测试群聊功能
another_group_id = "635409929"

async def test_text_messages():
    if test_user_id:
        Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
        result = await Send.Text("测试私聊文本消息")
        sdk.logger.info(f"私聊文本消息发送结果: {result}")
        
    if test_group_id:
        Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
        result = await Send.Text("测试群聊文本消息")
        sdk.logger.info(f"群聊文本消息发送结果: {result}")

async def test_rich_messages():
    if test_user_id:
        Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
        result = await Send.Html("<b>加粗</b> <i>斜体</i> <u>下划线</u>")
        sdk.logger.info(f"HTML消息发送结果: {result}")
        
        result = await Send.Markdown("# 标题\n- 列表项1\n- 列表项2")
        sdk.logger.info(f"Markdown消息发送结果: {result}")
    if test_group_id:
        Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
        result = await Send.Html("<b>加粗</b> <i>斜体</i> <u>下划线</u>")
        sdk.logger.info(f"HTML消息发送结果: {result}")
        result = await Send.Markdown("# 标题\n- 列表项1\n- 列表项2")
        sdk.logger.info(f"Markdown消息发送结果: {result}")

async def test_media_messages():
    test_files = [
        ("test_files/test.docx", "file", "测试文档.docx"),
        ("test_files/test.jpg", "image", "测试图片.jpg"),
        ("test_files/test.mp4", "video", "测试视频.mp4")
    ]
    
    # 创建测试目录和文件（如果不存在）
    os.makedirs("test_files", exist_ok=True)
    for file in test_files:
        if not os.path.exists(file[0]):
            with open(file[0], "wb") as f:
                f.write(b"Test content for " + file[2].encode())
    
    for target_type, target_id in [("user", test_user_id), ("group", test_group_id)]:
        if not target_id:
            continue
            
        Send = sdk.adapter.yunhu.Send.To(target_type, target_id)
        
        for file_path, file_type, display_name in test_files:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                    
                    if file_type == "file":
                        result = await Send.File(content, filename=display_name)
                    elif file_type == "image":
                        result = await Send.Image(content, filename=display_name)
                    elif file_type == "video":
                        result = await Send.Video(content, filename=display_name)
                    
                    sdk.logger.info(f"{target_type} {file_type}普通上传结果: {result}")
                    
                    # 测试流式上传
                    async def file_stream():
                        with open(file_path, "rb") as f:
                            while chunk := f.read(4096 * 1024):
                                yield chunk
                                await asyncio.sleep(0.05)

                    if file_type == "file":
                        result = await Send.File(file_stream(), stream=True, filename="stream_"+display_name)
                    elif file_type == "image":
                        result = await Send.Image(file_stream(), stream=True, filename="stream_"+display_name)
                    elif file_type == "video":
                        result = await Send.Video(file_stream(), stream=True, filename="stream_"+display_name)
                        
                    sdk.logger.info(f"{target_type} {file_type}流式上传结果: {result}")
                    
            except Exception as e:
                sdk.logger.error(f"{target_type} {file_type}上传失败: {str(e)}", exc_info=True)

async def test_message_operations():
    if test_group_id:
        Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
        
        # 发送初始消息
        send_result = await Send.Text("测试编辑的消息")
        msg_id = send_result['data']['messageInfo']['msgId']
        sdk.logger.info(f"初始消息发送成功: {msg_id}")
        
        # 编辑消息
        edit_result = await Send.Edit(msg_id, "已编辑的消息内容")
        sdk.logger.info(f"消息编辑结果: {edit_result}")
        
        # 撤回消息
        recall_result = await Send.Recall(msg_id)
        sdk.logger.info(f"消息撤回结果: {recall_result}")
    if test_user_id:
        Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
        
        # 发送初始消息
        send_result = await Send.Text("测试编辑的消息")
        msg_id = send_result['data']['messageInfo']['msgId']
        sdk.logger.info(f"初始消息发送成功: {msg_id}")
        
        # 编辑消息
        edit_result = await Send.Edit(msg_id, "已编辑的消息内容")
        sdk.logger.info(f"消息编辑结果: {edit_result}")
        
        # 撤回消息
        recall_result = await Send.Recall(msg_id)
        sdk.logger.info(f"消息撤回结果: {recall_result}")

async def test_buttons():
    buttons = [
        {
            "text": "按钮1",
            "actionType": 2,
            "value": "button1_value"
        },
        {
            "text": "按钮2",
            "actionType": 1,
            "url": "http://www.example.com"
        }
    ]
    
    # 编辑按钮
    new_buttons = [
        {
            "text": "新按钮1",
            "actionType": 2,
            "value": "new_button1_value"
        }
    ]
    if test_group_id:
        Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
        # 发送带按钮的消息
        send_result = await Send.Text("测试按钮功能", buttons=buttons)
        msg_id = send_result['data']['messageInfo']['msgId']
        sdk.logger.info(f"带按钮消息发送成功: {msg_id}")
        
        edit_result = await Send.Edit(msg_id, "已更新按钮的消息", buttons=new_buttons)
        sdk.logger.info(f"按钮编辑结果: {edit_result}")
    if test_user_id:
        Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
        # 发送带按钮的消息
        send_result = await Send.Text("测试按钮功能", buttons=buttons)
        msg_id = send_result['data']['messageInfo']['msgId']
        sdk.logger.info(f"带按钮消息发送成功: {msg_id}")
        
        edit_result = await Send.Edit(msg_id, "已更新按钮的消息", buttons=new_buttons)
        sdk.logger.info(f"消息更新成功: {msg_id}")
async def test_batch_messages():
    if test_user_id and test_group_id:
        # 批量发送给多个用户
        Send = sdk.adapter.yunhu.Send.To("user", [test_user_id, another_user_id])
        result = await Send.Text("批量用户消息测试")
        sdk.logger.info(f"批量用户消息结果: {result}")
        
        # 批量发送给多个群组
        Send = sdk.adapter.yunhu.Send.To("group", [test_group_id, another_group_id])
        result = await Send.Text("批量群组消息测试")
        sdk.logger.info(f"批量群组消息结果: {result}")

async def test_board():
    if test_user_id:
        Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
        
        # 发布全局公告
        board_result = await Send.Board("global", "测试全局公告", expire_time=3600)
        sdk.logger.info(f"全局公告发布结果: {board_result}")
        
        # 发布用户公告
        board_result = await Send.Board("local", "测试用户公告")
        sdk.logger.info(f"用户公告发布结果: {board_result}")
        
        # 撤销公告
        dismiss_result = await Send.DismissBoard("local", chat_id=test_user_id, chat_type="user", member_id=test_user_id)
        sdk.logger.info(f"撤销用户公告结果: {dismiss_result}")
        dismiss_result = await Send.DismissBoard("global")
        sdk.logger.info(f"撤销全局公告结果: {dismiss_result}")

async def test_streaming():
    async def text_stream():
        for i in range(5):
            yield f"流式文本消息第 {i+1} 部分\n".encode("utf-8")
            await asyncio.sleep(1)
            
    if test_user_id:
        Send = sdk.adapter.yunhu.Send.To("user", test_user_id)
        result = await Send.Stream("text", text_stream())
        sdk.logger.info(f"流式文本消息结果: {result}")
    if test_group_id:
        Send = sdk.adapter.yunhu.Send.To("group", test_group_id)
        result = await Send.Stream("text", text_stream())
        sdk.logger.info(f"流式文本消息结果: {result}")
async def test_event_handlers():
    yunhu = sdk.adapter.yunhu
    
    @yunhu.on("message")
    async def handle_message(data):
        sdk.logger.info(f"收到消息事件: {data}")
        
    @yunhu.on("command")
    async def handle_command(data):
        sdk.logger.info(f"收到指令事件: {data}")
        
    @yunhu.on("follow")
    async def handle_follow(data):
        sdk.logger.info(f"收到关注事件: {data}")

async def main():
    try:
        sdk.init()
        await sdk.adapter.startup()
        await asyncio.sleep(1)
        
        # 注册事件处理器
        await test_event_handlers()
        
        # 执行各项测试
        await test_text_messages()
        await test_rich_messages()
        await test_media_messages()
        await test_message_operations()
        await test_buttons()
        await test_batch_messages()
        await test_board()
        await test_streaming()
        
        sdk.logger.info("所有测试已完成")
        await asyncio.Event().wait()
    except Exception as e:
        sdk.logger.error(f"测试过程中出错: {str(e)}", exc_info=True)
    except KeyboardInterrupt:
        sdk.logger.info("正在停止程序")
    finally:
        await sdk.adapter.shutdown()

if __name__ == "__main__":
    asyncio.run(main())