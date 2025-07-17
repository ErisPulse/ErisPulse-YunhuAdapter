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

这仅仅在 sdk.adapter.yunhu.on() 的时候生效，你完全可以使用 标准OneBot12 事件（sdk.adapter.on）来获取信息

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
首次运行会生成配置，内容及解释如下


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
