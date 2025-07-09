# main.py
# ErisPulse 主程序文件
# 本文件由 SDK 自动创建，您可随意修改
import asyncio
import os
from ErisPulse import sdk

async def test_edit_add_button():
    def_buttons =  [
                {
                    "text": "114514",
                    "actionType": 2,
                    "value": "xxxx"
                },
                {
                    "text": "1919810",
                    "actionType": 1,
                    "url": "http://www.baidu.com"
                }
            ]
    edit_button = [
                {
                    "text": "昏睡红茶",
                    "actionType": 2,
                    "value": "xxxx"
                },
                {
                    "text": "下北泽俊豪",
                    "actionType": 1,
                    "url": "http://www.baidu.com"
                }
            ]

    Send = sdk.adapter.yunhu.Send.To("group", "635409929")
    send_result = await Send.Text("测试编辑", buttons=def_buttons)
    msg_id = send_result['data']['messageInfo']['msgId']
    sdk.logger.info(f"发送消息成功: {msg_id}")

    result = await Send.Edit(msg_id, "测试编辑", buttons=edit_button)
    sdk.logger.info(f"编辑消息成功: {result}")
async def test_uploads():
    test_files = [
        ("test_files/test.docx", "file", "流式-测试文档.docx"),
        ("test_files/test.jpg", "image", "流式-测试图片.jpg"),
        ("test_files/test.mp4", "video", "流式-测试视频.mp4")
    ]
    
    Send = sdk.adapter.yunhu.Send.To("group", "635409929")
    
    for file_path, file_type, display_name in test_files:
        if not os.path.exists(file_path):
            sdk.logger.warning(f"测试文件不存在: {file_path}")
            continue

        # sdk.logger.info(f"开始普通上传: {display_name}")
        # try:
        #     with open(file_path, "rb") as f:
        #         content = f.read()
                
        #         if file_type == "file":
        #             result = await Send.File(content, filename=display_name)
        #         elif file_type == "image":
        #             result = await Send.Image(content, filename=display_name)
        #         elif file_type == "video":
        #             result = await Send.Video(content, filename=display_name)
                
        #         sdk.logger.info(f"普通上传成功: {display_name} - 结果: {result}")
        # except Exception as e:
        #     sdk.logger.error(f"普通上传失败: {display_name} - {str(e)}", exc_info=True)
            
        sdk.logger.info(f"开始流式上传: {display_name}")
        try:
            async def file_stream():
                with open(file_path, "rb") as f:
                    while chunk := f.read(512 * 1024):
                        yield chunk
                        await asyncio.sleep(0.01)
            
            if file_type == "file":
                result = await Send.File(file_stream(), stream=True, filename=display_name)
            elif file_type == "image":
                result = await Send.Image(file_stream(), stream=True, filename=display_name)
            elif file_type == "video":
                result = await Send.Video(file_stream(), stream=True, filename=display_name)
            
            sdk.logger.info(f"流式上传成功: {display_name} - 结果: {result}")
        except Exception as e:
            sdk.logger.error(f"流式上传失败: {display_name} - {str(e)}", exc_info=True)

async def main():
    try:
        sdk.init()
        await sdk.adapter.startup()
        await asyncio.sleep(1)

        await test_edit_add_button()

        await test_uploads()
        
        await asyncio.Event().wait()
    except Exception as e:
        sdk.logger.error(e)
    except KeyboardInterrupt:
        sdk.logger.info("正在停止程序")
    finally:
        await sdk.adapter.shutdown()

if __name__ == "__main__":
    asyncio.run(main())