# 云湖适配器与OneBot12协议的转换对照

## 云湖特有事件类型

云湖平台提供以下特有事件类型，可在消息处理中检测使用：

### 1. 普通消息事件
- **eventType**: `message.receive.normal`
- **说明**: 用户发送的普通消息（文本、图片、视频、文件、表情包等）
- **转换后**: OneBot12 `message` 事件，`detail_type` 为 `private` 或 `group`

### 2. 指令消息事件
- **eventType**: `message.receive.instruction`
- **说明**: 用户发送的表单指令消息，包含结构化表单数据
- **转换后**: OneBot12 `message` 事件，包含 `yunhu_command` 字段和 `yunhu_form` 消息段

### 3. 关注机器人事件
- **eventType**: `bot.followed`
- **说明**: 用户关注/添加机器人为好友
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `friend_increase`

### 4. 取消关注机器人事件
- **eventType**: `bot.unfollowed`
- **说明**: 用户取消关注/删除机器人好友
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `friend_decrease`

### 5. 加入群事件
- **eventType**: `group.join`
- **说明**: 用户加入机器人所在的群
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `group_member_increase`

### 6. 退出群事件
- **eventType**: `group.leave`
- **说明**: 用户退出机器人所在的群
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `group_member_decrease`

### 7. 消息中按钮点击事件
- **eventType**: `button.report.inline`
- **说明**: 用户点击消息中的按钮（仅 `actionType=3` 点击汇报类型会触发）
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `yunhu_button_click`

### 8. 快捷菜单事件
- **eventType**: `bot.shortcut.menu`
- **说明**: 用户触发快捷菜单
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `yunhu_shortcut_menu`

### 9. 机器人设置事件
- **eventType**: `bot.setting`
- **说明**: 用户在群中修改机器人设置
- **转换后**: OneBot12 `notice` 事件，`detail_type` 为 `yunhu_bot_setting`

### 事件处理示例

```python
from ErisPulse.Core.Event import notice, message

# 处理普通消息
@message.on_message()
async def handle_message(event):
    if event.get("detail_type") == "group":
        text = event.get_text()
        # 处理群消息...
    else:
        # 处理私聊消息...

# 处理通知事件（包括所有云湖特有事件）
@notice.on_notice()
async def handle_notice(event):
    detail_type = event.get("detail_type")

    if detail_type == "friend_increase":
        # 新用户关注机器人
        user_id = event.get_user_id()
        await event.reply("欢迎关注！")

    elif detail_type == "friend_decrease":
        # 用户取消关注
        user_id = event.get_user_id()

    elif detail_type == "group_member_increase":
        # 新成员加群
        group_id = event.get_group_id()
        user_id = event.get_user_id()
        await event.reply(f"欢迎新成员 {event.get_user_nickname()}！")

    elif detail_type == "group_member_decrease":
        # 成员退群
        group_id = event.get_group_id()

    elif detail_type == "yunhu_button_click":
        # 按钮点击事件
        user_id = event.get_user_id()
        button_value = event.get("yunhu_button", {}).get("value", "")
        await event.reply(f"你点击了: {button_value}")

    elif detail_type == "yunhu_shortcut_menu":
        # 快捷菜单事件
        menu_info = event.get("yunhu_menu", {})
        menu_id = menu_info.get("id", "")

    elif detail_type == "yunhu_bot_setting":
        # 机器人设置变更
        settings = event.get("yunhu_setting", {})
        group_id = event.get("group_id", "")
```

---

### 1. 文本消息（普通消息）

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "e4c11b08a7b74bbab89cfa5bf3ac8426",
    "eventType": "message.receive.normal",
    "eventTime": 1752471707745
  },
  "event": {
    "sender": {
      "senderId": "5197892",
      "senderType": "user",
      "senderUserLevel": "owner",
      "senderNickname": "YingXinche"
    },
    "chat": {
      "chatId": "853732258",
      "chatType": "group"
    },
    "message": {
      "msgId": "5922f47e4a334b4f86915b0bfc02d553",
      "parentId": "",
      "sendTime": 1752471707736,
      "chatId": "853732258",
      "chatType": "group",
      "contentType": "text",
      "content": {
        "text": "1"
      },
      "instructionId": 0,
      "instructionName": "",
      "commandId": 0,
      "commandName": ""
    }
  }
}
```
转换后
```json
{
  "id": "e4c11b08a7b74bbab89cfa5bf3ac8426",
  "time": 1752471707,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "message_id": "5922f47e4a334b4f86915b0bfc02d553",
  "message": [
    {
      "type": "text",
      "data": {
        "text": "1"
      }
    }
  ],
  "alt_message": "1",
  "user_id": "5197892",
  "user_nickname": "YingXinche",
  "group_id": "853732258"
}
```

### 2. 图片消息

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "ec4f242e3e244d7088b085815a90c4c9",
    "eventType": "message.receive.normal",
    "eventTime": 1752471718575
  },
  "event": {
    "sender": {
      "senderId": "5197892",
      "senderType": "user",
      "senderUserLevel": "owner",
      "senderNickname": "YingXinche"
    },
    "chat": {
      "chatId": "853732258",
      "chatType": "group"
    },
    "message": {
      "msgId": "9c2ce3ef32774479854ca04a3bf3738b",
      "parentId": "",
      "sendTime": 1752471718404,
      "chatId": "853732258",
      "chatType": "group",
      "contentType": "image",
      "content": {
        "imageUrl": "https://chat-storage1.jwznb.com/b035eeac93d31ec33cb5a106cdf10d07.png?sign=71a455d9a51152b03ce213dc621fb7f4&t=6874a6b6",
        "imageName": "b035eeac93d31ec33cb5a106cdf10d07.png",
        "etag": "Fp8HilojhNGBJugfq1odZiP3Y-i-",
        "imageWidth": 48,
        "imageHeight": 25
      },
      "instructionId": 0,
      "instructionName": "",
      "commandId": 0,
      "commandName": ""
    }
  }
}
```
转换后
```json
{
  "id": "ec4f242e3e244d7088b085815a90c4c9",
  "time": 1752471718,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "message_id": "9c2ce3ef32774479854ca04a3bf3738b",
  "message": [
    {
      "type": "image",
      "data": {
        "file_id": "https://chat-storage1.jwznb.com/b035eeac93d31ec33cb5a106cdf10d07.png?sign=71a455d9a51152b03ce213dc621fb7f4&t=6874a6b6",
        "url": "https://chat-storage1.jwznb.com/b035eeac93d31ec33cb5a106cdf10d07.png?sign=71a455d9a51152b03ce213dc621fb7f4&t=6874a6b6",
        "file_name": "b035eeac93d31ec33cb5a106cdf10d07.png",
        "width": 48,
        "height": 25
      }
    }
  ],
  "alt_message": "[图片:b035eeac93d31ec33cb5a106cdf10d07.png]",
  "user_id": "5197892",
  "user_nickname": "YingXinche",
  "group_id": "853732258"
}
```

### 3. 视频消息

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "318a40dc58194503aac43fb0aa10d989",
    "eventType": "message.receive.normal",
    "eventTime": 1752471734500
  },
  "event": {
    "sender": {
      "senderId": "5197892",
      "senderType": "user",
      "senderUserLevel": "owner",
      "senderNickname": "YingXinche"
    },
    "chat": {
      "chatId": "853732258",
      "chatType": "group"
    },
    "message": {
      "msgId": "a8f74727a01d4c9ba5bdd2dbade72169",
      "parentId": "",
      "sendTime": 1752471734088,
      "chatId": "853732258",
      "chatType": "group",
      "contentType": "video",
      "content": {
        "etag": "lpxYPI2jzL-TLIiw7Md6Xu24r8ED",
        "videoUrl": "8dd8b1491001f6ae1f37f58ebed21e35.mp4",
        "videoDuration": 57
      },
      "instructionId": 0,
      "instructionName": "",
      "commandId": 0,
      "commandName": ""
    }
  }
}
```
转换后
```json
{
  "id": "318a40dc58194503aac43fb0aa10d989",
  "time": 1752471734,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "message_id": "a8f74727a01d4c9ba5bdd2dbade72169",
  "message": [
    {
      "type": "video",
      "data": {
        "file_id": "8dd8b1491001f6ae1f37f58ebed21e35.mp4",
        "url": "8dd8b1491001f6ae1f37f58ebed21e35.mp4",
        "file_name": "",
        "width": 0,
        "height": 0,
        "duration": 57
      }
    }
  ],
  "alt_message": "[视频:]",
  "user_id": "5197892",
  "user_nickname": "YingXinche",
  "group_id": "853732258"
}
```

### 4. 文件消息

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "9cbc1d5840a547f2a7f98342d6d995ff",
    "eventType": "message.receive.normal",
    "eventTime": 1752471740254
  },
  "event": {
    "sender": {
      "senderId": "5197892",
      "senderType": "user",
      "senderUserLevel": "owner",
      "senderNickname": "YingXinche"
    },
    "chat": {
      "chatId": "853732258",
      "chatType": "group"
    },
    "message": {
      "msgId": "d713f5beccfb4d5894af25d36a8dd2f1",
      "parentId": "",
      "sendTime": 1752471740246,
      "chatId": "853732258",
      "chatType": "group",
      "contentType": "file",
      "content": {
        "fileName": "cline_task_jun-5-2025_9-33-00-pm.md",
        "fileUrl": "920be2c6723242e08ee75e0faee87611",
        "etag": "FtTNpPdS5ZAlnhXBP5EfdvoIg_XX",
        "fileSize": 23900
      },
      "instructionId": 0,
      "instructionName": "",
      "commandId": 0,
      "commandName": ""
    }
  }
}
```
转换后
```json
{
  "id": "9cbc1d5840a547f2a7f98342d6d995ff",
  "time": 1752471740,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "message_id": "d713f5beccfb4d5894af25d36a8dd2f1",
  "message": [
    {
      "type": "file",
      "data": {
        "file_id": "920be2c6723242e08ee75e0faee87611",
        "url": "920be2c6723242e08ee75e0faee87611",
        "file_name": "cline_task_jun-5-2025_9-33-00-pm.md",
        "size": 23900
      }
    }
  ],
  "alt_message": "[文件:cline_task_jun-5-2025_9-33-00-pm.md]",
  "user_id": "5197892",
  "user_nickname": "YingXinche",
  "group_id": "853732258"
}
```

### 5. 指令消息（带表单）

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "04a528cd53aa4f9b8ccd16868645c172",
    "eventType": "message.receive.instruction",
    "eventTime": 1752471814418
  },
  "event": {
    "sender": {
      "senderId": "2129537",
      "senderType": "user",
      "senderUserLevel": "member",
      "senderNickname": "北医六院精神科"
    },
    "chat": {
      "chatId": "30535459",
      "chatType": "bot"
    },
    "message": {
      "msgId": "da865dea10df4ab299624d634015e654",
      "parentId": "",
      "sendTime": 1752471814408,
      "chatId": "30535459",
      "chatType": "bot",
      "contentType": "form",
      "content": {
        "formJson": {
          "abgapt": {
            "id": "abgapt",
            "type": "textarea",
            "label": null,
            "value": ""
          },
          "mnabyo": {
            "selectIndex": 0,
            "selectValue": "",
            "id": "mnabyo",
            "type": "select",
            "label": null
          },
          "gvanmu": {
            "id": "gvanmu",
            "type": "radio",
            "label": null,
            "selectIndex": -1,
            "selectValue": ""
          },
          "gurpgk": {
            "id": "gurpgk",
            "type": "input",
            "label": null,
            "value": null
          },
          "owtgcl": {
            "id": "owtgcl",
            "type": "switch",
            "label": null,
            "value": false
          },
          "qkmlif": {
            "id": "qkmlif",
            "type": "checkbox",
            "label": null,
            "selectStatus": [
              false
            ],
            "selectValues": []
          }
        }
      },
      "instructionId": 1766,
      "instructionName": "123123",
      "commandId": 1766,
      "commandName": "123123"
    }
  }
}
```
转换后
```json
{
  "id": "04a528cd53aa4f9b8ccd16868645c172",
  "time": 1752471814,
  "type": "message",
  "detail_type": "private",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": "30535459"
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "message_id": "da865dea10df4ab299624d634015e654",
  "message": [
    {
      "type": "yunhu_form",
      "data": {
        "id": 1766,
        "name": "123123",
        "fields": [
          {
            "id": "abgapt",
            "type": "textarea",
            "label": null,
            "value": ""
          },
          {
            "id": "mnabyo",
            "type": "select",
            "label": null,
            "value": ""
          },
          {
            "id": "gvanmu",
            "type": "radio",
            "label": null,
            "value": ""
          },
          {
            "id": "gurpgk",
            "type": "input",
            "label": null,
            "value": null
          },
          {
            "id": "owtgcl",
            "type": "switch",
            "label": null,
            "value": "False"
          },
          {
            "id": "qkmlif",
            "type": "checkbox",
            "label": null,
            "value": ""
          }
        ]
      }
    }
  ],
  "alt_message": "[表单:123123]",
  "user_id": "2129537",
  "user_nickname": "北医六院精神科",
  "yunhu_command": {
    "name": "123123",
    "id": "1766",
    "args": "",
    "form": {
      "abgapt": {
        "id": "abgapt",
        "type": "textarea",
        "label": null,
        "value": ""
      },
      "mnabyo": {
        "selectIndex": 0,
        "selectValue": "",
        "id": "mnabyo",
        "type": "select",
        "label": null
      },
      "gvanmu": {
        "id": "gvanmu",
        "type": "radio",
        "label": null,
        "selectIndex": -1,
        "selectValue": ""
      },
      "gurpgk": {
        "id": "gurpgk",
        "type": "input",
        "label": null,
        "value": null
      },
      "owtgcl": {
        "id": "owtgcl",
        "type": "switch",
        "label": null,
        "value": false
      },
      "qkmlif": {
        "id": "qkmlif",
        "type": "checkbox",
        "label": null,
        "selectStatus": [
          false
        ],
        "selectValues": []
      }
    }
  }
}
```

### 6. 按钮点击事件

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "6e74603b06854b06b0103d62a7c86867",
    "eventType": "button.report.inline",
    "eventTime": 1752471702516
  },
  "event": {
    "time": 1752471702513,
    "msgId": "168da7860ce040efa346bcbf54c1f45e",
    "recvId": "853732258",
    "recvType": "group",
    "userId": "5197892",
    "value": "test_button_value"
  }
}
```
转换后
```json
{
  "id": "6e74603b06854b06b0103d62a7c86867",
  "time": 1752471702,
  "type": "notice",
  "detail_type": "yunhu_button_click",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "user_id": "5197892",
  "user_nickname": "YingXinche",
  "message_id": "168da7860ce040efa346bcbf54c1f45e",
  "yunhu_button": {
    "id": "",
    "value": "test_button_value"
  }
}
```

### 7. 关注机器人事件

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "39d9d0a90c4d4228a709a5e4a1582d02",
    "eventType": "bot.followed",
    "eventTime": 1752471787508
  },
  "event": {
    "time": 1752471787494,
    "chatId": "30535459",
    "chatType": "bot",
    "userId": "2129537",
    "nickname": "北医六院精神科",
    "avatarUrl": "https://chat-storage1.jwznb.com/953ac44df2c868727e399d491e5e7090.jpg?sign=3bd02bfd1fed3a87fca8264a5b17078a&t=6874a6fb"
  }
}
```
转换后
```json
{
  "id": "39d9d0a90c4d4228a709a5e4a1582d02",
  "time": 1752471787,
  "type": "notice",
  "detail_type": "friend_increase",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": "30535459"
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "user_id": "2129537",
  "user_nickname": "北医六院精神科"
}
```

### 8. 用户加群事件

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "15cc20a2f3464ac7a621eaf04e3e2a4b",
    "eventType": "group.join",
    "eventTime": 1752472053581
  },
  "event": {
    "time": 1752472053558,
    "chatId": "635409929",
    "chatType": "group",
    "userId": "2129537",
    "nickname": "北医六院精神科",
    "avatarUrl": "https://chat-storage1.jwznb.com/953ac44df2c868727e399d491e5e7090.jpg?sign=c196eed102f9bc1397d79fd827e0d374&t=6874a805"
  }
}
```
转换后
```json
{
  "id": "15cc20a2f3464ac7a621eaf04e3e2a4b",
  "time": 1752472053,
  "type": "notice",
  "detail_type": "group_member_increase",
  "sub_type": "invite",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "group_id": "635409929",
  "user_id": "2129537",
  "user_nickname": "北医六院精神科",
  "operator_id": ""
}
```


### 9. 机器人设置事件


原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "1d66a0c0132e4519a4063276485d24bd",
    "eventType": "bot.setting",
    "eventTime": 1752471938486
  },
  "event": {
    "time": 1752471938483,
    "chatId": "30535459",
    "chatType": "bot",
    "groupId": "635409929",
    "groupName": "ErisPulse",
    "avatarUrl": "https://chat-img.jwznb.com/cd0ea50d0e21eab0ddb67505cd274dc3.jpg",
    "settingJson": "{\"lokola\":{\"id\":\"lokola\",\"type\":\"radio\",\"label\":null,\"selectIndex\":-1,\"selectValue\":\"\"},\"ngcezg\":{\"id\":\"ngcezg\",\"type\":\"input\",\"label\":null,\"value\":null},\"bvxrzf\":{\"id\":\"bvxrzf\",\"type\":\"switch\",\"label\":null,\"value\":false},\"fzgsya\":{\"id\":\"fzgsya\",\"type\":\"checkbox\",\"label\":null,\"selectStatus\":[false],\"selectValues\":[]},\"ljmgbp\":{\"id\":\"ljmgbp\",\"type\":\"textarea\",\"label\":null,\"value\":\"\"},\"azyfwy\":{\"id\":\"azyfwy\",\"type\":\"select\",\"label\":null,\"selectIndex\":0,\"selectValue\":\"\"}}"
  }
}
```
转换后
```json
{
  "id": "1d66a0c0132e4519a4063276485d24bd",
  "time": 1752471938,
  "type": "notice",
  "detail_type": "yunhu_bot_setting",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": "30535459"
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "group_id": "635409929",
  "user_nickname": "北医六院精神科",
  "yunhu_setting": "{\"lokola\":{\"id\":\"lokola\",\"type\":\"radio\",\"label\":null,\"selectIndex\":-1,\"selectValue\":\"\"},\"ngcezg\":{\"id\":\"ngcezg\",\"type\":\"input\",\"label\":null,\"value\":null},\"bvxrzf\":{\"id\":\"bvxrzf\",\"type\":\"switch\",\"label\":null,\"value\":false},\"fzgsya\":{\"id\":\"fzgsya\",\"type\":\"checkbox\",\"label\":null,\"selectStatus\":[false],\"selectValues\":[]},\"ljmgbp\":{\"id\":\"ljmgbp\",\"type\":\"textarea\",\"label\":null,\"value\":\"\"},\"azyfwy\":{\"id\":\"azyfwy\",\"type\":\"select\",\"label\":null,\"selectIndex\":0,\"selectValue\":\"\"}}"
}
```

### 10. 快捷菜单事件

原始事件:
```json
{
  "version": "1.0",
  "header": {
    "eventId": "e43bf93f28ee42bdbb5b8d4d6120d79a",
    "eventType": "bot.shortcut.menu",
    "eventTime": 1752472004836
  },
  "event": {
    "botId": "30535459",
    "menuId": "B4X00M5B",
    "menuType": 1,
    "menuAction": 1,
    "chatId": "853732258",
    "chatType": "group",
    "senderType": "user",
    "senderId": "5197892",
    "sendTime": 1752472004
  }
}
```
转换后
```json
{
  "id": "e43bf93f28ee42bdbb5b8d4d6120d79a",
  "time": 1752472004,
  "type": "notice",
  "detail_type": "yunhu_shortcut_menu",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "yunhu_raw": {
    ... # 省略，原始事件内容
  },
  "user_id": "5197892",
  "user_nickname": "YingXinche",
  "group_id": "853732258",
  "yunhu_menu": {
    "id": "B4X00M5B",
    "type": 1,
    "action": 1
  }
}
```

---

## 云湖发送消息类型（OneBot12扩展）

云湖适配器支持使用 OneBot12 消息段格式发送消息，支持以下类型：

### 1. 基础消息类型

| 类型 | 说明 | 参数 |
|------|------|------|
| `text` | 纯文本 | `text`: 文本内容 |
| `html` | HTML格式 | `html`: HTML代码 |
| `markdown` | Markdown格式 | `markdown`: Markdown代码 |

### 2. 媒体消息类型

| 类型 | 说明 | 参数 |
|------|------|------|
| `image` | 图片 | `file`: 文件/URL, `stream`: 是否流式, `filename`: 文件名 |
| `video` | 视频 | `file`: 文件/URL, `stream`: 是否流式, `filename`: 文件名 |
| `file` | 文件 | `file`: 文件/URL, `stream`: 是否流式, `filename`: 文件名 |
| `audio` | 语音/音频 | `file`: 文件/URL, `stream`: 是否流式, `filename`: 文件名 |

### 3. 云湖特有类型

| 类型 | 说明 | 参数 |
|------|------|------|
| `yunhu_expression` | 表情包/贴纸 | `sticker_id`: 贴纸ID, `sticker_pack_id`: 贴纸包ID |
| `yunhu_button` | 按钮 | ��下方按钮格式 |
| `reply` | 回复消息 | `message_id`: 消息ID |
| `mention` | @用户 | `user_id`: 用户ID |

### 按钮格式

```python
# 按钮格式示例
buttons = [
    [
        {"text": "按钮文字", "actionType": 1, "url": "http://example.com"},      # 跳转URL
        {"text": "复制", "actionType": 2, "value": "复制的内容"},              # 复制到剪贴板
        {"text": "确认", "actionType": 3, "value": "confirm"}               # 点击汇报
    ]
]

# 使用 Raw_ob12 发送带按钮消息
message = [
    {"type": "text", "data": {"text": "请确认操作"}},
    {"type": "yunhu_button", "data": {"buttons": buttons}}
]
await yunhu.Send.To("group", group_id).Raw_ob12(message)
```

### 4. 流式消息类型

云湖支持流式消息发送，适合长文本或大文件的渐进式发送：

```python
async def text_generator():
    """文本流式生成器"""
    for i in range(10):
        yield f"第 {i+1} 行内容\n"
        await asyncio.sleep(0.5)

# 发送流式文本消息
await yunhu.Send.To("group", group_id).Stream(
    content_type="text",
    content_generator=text_generator()
)
```

#### 支持的流式类型

| content_type | 说明 |
|------------|------|
| `text` | 流式文本 |
| `markdown` | 流式Markdown |
| `html` | 流式HTML |

### 5. 使用链式调用发送

```python
# 基础发送
await yunhu.Send.To("group", "123").Text("Hello")

# 发送带@的消息
await yunhu.Send.To("group", "123").At("user1").At("user2").Text("@成员")

# 发送带按钮的消息
buttons = [[{"text": "确认", "actionType": 3, "value": "ok"}]]
await yunhu.Send.To("group", "123").Buttons(buttons).Text("请确认")

# 发送回复消息
await yunhu.Send.To("group", "123").Reply("msg_id").Text("回复内容")

# 组合使用
await yunhu.Send.To("group", "123").Reply("msg_id").At("user1").Buttons(buttons).Text("复合消息")

# 使用 Raw_ob12 发送复杂消息
message = [
    {"type": "text", "data": {"text": "第一行"}},
    {"type": "image", "data": {"file": "http://example.com/img.jpg"}},
    {"type": "text", "data": {"text": "第二行"}}
]
await yunhu.Send.To("group", "123").Raw_ob12(message)
```

### 6. 批量发送

```python
# 批量发送到用户列表
user_ids = ["user1", "user2", "user3"]
await yunhu.Send.To("user", user_ids).Text("批量消息")

# 批量发送到群列表
group_ids = ["group1", "group2"]
await yunhu.Send.To("group", group_ids).Text("群发消息")
```

### 7. 消息操作

```python
# 撤回消息
await yunhu.Send.To("group", "123").Recall("message_id")

# 编辑消息
await yunhu.Send.To("group", "123").Edit(
    msg_id="message_id",
    text="新内容",
    content_type="text",
    buttons=buttons
)
```

### 8. 公告看板

```python
# 发布本地公告（指定群）
await yunhu.Send.To("group", "123").Board(
    scope="local",
    content="公告内容",
    content_type="text"
)

# 发布全局公告
await yunhu.Send.Board(
    scope="global",
    content="全局公告",
    content_type="text"
)

# 撤销公告
await yunhu.Send.To("group", "123").DismissBoard(scope="local")
await yunhu.Send.DismissBoard(scope="global")
```