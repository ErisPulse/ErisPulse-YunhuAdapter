# YunhuAdapter 模块文档

## 简介
YunhuAdapter 是基于 [ErisPulse](https://github.com/ErisPulse/ErisPulse/) 架构的云湖协议适配器，整合了所有云湖功能模块，提供统一的事件处理和消息操作接口。

## 使用示例

### 事件映射关系
| 官方事件命名 | Adapter事件命名 |
|--------------|----------------|
| message.receive.normal | message |
| message.receive.instruction | command |
| bot.followed | follow |
| bot.unfollowed | unfollow |
| group.join | group_join |
| group.leave | group_leave |
| button.report.inline | button_click |
| bot.shortcut.menu | shortcut_menu |

### 官方事件内容示例
```json
{
    "version": "1.0",
    "header": {
        "eventId": "xxxxx",
        "eventTime": 1647735644000,
        "eventType": "message.receive.instruction"
    },
    "event": {
        "sender": {
            "senderId": "xxxxx",
            "senderType": "user",
            "senderUserLevel": "member",
            "senderNickname": "昵称"
        },
        "chat": {
            "chatId": "xxxxx",
            "chatType": "group"
        },
        "message": {
            "msgId": "xxxxxx",
            "parentId": "xxxx",
            "sendTime": 1647735644000,
            "chatId": "xxxxxxxx",
            "chatType": "group",
            "contentType": "text",
            "content": {
                "text": "早上好"
            },
            "commandId": 98,
            "commandName": "计算器"
        }
    }
}
```

### 初始化与事件处理
```python
from ErisPulse import sdk

async def main():
    # 初始化 SDK
    sdk.init()

    # 获取适配器实例
    yunhu = sdk.adapter.Yunhu

    # 注册事件处理器
    @yunhu.on("message")
    async def handle_message(data):
        """处理普通消息事件"""
        sender = data["event"]["sender"]["senderId"]
        message = data["event"]["message"]["content"]["text"]
        print(f"收到消息: {message}")
        await yunhu.Send.To("user", sender).Text(f"已收到消息: {message}")

    @yunhu.on("command")
    async def handle_command(data):
        """处理指令事件"""
        command_info = data["event"]["message"]
        sender_id = data["event"]["sender"]["senderId"]
        command_name = command_info["commandName"]
        
        print(f"收到指令: {command_name}, 参数: {command_args}")
        
        if command_name == "计算器":
            await yunhu.Send.To("user", sender_id).Text(f"计算结果: 114514")
        else:
            await yunhu.Send.To("user", sender_id).Text(f"未知指令: {command_name}")

    @yunhu.on("follow")
    async def handle_follow(data):
        print(f"新关注: {data}")
        user_id = data["event"]["sender"]["senderId"]
        await yunhu.Send.To("user", user_id).Text("感谢关注！")

    # 启动适配器
    await sdk.adapter.startup()

    # 保持程序运行
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## 消息发送示例

```python
# 发送文本消息
await yunhu.Send.To("user", "user123").Text("Hello World!")

# 发送图片（需先读取为 bytes）
with open("image.png", "rb") as f:
    image_data = f.read()
await yunhu.Send.To("user", "user123").Image(image_data)

# 发送视频（需先读取为 bytes）
with open("video.mp4", "rb") as f:
    video_data = f.read()
await yunhu.Send.To("group", "group456").Video(video_data)

# 发送文件（需先读取为 bytes）
with open("file.txt", "rb") as f:
    file_data = f.read()
await yunhu.Send.To("group", "group456").File(file_data)

# 发送富文本 (HTML)
await yunhu.Send.To("group", "group456").Html("<b>加粗</b>消息")

# 发送 Markdown 格式消息
await yunhu.Send.To("user", "user123").Markdown("# 标题\n- 列表项")

# 批量发送消息 （过时的）
# 该方法批量发送文本/富文本消息时, 更推荐的方法是使用: 
#   Send.To('user'/'group', user_ids: list/group_ids: list).Text/Html/Markdown(message, buttons = None, parent_id = None)
await yunhu.Send.To("users", ["user1", "user2"]).Batch("批量通知")

# 编辑已有消息
# 可以在编辑时添加按钮
# Send.To('user'/'group', user_ids: list/group_ids: list).Edit(message_id, message, buttons = None)
await yunhu.Send.To("user", "user123").Edit("msg_abc123", "修改后的内容")

# 撤回消息
await yunhu.Send.To("group", "group456").Recall("msg_abc123")

# 流式消息传输
async def stream_generator():
    for i in range(5):
        yield f"这是第 {i+1} 段内容\n".encode("utf-8")
        await asyncio.sleep(1)

await yunhu.Send.To("user", "user123").Stream("text", stream_generator())
```
> Text/Html/Markdown 的发送支持使用list传入多个id进行批量发送 | 而不再推荐使用 await yunhu.Send.To("users", ["user1", "user2"]).Batch("批量通知")
---

### 配置说明

在 env.py 中进行如下配置：

```python
sdk.env.set("YunhuAdapter", {
    "token": "your_bot_token",
    "mode": "server",  # 可选: server 或 polling
    "server": {
        "host": "0.0.0.0",      # Webhook 监听地址
        "port": 25888,          # Webhook 监听端口
        "path": "/yunhu/webhook" # Webhook 路径
    },
    "polling": {
        "url": "https://sse.bot.anran.xyz/sse"  # SSE 轮询地址（polling 模式）
    }
})
```

---

### 公告看板管理

```python
# 发布全局公告
await yunhu.Send.To("user", "user123").Board("global", "重要公告", expire_time=86400)

# 发布群组公告
await yunhu.Send.To("user", "user123").Board("local", "指定用户看板")

# 撤销公告
await yunhu.Send.To("user", "user123").DismissBoard("local" / "global")
```

## 新特性

#### 2.6.0
##### File/Image/Video 已支持流式上传模式
```python
async def generate_file():
    with open('large_file.mp4', 'rb') as f:
        while chunk := f.read(1024*1024):
            yield chunk
            await asyncio.sleep(0.1)

await yunhu.Send.Video(generate_file(), stream=True)
```
#### 2.7.0
编辑消息支持传入按钮
上传文件时可以传入文件名（包括流式）

#### 2.8.0
添加 ErisPulse 2.0.0 对于OneBot12协议对转的兼容

### 参数说明
| 参数 | 类型 | 说明 |
|------|------|------|
| file | bytes/AsyncGenerator | 文件内容或异步生成器 |
| stream | bool | 是否使用流式模式(默认False) |
| parent_id | str | 父消息ID(可选) |


### 注意事项：

1. 确保在调用 `startup()` 前完成所有处理器的注册
2. 生产环境建议配置服务器反向代理指向 webhook 地址以实现 HTTPS
3. 二进制内容（图片/视频等）需以 `bytes` 形式传入
4. 程序退出时请调用 `shutdown()` 确保资源释放
5. 指令事件中的 commandId 是唯一标识符，可用于区分不同的指令
6. 官方事件数据结构需通过 `data["event"]` 访问

---

### 参考链接

- [ErisPulse 主库](https://github.com/ErisPulse/ErisPulse/)
- [云湖官方文档](https://www.yhchat.com/document/1-3)
- [模块开发指南](https://github.com/ErisPulse/ErisPulse/tree/main/docs/DEVELOPMENT.md)