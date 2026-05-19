import asyncio
from ErisPulse import sdk
from ErisPulse.Core.Event import notice

TEST_USER_ID = "5197892"
A2UI_Text = """

```json
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "button_demo",
    "catalogId": "https://a2ui.org/specification/v0_9/standard_catalog.json",
    "sendDataModel": true
  }
}
```


```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "button_demo",
    "components": [
      {
        "id": "root",
        "component": "Column",
        "justify": "center",
        "align": "center",
        "children": [
          "titleText",
          "infoText",
          "actionButton",
          "statusText"
        ]
      },
      {
        "id": "titleText",
        "component": "Text",
        "text": "按钮测试示例",
        "variant": "h2"
      },
      {
        "id": "infoText",
        "component": "Text",
        "text": "点击下面的按钮测试功能：",
        "variant": "body"
      },
      {
        "id": "actionButton",
        "component": "Button",
        "child": "buttonLabel",
        "action": {
          "event": {
            "name": "buttonClicked",
            "context": {
              "timestamp": "2024-01-01T00:00:00Z",
              "message": "按钮被点击了！"
            }
          }
        },
        "variant": "primary"
      },
      {
        "id": "buttonLabel",
        "component": "Text",
        "text": "点击我"
      },
      {
        "id": "statusText",
        "component": "Text",
        "text": "等待点击...",
        "variant": "caption"
      }
    ]
  }
}
```

"""

@notice.on_notice()
async def handle_a2ui_button(event):
    if event.get("detail_type") != "yunhu_a2ui_button":
        return

    user_id = event.get_user_id()
    user_nickname = event.get_user_nickname() or "用户"
    a2ui = event.get("yunhu_a2ui", {})
    action_name = a2ui.get("action_name", "")
    form_context = a2ui.get("form_context", {})
    interaction_json = a2ui.get("interaction_json", "")

    sdk.logger.info(
        f"A2UI按钮事件: 用户 {user_nickname}({user_id}) "
        f"action={action_name} form={form_context} interaction={interaction_json}"
    )

    msg_id = event.get("message_id", "")
    if msg_id:
        yunhu = sdk.adapter.get("yunhu")
        updated_text = A2UI_Text.replace("等待点击...", "已点击")
        rs = await yunhu.Send.To("user", user_id).Edit(msg_id, updated_text, content_type="a2ui")
        sdk.logger.info(f"已编辑消息 {msg_id} 状态为「已点击」 | {rs}")


async def main():
    try:
        isInit = await sdk.init_task()
        if not isInit:
            sdk.logger.error("ErisPulse 初始化失败")
            return

        await sdk.adapter.startup()
        await asyncio.sleep(3)

        yunhu = sdk.adapter.get("yunhu")
        result = await yunhu.Send.To("user", TEST_USER_ID).A2UI(A2UI_Text)
        sdk.logger.info(f"发送结果: {result}")

        await asyncio.Event().wait()
    except KeyboardInterrupt:
        sdk.logger.info("正在停止")
    finally:
        await sdk.adapter.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
