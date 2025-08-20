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

# 批量发送消息
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

首次运行会生成配置，内容及解释如下：

```toml
# config.toml
[Yunhu_Adapter]
token = "your_yunhu_token"

[Yunhu_Adapter.server]
path = "/webhook"
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

---

### 参考链接

- [ErisPulse 主库](https://github.com/ErisPulse/ErisPulse/)
- [云湖官方文档](https://www.yhchat.com/document/1-3)
- [模块开发指南](https://github.com/ErisPulse/ErisPulse/tree/main/docs/DEVELOPMENT.md)
