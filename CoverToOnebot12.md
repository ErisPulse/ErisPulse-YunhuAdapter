# 云湖适配器与OneBot12协议的转换对照

### 1. 文本消息（普通消息）
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "c192ccc83d5147f2859ca77bcfafc9f9",
    "eventType": "message.receive.normal",
    "eventTime": 1748613099002
  },
  "event": {
    "sender": {
      "senderId": "6300451",
      "senderType": "user",
      "senderUserLevel": "owner",
      "senderNickname": "ShanFish"
    },
    "chat": {
      "chatId": "49871624",
      "chatType": "bot"
    },
    "message": {
      "msgId": "5c887bc0a82244c7969c08000f5b3ae8",
      "parentId": "",
      "sendTime": 1748613098989,
      "chatId": "49871624",
      "chatType": "bot",
      "contentType": "text",
      "content": {
        "text": "你好"
      }
    }
  }
}
```
OneBot12协议输出：
```json
{
  "id": "c192ccc83d5147f2859ca77bcfafc9f9",
  "time": 1748613099,
  "type": "message",
  "detail_type": "private",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": "49871624"
  },
  "message_id": "5c887bc0a82244c7969c08000f5b3ae8",
  "message": [
    {
      "type": "text",
      "data": {
        "text": "你好"
      }
    }
  ],
  "alt_message": "你好",
  "user_id": "6300451"
}
```
### 2. 图片消息
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "74e2567cf0494f37af1beee9a37c7cd3",
    "eventType": "message.receive.normal",
    "eventTime": 1752083350157
  },
  "event": {
    "sender": {
      "senderId": "2129537",
      "senderType": "user",
      "senderUserLevel": "member",
      "senderNickname": "用户2129537"
    },
    "chat": {
      "chatId": "635409929",
      "chatType": "group"
    },
    "message": {
      "msgId": "8d104a58549648e8b7c4bfe23aba6ae0",
      "contentType": "image",
      "content": {
        "imageUrl": "https://chat-storage1.jwznb.com/e22aacd7951783a51a1dcd5f602e5428.jpg",
        "imageName": "e22aacd7951783a51a1dcd5f602e5428.jpg",
        "imageWidth": 8000,
        "imageHeight": 6000
      }
    }
  }
}
```
OneBot12协议输出：
```json
{
  "id": "74e2567cf0494f37af1beee9a37c7cd3",
  "time": 1752083350,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "message_id": "8d104a58549648e8b7c4bfe23aba6ae0",
  "message": [
    {
      "type": "image",
      "data": {
        "file_id": "https://chat-storage1.jwznb.com/e22aacd7951783a51a1dcd5f602e5428.jpg",
        "url": "https://chat-storage1.jwznb.com/e22aacd7951783a51a1dcd5f602e5428.jpg",
        "file_name": "e22aacd7951783a51a1dcd5f602e5428.jpg",
        "width": 8000,
        "height": 6000
      }
    }
  ],
  "alt_message": "",
  "user_id": "2129537",
  "group_id": "635409929"
}
```
### 3. 视频消息
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "6839c7755f544fd7b6f21d62f4e00401",
    "eventType": "message.receive.normal",
    "eventTime": 1752083413361
  },
  "event": {
    "sender": {
      "senderId": "2129537",
      "senderType": "user",
      "senderUserLevel": "member",
      "senderNickname": "用户2129537"
    },
    "chat": {
      "chatId": "635409929",
      "chatType": "group"
    },
    "message": {
      "msgId": "18bbf7cdc6aa454b876865532da4ee22",
      "contentType": "video",
      "content": {
        "videoUrl": "ccaf1eaaaa4d1996a952e148f2b18705.mp4",
        "videoDuration": 1
      }
    }
  }
}
```
OneBot12协议输出：
```json
{
  "id": "6839c7755f544fd7b6f21d62f4e00401",
  "time": 1752083413,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "message_id": "18bbf7cdc6aa454b876865532da4ee22",
  "message": [
    {
      "type": "video",
      "data": {
        "file_id": "ccaf1eaaaa4d1996a952e148f2b18705.mp4",
        "url": "ccaf1eaaaa4d1996a952e148f2b18705.mp4",
        "file_name": "ccaf1eaaaa4d1996a952e148f2b18705.mp4",
        "duration": 1
      }
    }
  ],
  "alt_message": "",
  "user_id": "2129537",
  "group_id": "635409929"
}
```
### 4. 文件消息
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "f60a6e0fa1414f8e85803e12f9b20613",
    "eventType": "message.receive.normal",
    "eventTime": 1752083425408
  },
  "event": {
    "sender": {
      "senderId": "2129537",
      "senderType": "user",
      "senderUserLevel": "member",
      "senderNickname": "用户2129537"
    },
    "chat": {
      "chatId": "635409929",
      "chatType": "group"
    },
    "message": {
      "msgId": "0957bb9e73ed4defa74b51c6efb69470",
      "contentType": "file",
      "content": {
        "fileName": "IMG_20250710_013859088.jpg",
        "fileUrl": "e22aacd7951783a51a1dcd5f602e5428.jpg",
        "fileSize": 8720285
      }
    }
  }
}
```
OneBot12协议输出：
```json
{
  "id": "f60a6e0fa1414f8e85803e12f9b20613",
  "time": 1752083425,
  "type": "message",
  "detail_type": "group",
  "sub_type": "",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "message_id": "0957bb9e73ed4defa74b51c6efb69470",
  "message": [
    {
      "type": "file",
      "data": {
        "file_id": "e22aacd7951783a51a1dcd5f602e5428.jpg",
        "url": "e22aacd7951783a51a1dcd5f602e5428.jpg",
        "file_name": "IMG_20250710_013859088.jpg",
        "size": 8720285
      }
    }
  ],
  "alt_message": "",
  "user_id": "2129537",
  "group_id": "635409929"
}
```
### 5. 指令消息（带表单）
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "5cdde5bf2f184a5e87b1da62dfc6df10",
    "eventType": "message.receive.instruction",
    "eventTime": 1752083091036
  },
  "event": {
    "sender": {
      "senderId": "5197892",
      "senderType": "user",
      "senderUserLevel": "owner",
      "senderNickname": "YingXinche"
    },
    "chat": {
      "chatId": "635409929",
      "chatType": "group"
    },
    "message": {
      "msgId": "a06d07462b1b48a6b5d39f5b85e0a95d",
      "contentType": "form",
      "content": {
        "formJson": {
          "gurpgk": {
            "value": "1",
            "type": "input"
          },
          "owtgcl": {
            "value": true,
            "type": "switch"
          }
        }
      },
      "instructionId": 1766,
      "instructionName": "123123"
    }
  }
}
```
OneBot12协议输出：
```json
{
  "id": "5cdde5bf2f184a5e87b1da62dfc6df10",
  "time": 1752083091,
  "type": "message",
  "detail_type": "group",
  "sub_type": "command",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "message_id": "a06d07462b1b48a6b5d39f5b85e0a95d",
  "message": [
    {
      "type": "form",
      "data": {
        "id": "1766",
        "name": "123123",
        "fields": [
          {
            "id": "gurpgk",
            "type": "input",
            "value": "1"
          },
          {
            "id": "owtgcl",
            "type": "switch",
            "value": "true"
          }
        ]
      }
    }
  ],
  "alt_message": "",
  "user_id": "5197892",
  "group_id": "635409929",
  "command": {
    "name": "123123",
    "id": "1766",
    "form": {
      "gurpgk": {
        "value": "1",
        "type": "input"
      },
      "owtgcl": {
        "value": true,
        "type": "switch"
      }
    }
  }
}
```
### 6. 按钮点击事件
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "0d6d269ff7f046828c8562f905f9ee08",
    "eventType": "button.report.inline",
    "eventTime": 1749446185273
  },
  "event": {
    "time": 1749446185268,
    "msgId": "1838c3dd84474e9e9e1e00ca64e72065",
    "recvId": "6300451",
    "recvType": "user",
    "userId": "6300451",
    "value": "xxxx"
  }
}
```
OneBot12协议输出：
```json
{
  "id": "0d6d269ff7f046828c8562f905f9ee08",
  "time": 1749446185,
  "type": "notice",
  "detail_type": "button_click",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "user_id": "6300451",
  "message_id": "1838c3dd84474e9e9e1e00ca64e72065",
  "button": {
    "id": "",
    "value": "xxxx"
  }
}
```
### 7. 关注机器人事件
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "3fe280a400f9460daa03a642d1fad39b",
    "eventType": "bot.followed",
    "eventTime": 1749443049592
  },
  "event": {
    "time": 1749443049580,
    "chatId": "49871624",
    "chatType": "bot",
    "userId": "3707697",
    "nickname": "ShanFishApp"
  }
}
```
OneBot12协议输出：
```json
{
  "id": "3fe280a400f9460daa03a642d1fad39b",
  "time": 1749443049,
  "type": "notice",
  "detail_type": "friend_increase",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": "49871624"
  },
  "user_id": "3707697"
}
```
### 8. 用户加群事件
云湖协议输入：
```json
{
  "version": "1.0",
  "header": {
    "eventId": "d5429cb5e4654fbcaeee9e4adb244741",
    "eventType": "group.join",
    "eventTime": 1749442891943
  },
  "event": {
    "time": 1749442891843,
    "chatId": "985140593",
    "chatType": "group",
    "userId": "3707697",
    "nickname": "ShanFishApp"
  }
}
```
OneBot12协议输出：
```json
{
  "id": "d5429cb5e4654fbcaeee9e4adb244741",
  "time": 1749442891,
  "type": "notice",
  "detail_type": "group_member_increase",
  "sub_type": "invite",
  "platform": "yunhu",
  "self": {
    "platform": "yunhu",
    "user_id": ""
  },
  "group_id": "985140593",
  "user_id": "3707697",
  "operator_id": ""
}
```