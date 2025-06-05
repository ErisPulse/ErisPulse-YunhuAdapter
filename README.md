# YunhuAdapter 模块文档

## 简介
YunhuAdapter 是基于 [ErisPulse](https://github.com/ErisPulse/ErisPulse/) 架构的云湖协议适配器，整合了所有云湖功能模块，提供统一的事件处理和消息操作接口。

## 使用示例

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
        print(f"收到消息: {data}")
        await yunhu.send("user", data["event"]["sender"]["id"], "已收到您的消息！")

    @yunhu.on("follow")
    async def handle_follow(data):
        print(f"新关注: {data}")
        await yunhu.send("user", data["event"]["user"]["id"], "感谢关注！")

    # 启动适配器
    await sdk.adapter.startup()

    # 保持程序运行
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 消息发送示例
```python
# 发送文本消息
await yunhu.send("group", "123456", "Hello World!")

# 发送图片（需先读取为 bytes）
with open("image.png", "rb") as f:
    await yunhu.send("user", "user123", f.read(), content_type="image")

# 批量发送消息
await yunhu.batch_send("user", ["user1", "user2"], "批量消息通知")
```

## 配置说明
在 `env.py` 中进行如下配置：

```python
sdk.env.set("YunhuAdapter", {
    "token": "your_bot_token",
    "server": {
        "host": "127.0.0.1",  # Webhook 监听地址
        "port": 8080,         # Webhook 监听端口
        "path": "/webhook"    # Webhook 路径
    }
})
```

## 事件类型
支持处理以下云湖事件：

| 事件类型                     | 映射名称       | 说明                  |
|------------------------------|----------------|-----------------------|
| `message.receive.normal`     | `message`      | 普通消息              |
| `message.receive.instruction`| `command`      | 指令消息              |
| `bot.followed`               | `follow`       | 关注机器人            |
| `bot.unfollowed`             | `unfollow`     | 取消关注              |
| `group.join`                 | `group_join`   | 用户加群              |
| `group.leave`                | `group_leave`  | 用户退群              |
| `button.report.inline`       | `button_click` | 按钮点击              |
| `bot.shortcut.menu`          | `shortcut_menu`| 快捷菜单              |

## 高级功能

## 公告看板管理
```python
# 发布全局公告
await yunhu.publish_board("global", "重要公告", expire_time=86400)

# 发布群组公告
await yunhu.publish_board("local", "群公告", 
    chat_id="group123", 
    chat_type="group"
)

# 撤销公告
await yunhu.dismiss_board("local", chat_id="group123", chat_type="group")
```

### 消息编辑与撤回
```python
# 编辑消息
await yunhu.edit(
    msg_id="msg_abc123",
    conversation_type="user",
    target_id="user123",
    message="修改后的内容"
)

# 撤回消息
await yunhu.recall(
    msg_id="msg_abc123",
    conversation_type="group",
    target_id="group123"
)
```

### 历史消息查询
```python
# 查询最近5条消息
history = await yunhu.get_history(
    conversation_type="group",
    target_id="group123",
    before=5
)

# 查询指定消息之后的记录
history = await yunhu.get_history(
    conversation_type="user",
    target_id="user123",
    msg_id="msg_abc123",
    after=10
)
```

## 流式消息传输支持

云湖适配器支持通过 **分块传输编码（Chunked Transfer Encoding）** 技术实现流式消息发送，适用于需要逐步生成或实时传输大量内容的场景。

### 使用方式：

通过新增的 send_stream 方法进行调用，需传入一个异步生成器作为内容源。

```python
async def stream_generator():
    for i in range(5):
        yield f"这是第 {i+1} 段内容\n".encode("utf-8")
        await asyncio.sleep(1)

await sdk.adapter.Yunhu.send_stream(
    conversation_type="user",
    target_id="user123",
    content_type="text",
    content_generator=stream_generator()
)
```

### 参数说明：

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| `conversation_type` | `str` | 是 | 会话类型 (`user` 或 `group`) |
| `target_id` | `str` | 是 | 接收方 ID |
| `content_type` | `str` | 是 | 内容类型 (`text` 或 `markdown`) |
| `content_generator` | `AsyncGenerator[bytes, None]` | 是 | 异步字节生成器，用于提供流式数据 |
| `parent_id` | `str` | 否 | 父级消息 ID，用于关联上下文 |

### 注意事项：

1. 请确保 `content_generator` 是一个有效的异步生成器。
2. 每次 `yield` 应返回 `bytes` 类型的数据。
3. 收件端将按发送节奏逐步接收内容，适合长文本或实时生成内容的推送。

### 典型应用场景：

- AI 聊天机器人的逐步回复输出
- 日志信息的实时推送
- 大段文本或富文本内容的渐进式发送
- 实时交互中的进度反馈

如需进一步扩展，可结合压缩、加密、断点续传等功能进行增强。

## 注意事项
1. 确保在调用 `startup()` 前完成所有处理器的注册
2. 生产环境建议配置服务器反向代理指向webhook地址以实现HTTPS
3. 二进制内容（图片/视频等）需以 `bytes` 形式传入
4. 程序退出时请调用 `shutdown()` 确保资源释放

## 参考链接
- [ErisPulse 主库](https://github.com/ErisPulse/ErisPulse/)
- [云湖官方文档](https://www.yhchat.com/document/1-3)
- [模块开发指南](https://github.com/ErisPulse/ErisPulse/tree/main/docs/DEVELOPMENT.md)