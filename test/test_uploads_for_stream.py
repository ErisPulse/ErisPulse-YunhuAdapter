# main.py
# ErisPulse 主程序文件
# 本文件由 SDK 自动创建，您可随意修改
import asyncio
import os
from ErisPulse import sdk

async def test_uploads():
    test_files = [
        "test_files/test.docx",
        "test_files/test.jpg", 
        "test_files/test.mp4"
    ]
    
    # 获取Send实例
    Send = sdk.adapter.yunhu.Send.To("group", "635409929")
    
    for file_path in test_files:
        if not os.path.exists(file_path):
            sdk.logger.warning(f"测试文件不存在: {file_path}")
            continue

        with open(file_path, "rb") as f:
            content = f.read()
            sdk.logger.info(f"开始普通上传: {file_path}")
            try:
                if file_path.endswith(".docx"):
                    sdk.logger.info(f"文件类型为docx，上传结果为: {await Send.File(content)}") 
                elif file_path.endswith(".jpg"):
                    sdk.logger.info(f"文件类型为jpg，上传结果为: {await Send.Image(content)}")
                elif file_path.endswith(".mp4"):
                    sdk.logger.info(f"文件类型为mp4，上传结果为: {await Send.Video(content)}")
                sdk.logger.info(f"普通上传成功: {file_path}")
            except Exception as e:
                sdk.logger.error(f"普通上传失败: {file_path} - {str(e)}")
                
        async def file_stream():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024*1024):
                    yield chunk
                    await asyncio.sleep(0.1)
                    
        sdk.logger.info(f"开始流式上传: {file_path}")
        try:
            if file_path.endswith(".docx"):
                sdk.logger.info(f"文件类型为docx，上传结果为: {await Send.File(file_stream(), stream=True)}")
            elif file_path.endswith(".jpg"):
                sdk.logger.info(f"文件类型为jpg，上传结果为: {await Send.Image(file_stream(), stream=True)}")
            elif file_path.endswith(".mp4"):
                sdk.logger.info(f"文件类型为mp4，上传结果为: {await Send.Video(file_stream(), stream=True)}")
            sdk.logger.info(f"流式上传成功: {file_path}")
        except Exception as e:
            sdk.logger.error(f"流式上传失败: {file_path} - {str(e)}")

async def main():
    try:
        sdk.init()
        await sdk.adapter.startup()
        
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