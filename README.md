<div align="center">

<img src=".github/assets/ErisPulseLogo.png" width="180" alt="ErisPulse YunhuAdapter" />

# ErisPulse YunhuAdapter

**云湖协议适配器 —— AI时代的社交聊天平台**

基于 ErisPulse 架构的云湖协议适配器，整合所有云湖功能模块，提供统一的事件处理和消息操作接口，支持 WebSocket / Webhook 双模式与多 Bot 配置。

<p>
  <a href="https://pypi.org/project/ErisPulse-YunhuAdapter/"><img src="https://img.shields.io/pypi/v/ErisPulse-YunhuAdapter?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-YunhuAdapter/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/ErisPulse/ErisPulse-YunhuAdapter"><img src="https://img.shields.io/github/stars/ErisPulse/ErisPulse-YunhuAdapter?style=for-the-badge&logo=github&color=brightgreen" alt="Stars"></a>
  <a href="https://pepy.tech/project/ErisPulse-YunhuAdapter"><img src="https://img.shields.io/pepy/dt/ErisPulse-YunhuAdapter?style=for-the-badge&color=blue" alt="Downloads"></a>
  <a href="https://github.com/ErisPulse/ErisPulse"><img src="https://img.shields.io/badge/Powered_by-ErisPulse-FF6B9D?style=for-the-badge&logo=bookstack&logoColor=white" alt="ErisPulse"></a>
</p>

</div>

---

## 简介
YunhuAdapter 是基于 [ErisPulse](https://github.com/ErisPulse/ErisPulse/) 架构的云湖协议适配器，整合了所有云湖功能模块，提供统一的事件处理和消息操作接口。

## 使用示例

### 平台原生事件 → OneBot12 映射关系

所有云湖原生事件会自动转换为 OneBot12 标准格式，可通过标准装饰器监听。

| 原生事件类型 | OneBot12 detail_type | 说明 |
|-------------|---------------------|------|
| message.receive.normal | message | 普通消息 |
| message.receive.instruction | message | 指令消息 |
| bot.followed | notice.friend_increase | 用户关注机器人 |
| bot.unfollowed | notice.friend_decrease | 用户取消关注 |
| group.join | notice.group_member_increase | 用户加入群组 |
| group.leave | notice.group_member_decrease | 用户离开群组 |
| button.report.inline | notice.yunhu_button_click | 按钮点击 |
| a2ui.button.report | notice.yunhu_a2ui_button | A2UI按钮点击 |
| bot.shortcut.menu | notice.yunhu_shortcut_menu | 快捷菜单 |
| bot.setting | notice.yunhu_bot_setting | 机器人设置变更 |

---

## 消息发送示例

```python
# 发送文本消息
await yunhu.Send.To("user", "user123").Text("Hello World!")

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

# 发送 A2UI 交互卡片
await yunhu.Send.To("user", "user123").A2UI("A2UI交互卡片内容")

# 发送 Raw OneBot12 格式消息
await yunhu.Send.To("user", "user123").Raw_ob12([{"type": "text", "data": {"text": "Hello"}}])

# 发送带按钮的文本消息
buttons = [[{"text": "点击", "actionType": 3, "value": "clicked"}]]
await yunhu.Send.To("user", "user123").Buttons(buttons).Text("带按钮的消息")

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

# 发布全局公告（无 To 即为全局）
await yunhu.Send.Board("重要公告")

# 发布指定用户看板（有 To 即为本地）
await yunhu.Send.To("user", "user123").Board("指定用户看板")

# 发布 1 小时后过期的看板（相对时长）
await yunhu.Send.Expire(3600).Board("一小时后过期")

# 发布指定时间戳过期的看板（绝对时间戳，秒级）
await yunhu.Send.To("group", "big").ExpireAt(1785208268).Board("指定时间后过期")

# 发布指定群聊指定用户可见的看板
await yunhu.Send.To("group", "big").ForMember("11451419180").Board("只有特定群聊特定用户可见")

# 发送特定消息类型的看板
await yunhu.Send.To("group", "big").Board("看板内容", content_type="markdown")

# 撤销看板
await yunhu.Send.To("group", "group456").DismissBoard()
await yunhu.Send.DismissBoard()

# 群组管理：移除群成员
await yunhu.Send.To("group", "group456").Kick("user789")

# 群组管理：用户禁言（10分钟）
await yunhu.Send.To("group", "group456").Ban("user789", duration=600)

# 群组管理：解除禁言
await yunhu.Send.To("group", "group456").Ban("user789", duration=0)

# 群组管理：创建群标签
await yunhu.Send.To("group", "group456").CreateTag("VIP", color="#FF5733", desc="VIP会员")

# 群组管理：修改群标签
await yunhu.Send.To("group", "group456").EditTag("VIP", new_tag="SVIP", color="#33C4FF")

# 群组管理：删除群标签
await yunhu.Send.To("group", "group456").DeleteTag("VIP")

# 群组管理：获取群标签列表
result = await yunhu.Send.To("group", "group456").GetTagList()

# 群组管理：给用户添加标签
await yunhu.Send.To("group", "group456").AddUserTag("user789", "VIP")

# 群组管理：移除用户标签
await yunhu.Send.To("group", "group456").RemoveUserTag("user789", "VIP")

# 群组管理：限制消息类型
await yunhu.Send.To("group", "group456").SetMsgTypeLimit("text,image,video")

# 获取会话历史消息（用户/群均可）
# 获取群最近10条消息
result = await yunhu.Send.To("group", "group456").GetMessages(before=10)

# 获取指定消息ID前后各10条消息（共21条）
result = await yunhu.Send.To("group", "group456").GetMessages(message_id="msg_xxx", before=10, after=10)
```

> Text/Html/Markdown 的发送支持使用list传入多个id进行批量发送 | 而不再推荐使用 await yunhu.Send.To("user", ["user1", "user2"]).Batch("批量通知")

---

### 配置说明

首次运行会生成配置。云湖适配器支持多机器人配置。

#### 首次运行生成的默认配置

```toml
[Yunhu_Adapter.accounts.default]
token = ""            # 机器人token（必填，请修改为实际token）
mode = "ws"           # 接收模式: "ws" 或 "webhook"
webhook_path = "/webhook"  # Webhook路径（仅webhook模式生效）
enabled = true
name = ""
```

#### 多Bot配置示例

```toml
# WebSocket 长连接模式（默认）
[Yunhu_Adapter.accounts.bot1]
token = "your_bot1_token"
enabled = true

# Webhook 模式（需公网服务器）
[Yunhu_Adapter.accounts.bot2]
token = "your_bot2_token"
mode = "webhook"
webhook_path = "/webhook/bot2"
enabled = true
```

**配置项说明：**
- `token`：云湖平台提供的API token（必填）
- `mode`：事件接收模式（可选，默认为`"ws"`）
  - `"ws"`：通过WebSocket长连接接收事件，无需公网IP，支持自动重连（默认）
  - `"webhook"`：通过HTTP Webhook接收事件，需配合公网可访问的服务器
- `webhook_path`：接收云湖事件的HTTP路径（仅webhook模式，可选，默认为"/webhook"）
- `enabled`：是否启用该账户（可选，默认为true）

**重要提示：**
1. 云湖平台的机器人ID在运行时自动检测，无需在配置中指定
2. ws模式会自动连接 `wss://ws.jwzhd.com/subscribe?token=<your_token>`，支持自动重连（指数退避，最长60秒）
3. webhook模式下，每个bot应有独立的`webhook_path`
4. 可以混合使用webhook和ws模式，不同bot可使用不同的接收模式

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

请参考 [云湖平台特性文档](platform-features.md) 了解云湖平台的特有功能，包括特有消息段类型、扩展字段说明、表单消息事件、按钮点击事件、机器人设置事件和快捷菜单事件等内容。

## 系列教程

从零到一学习云湖机器人开发：[ErisPulse x 云湖 · 系列教程](./YunhuPost/README.md)（安装配置 → SendDSL → 命令系统 → 数据存储 → 交互 → Api 标准动作，共 10 篇）。

## 事件监听示例

### 使用 Event 模块（推荐）

```python
from ErisPulse import sdk
from ErisPulse.Core.Event import message, notice, command

@message.on_message()
async def handle_message(event):
    if event.get_platform() == "yunhu":
        bot_id = event.get_self_user_id()
        await event.reply(f"收到消息，Bot: {bot_id}")

@notice.on_notice()
async def handle_notice(event):
    if event.get_platform() == "yunhu":
        dt = event.get("detail_type")
        if dt == "yunhu_button_click":
            btn = event.get("yunhu_button", {})
            await event.reply(f"按钮点击: {btn.get('value')}")

@command("test")
async def handle_command(event):
    await event.reply("测试命令已收到")
```

### 云湖 EventMixin 扩展方法

云湖适配器为事件对象注册了平台扩展方法，可在事件处理器中直接调用：

```python
@message.on_message()
async def handle(event):
    if event.get_platform() != "yunhu":
        return
    # 发送者信息
    role = event.get_sender_role()         # owner / admin / member（标准映射）
    avatar = event.get_sender_avatar()     # 头像 URL
    level = event.get_sender_level()       # 云湖原生级别

@notice.on_notice()
async def handle_notice(event):
    if event.is_button_click():
        value = event.get_button_value()   # 按钮值
    elif event.is_a2ui_button():
        action = event.get_a2ui_action()   # A2UI 操作名
        ctx = event.get_a2ui_form_context()  # 表单上下文
```

可用方法：`get_sender_role` / `get_sender_title` / `get_sender_level` / `get_sender_avatar` / `get_raw_event` / `get_command` / `get_button_value` / `get_a2ui_action` / `get_a2ui_form_context` / `get_menu_id` / `get_setting` / `is_command_message` / `is_button_click` / `is_a2ui_button`。

## 标准 API 动作（Api DSL）

跨平台标准动作通过 `Api` 调用（详见 [平台特性文档](platform-features.md#标准-api-动作apidsl)）：

```python
yunhu = sdk.adapter.get("yunhu")

# 信息查询（公开 Web API，无需鉴权）
await yunhu.Api.get_self_info()
await yunhu.Api.get_user_info("7058262")
await yunhu.Api.get_group_info("635409929")

# 文件上传 / 撤回消息
await yunhu.Api.upload_file(type="path", name="a.png", path="./a.png")
await yunhu.Api.delete_message("msg_id", chat_id="123", chat_type="group")

# 平台扩展动作
await yunhu.Api.call("yunhu.kick", group_id="123", user_id="456")
await yunhu.Api.call("yunhu.set_member_title", group_id="123", user_id="456", title="VIP")
```

## 注意事项

1. 事件处理器通过装饰器在模块加载时自动注册，无需手动调用
2. 生产环境建议配置服务器反向代理指向 webhook 地址以实现 HTTPS
3. 二进制内容（图片/视频等）支持 `bytes`、本地路径、URL 三种传入方式
4. 程序退出时框架会自动调用适配器的 `shutdown()` 释放资源
5. 云湖平台的事件不包含机器人ID，适配器会在启动时自动探测 bot_id（向空群发探测请求解析错误信息）
6. 多 Bot 配置时，确保每个 Bot 有独立的 `webhook_path`，并在云湖平台配置对应URL

---

### 参考链接

- [ErisPulse 主库](https://github.com/ErisPulse/ErisPulse/)
- [云湖官方文档](https://www.yhchat.com/document/1-3)
- [模块开发指南](https://github.com/ErisPulse/ErisPulse/tree/main/docs/DEVELOPMENT.md)
