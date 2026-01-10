# YunhuAdapter 模块文档

## 简介
YunhuAdapter 是基于 [ErisPulse](https://github.com/ErisPulse/ErisPulse/) 架构的云湖协议适配器，整合了所有云湖功能模块，提供统一的事件处理和消息操作接口。

## 使用示例

### 平台原生事件映射关系
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

这仅仅在 `sdk.adapter.yunhu.on()` 的时候生效，你完全可以使用标准OneBot12事件（`sdk.adapter.on`）来获取信息。

### OneBot12标准事件类型

云湖适配器完全兼容 OneBot12 标准事件格式，并提供了一些扩展字段：

| 事件类型 | detail_type | 说明 |
|----------|-------------|------|
| 消息事件 | message | 标准消息事件 |
| 好友增加 | notice.friend_increase | 用户关注机器人 |
| 好友减少 | notice.friend_decrease | 用户取消关注机器人 |
| 群成员增加 | notice.group_member_increase | 用户加入群组 |
| 群成员减少 | notice.group_member_decrease | 用户离开群组 |
| 云湖按钮点击 | notice.yunhu_button_click | 用户点击按钮 |
| 云湖快捷菜单 | notice.yunhu_shortcut_menu | 用户点击快捷菜单 |
| 云湖机器人设置 | notice.yunhu_bot_setting | 机器人设置变更 |

---

## 消息发送示例

```python
# 发送文本消息（带按钮和父消息ID）
buttons = [[{"text": "点击", "actionType": 3, "value": "clicked"}]]
await yunhu.Send.To("user", "user123").Text("Hello World!", buttons=buttons, parent_id="parent_msg_id")

# 发送图片（支持自定义文件名）
with open("image.png", "rb") as f:
    image_data = f.read()
await yunhu.Send.To("user", "user123").Image(image_data, filename="my_image.png")

# 发送视频（支持流式上传）
async def video_generator():
    with open("video.mp4", "rb") as f:
        while chunk := f.read(8192):
            yield chunk

await yunhu.Send.To("group", "group456").Video(video_generator(), stream=True)

# 发送文件（支持自定义文件名和流式上传）
async def file_generator():
    with open("document.pdf", "rb") as f:
        while chunk := f.read(8192):
            yield chunk

await yunhu.Send.To("group", "group456").File(file_generator(), filename="文档.pdf", stream=True)

# 发送富文本 (HTML)
await yunhu.Send.To("group", "group456").Html("<b>加粗</b>消息")

# 发送 Markdown 格式消息
await yunhu.Send.To("user", "user123").Markdown("# 标题\n- 列表项")

# 批量发送消息（指定内容类型）
await yunhu.Send.To("user", ["user1", "user2"]).Batch(["user1", "user2"], "批量通知", content_type="text")

# 编辑已有消息（指定内容类型）
await yunhu.Send.To("user", "user123").Edit("msg_abc123", "修改后的内容", content_type="text")

# 撤回消息
await yunhu.Send.To("group", "group456").Recall("msg_abc123")

# 发送流式消息
async def stream_generator():
    for i in range(5):
        yield f"这是第 {i+1} 段内容\n".encode("utf-8")
        await asyncio.sleep(1)

await yunhu.Send.To("user", "user123").Stream("text", stream_generator())

# 发布全局公告（带过期时间）
await yunhu.Send.Board("global", "重要公告", expire_time=86400)

# 发布群组公告（指定成员）
await yunhu.Send.To("user", "user123").Board("local", "指定用户看板", member_id="member123")

# 撤销公告（指定群组）
await yunhu.Send.To("group", "group456").DismissBoard("local", chat_id="group456", chat_type="group")
```

> Text/Html/Markdown 的发送支持使用list传入多个id进行批量发送 | 而不再推荐使用 await yunhu.Send.To("user", ["user1", "user2"]).Batch("批量通知")

---

### 配置说明

首次运行会生成配置。云湖适配器支持多机器人配置。

#### 多Bot配置（推荐）

```toml
# config.toml
[Yunhu_Adapter.bots.bot1]
bot_id = "30535459"  # 机器人ID（必填）
token = "your_bot1_token"  # 机器人token（必填）
webhook_path = "/webhook/bot1"  # Webhook路径（可选，默认为"/webhook"）
enabled = true  # 是否启用（可选，默认为true）

[Yunhu_Adapter.bots.bot2]
bot_id = "12345678"  # 第二个机器人的ID
token = "your_bot2_token"  # 第二个机器人的token
webhook_path = "/webhook/bot2"  # 独立的webhook路径
enabled = true
```

**配置项说明：**
- `bot_id`：机器人的唯一标识ID（必填），用于标识是哪个机器人触发的事件
- `token`：云湖平台提供的API token（必填）
- `webhook_path`：接收云湖事件的HTTP路径（可选，默认为"/webhook"）
- `enabled`：是否启用该bot（可选，默认为true）

**重要提示：**
1. 云湖平台的事件中不包含机器人ID，因此必须在配置中明确指定`bot_id`
2. 每个bot都应该有独立的`webhook_path`，以便接收各自的webhook事件
3. 在云湖平台配置webhook时，请为每个bot配置对应的URL，例如：
   - Bot1: `https://your-domain.com/webhook/bot1`
   - Bot2: `https://your-domain.com/webhook/bot2`

#### 单Bot配置（兼容旧格式）

如果只有一个bot，也可以使用旧格式的配置（但建议迁移到新格式）：

```toml
# config.toml
[Yunhu_Adapter]
token = "your_yunhu_token"

[Yunhu_Adapter.server]
path = "/webhook"
```

**注意：** 旧格式配置会自动迁移为默认bot，但`bot_id`需要手动设置为实际值。

#### 指定发送Bot

可以通过`Using()`方法指定使用哪个bot发送消息：

```python
from ErisPulse.Core import adapter
yunhu = adapter.get("yunhu")

# 使用bot1发送消息
await yunhu.Send.Using("bot1").To("user", "user123").Text("Hello from bot1!")

# 使用bot2发送消息
await yunhu.Send.Using("bot2").To("group", "group456").Text("Hello from bot2!")

# 不指定时使用第一个启用的bot
await yunhu.Send.To("user", "user123").Text("Hello from default bot!")
```

---

## 云湖平台特有功能

请参考 [云湖平台特性文档](platform-features/yunhu.md) 了解云湖平台的特有功能，包括特有消息段类型、扩展字段说明、表单消息事件、按钮点击事件、机器人设置事件和快捷菜单事件等内容。

## 事件监听示例

### 使用 Event 模块（推荐）

```python
from ErisPulse.Core.Event import message, notice, command

@message.on_message()
async def handle_message(event):
    if event["platform"] == "yunhu":
        # 处理云湖消息事件
        pass

@notice.on_notice()
async def handle_notice(event):
    if event["platform"] == "yunhu":
        # 处理云湖通知事件
        pass

@command("test", help="测试命令")
async def handle_command(event):
    if event["platform"] == "yunhu":
        # 处理云湖命令事件
        pass
```

### 使用平台原生事件

```python
yunhu = sdk.adapter.get("yunhu")

# 使用平台原始事件名
@yunhu.on("message.receive.normal")
async def handle_normal_message(data):
    pass

# 或使用映射后的事件名（向后兼容）
@yunhu.on("message")
async def handle_message(data):
    pass

@yunhu.on("button.report.inline")
async def handle_button(data):
    # 处理按钮点击事件
    pass
```

### 使用 OneBot12 标准事件

```python
@sdk.adapter.on("message")
async def handle_message(event):
    if event["platform"] == "yunhu":
        # 处理云湖消息事件
        # 获取触发事件的机器人ID
        bot_id = event["self"]["user_id"]
        print(f"消息来自Bot: {bot_id}")
        
        # 可以根据不同的bot_id执行不同的逻辑
        if bot_id == "30535459":
            # bot1 的处理逻辑
            pass
        elif bot_id == "12345678":
            # bot2 的处理逻辑
            pass

@sdk.adapter.on("notice")
async def handle_notice(event):
    if event["platform"] == "yunhu":
        # 处理云湖通知事件
        pass
```

## 注意事项：

1. 确保在调用 `startup()` 前完成所有处理器的注册
2. 生产环境建议配置服务器反向代理指向 webhook 地址以实现 HTTPS
3. 二进制内容（图片/视频等）需以 `bytes` 形式传入
4. 程序退出时请调用 `shutdown()` 确保资源释放
5. 指令事件中的 commandId 是唯一标识符，可用于区分不同的指令
6. 官方事件数据结构需通过 `data["event"]` 访问
7. **重要**：云湖平台的事件不包含机器人ID，必须在配置中正确设置`bot_id`，以便识别是哪个机器人触发的事件
8. 多bot配置时，确保每个bot有独立的webhook路径，并在云湖平台正确配置对应的URL

---

### 参考链接

- [ErisPulse 主库](https://github.com/ErisPulse/ErisPulse/)
- [云湖官方文档](https://www.yhchat.com/document/1-3)
- [模块开发指南](https://github.com/ErisPulse/ErisPulse/tree/main/docs/DEVELOPMENT.md)
