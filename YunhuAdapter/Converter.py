"""
云湖平台事件转换模块
严格遵循OneBot 12标准格式进行事件转换

{!--< tips >!--}
注意：云湖平台特有字段均添加 yunhu_ 前缀作为扩展字段
{!--< /tips >!--}
"""

import time
import uuid
from typing import Dict, Optional, List

class YunhuConverter:
    def __init__(self):
        self._setup_event_mapping()
    
    def _setup_event_mapping(self):
        """初始化事件类型映射 (符合OneBot12标准)"""
        self.event_map = {
            # 标准消息事件
            "message.receive.normal": "message",
            "message.receive.instruction": "message",
            
            # 标准通知事件
            "bot.followed": "notice.friend_increase",
            "bot.unfollowed": "notice.friend_decrease",
            "group.join": "notice.group_member_increase",
            "group.leave": "notice.group_member_decrease",
            
            # 云湖特有事件（添加yunhu_前缀）
            "button.report.inline": "notice.yunhu_button_click",
            "bot.shortcut.menu": "notice.yunhu_shortcut_menu",
            "bot.setting": "notice.yunhu_bot_setting"
        }

    def convert(self, data: Dict) -> Optional[Dict]:
        """
        主转换方法
        
        改进点：
        1. 严格分离标准字段和扩展字段
        2. 使用OneBot12标准的事件类型格式
        3. 明确区分detail_type和sub_type
        4. 所有非标准字段添加yunhu_前缀
        
        :param data: 原始事件数据
        :return: 符合OneBot12标准的事件字典
        """
        if not isinstance(data, dict):
            raise ValueError("事件数据必须是字典类型")

        header = data.get("header", {})
        event_type = header.get("eventType", "")

        if not event_type:
            raise ValueError("事件数据缺少eventType字段")

        # 基础事件结构 (OneBot12标准)
        onebot_event = {
            "id": header.get("eventId", str(uuid.uuid4())),
            "time": int(header.get("eventTime", time.time() * 1000) / 1000),
            "type": "",
            "detail_type": "",
            "sub_type": "",
            "platform": "yunhu",
            "self": {
                "platform": "yunhu",
                "user_id": ""
            },
            # 扩展字段：保留原始数据
            "yunhu_raw": data
        }

        # 解析映射类型 (type.detail_type格式)
        mapped_type = self.event_map.get(event_type, "")
        if "." in mapped_type:
            event_type_parts = mapped_type.split(".")
            onebot_event["type"] = event_type_parts[0]
            onebot_event["detail_type"] = event_type_parts[1]
            if len(event_type_parts) > 2:
                onebot_event["sub_type"] = event_type_parts[2]

        # 根据事件类型分发处理
        handler_map = {
            "message": self._handle_message_event,
            "notice.friend_increase": self._handle_friend_event,
            "notice.friend_decrease": self._handle_friend_event,
            "notice.group_member_increase": self._handle_group_member_event,
            "notice.group_member_decrease": self._handle_group_member_event,
            "notice.yunhu_button_click": self._handle_button_event,
            "notice.yunhu_shortcut_menu": self._handle_menu_event,
            "notice.yunhu_bot_setting": self._handle_setting_event
        }
        
        handler = handler_map.get(mapped_type)
        return handler(event_type, data.get("event", {}), onebot_event) if handler else None

    def _handle_message_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理消息事件 (严格遵循OneBot12消息格式)
        
        改进点：
        1. 统一消息段结构
        2. 标准内容类型直接转换
        3. 云湖特有内容类型添加yunhu_前缀
        """
        msg_data = event_data.get("message", {})
        sender = event_data.get("sender", {})
        chat_info = event_data.get("chat", {})
        content_type = msg_data.get("contentType", "text")
        
        # 构建标准消息段
        message_segments = []
        alt_message = []
        
        # 处理文本内容
        if content_type == "text":
            text = msg_data.get("content", {}).get("text", "")
            if text:
                message_segments.append({"type": "text", "data": {"text": text}})
                alt_message.append(text)
        
        # 处理媒体内容 (标准类型)
        elif content_type == "image":
            media_data = self._build_media_data(msg_data.get("content", {}), "image")
            message_segments.append({"type": "image", "data": media_data})
            alt_message.append(f"[图片:{media_data.get('file_name', '')}]")
        
        elif content_type == "video":
            media_data = self._build_media_data(msg_data.get("content", {}), "video")
            message_segments.append({"type": "video", "data": media_data})
            alt_message.append(f"[视频:{media_data.get('file_name', '')}]")
        
        elif content_type == "file":
            media_data = self._build_media_data(msg_data.get("content", {}), "file")
            message_segments.append({"type": "file", "data": media_data})
            alt_message.append(f"[文件:{media_data.get('file_name', '')}]")
        
        # 处理云湖特有内容类型
        elif content_type == "form":
            form_data = self._build_form_data(msg_data.get("content", {}), msg_data)
            message_segments.append({"type": "yunhu_form", "data": form_data})
            alt_message.append(f"[表单:{form_data.get('name', '')}]")
        
        # 处理按钮 (云湖扩展)
        buttons = msg_data.get("content", {}).get("buttons")
        if buttons:
            message_segments.append({
                "type": "yunhu_button",
                "data": {"buttons": buttons}
            })
            alt_message.append("[按钮]")
        
        # 设置聊天类型 (OneBot12标准)
        chat_type = chat_info.get("chatType", "")
        base_event["detail_type"] = "private" if chat_type == "bot" else "group"

        # 构建最终消息事件
        base_event.update({
            "type": "message",
            "message_id": msg_data.get("msgId", ""),
            "message": message_segments,
            "alt_message": "".join(alt_message),
            "user_id": sender.get("senderId", "")
        })

        # 设置群聊ID或机器人ID
        if base_event["detail_type"] == "group":
            base_event["group_id"] = chat_info.get("chatId", "")
        else:
            base_event["self"]["user_id"] = chat_info.get("chatId", "")
        
        # 处理指令消息 (云湖扩展)
        if "receive.instruction" in event_type:
            if "receive.instruction" in event_type:
                command_data = self._build_command_data(
                    content=msg_data.get("content", {}),
                    message_event=msg_data,
                    content_type=content_type
                )
            base_event["yunhu_command"] = command_data
        
        return base_event
    def _handle_friend_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理机器人订阅关系变更事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "friend_increase" if event_type == "bot.followed" else "friend_decrease",
            "user_id": event_data.get("userId", ""),
            "self": {
                "platform": "yunhu",
                "user_id": event_data.get("chatId", "")
            }
        })
        return base_event
    def _handle_group_member_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理群成员变更事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "group_member_increase" if event_type == "group.join" else "group_member_decrease",
            "sub_type": "invite" if event_type == "group.join" else "leave",
            "group_id": event_data.get("chatId", ""),
            "user_id": event_data.get("userId", ""),
            "operator_id": "",
            "self": {
                "platform": "yunhu",
                "user_id": ""
            }
        })
        return base_event

    def _handle_button_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理按钮点击事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "yunhu_button_click",
            "user_id": event_data.get("userId", ""),
            "message_id": event_data.get("msgId", ""),
            "yunhu_button": {
                "id": event_data.get("buttonId", ""),
                "value": event_data.get("value", "")
            },
            "self": {
                "platform": "yunhu",
                "user_id": ""
            }
        })
        return base_event

    def _handle_menu_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理快捷菜单事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "yunhu_shortcut_menu",
            "user_id": event_data.get("senderId", ""),
            "group_id": event_data.get("chatId", "") if event_data.get("chatType") == "group" else "",
            "yunhu_menu": {
                "id": event_data.get("menuId", ""),
                "type": event_data.get("menuType", 1),
                "action": event_data.get("menuAction", 1)
            },
            "self": {
                "platform": "yunhu",
                "user_id": ""
            }
        })
        return base_event

    def _handle_setting_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理机器人设置事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "yunhu_bot_setting",
            "group_id": event_data.get("groupId", ""),
            "yunhu_setting": event_data.get("settingJson", {}),
            "self": {
                "platform": "yunhu",
                "user_id": event_data.get("chatId", "")
            }
        })
        return base_event
    def _build_media_data(self, content: Dict, media_type: str) -> Dict:
        """构建标准媒体数据 (OneBot12兼容)"""
        media_map = {
            "image": ("imageUrl", "imageName", "imageWidth", "imageHeight"),
            "video": ("videoUrl", "videoName", "videoWidth", "videoHeight", "videoDuration"),
            "file": ("fileUrl", "fileName", "fileSize")
        }
        
        url_key, name_key, *extra_keys = media_map[media_type]
        media_data = {
            "file_id": content.get(url_key, ""),
            "url": content.get(url_key, ""),
            "file_name": content.get(name_key, "")
        }
        
        # 添加类型特定字段
        if media_type == "image":
            media_data.update({
                "width": content.get(extra_keys[0], 0),
                "height": content.get(extra_keys[1], 0)
            })
        elif media_type == "video":
            media_data.update({
                "width": content.get(extra_keys[0], 0),
                "height": content.get(extra_keys[1], 0),
                "duration": content.get(extra_keys[2], 0)
            })
        elif media_type == "file":
            media_data["size"] = content.get(extra_keys[0], 0)
            
        return media_data
    def _build_form_data(self, content: Dict, message_event: Dict) -> Dict:
        """
        构建表单消息数据
        """
        form_json = content.get("formJson", {})
        form_data = []
        
        for field_id, field_data in form_json.items():
            field_type = field_data.get("type", "")
            field_value = ""
            
            if field_type == "input":
                field_value = field_data.get("value", "")
            elif field_type == "switch":
                field_value = str(field_data.get("value", False))
            elif field_type == "checkbox":
                selected = field_data.get("selectStatus", [])
                values = field_data.get("selectValues", [])
                field_value = ",".join([v for i, v in enumerate(values) if i < len(selected) and selected[i]])
            elif field_type == "textarea":
                field_value = field_data.get("value", "")
            elif field_type == "select":
                field_value = field_data.get("selectValue", "")
            elif field_type == "radio":
                field_value = field_data.get("selectValue", "")
            
            form_data.append({
                "id": field_id,
                "type": field_type,
                "label": field_data.get("label", ""),
                "value": field_value
            })
        
        return {
            "id": message_event.get("instructionId", ""),
            "name": message_event.get("instructionName", ""),
            "fields": form_data
        }

    def _build_command_data(self, content: Dict, message_event: Dict, content_type: str) -> Dict:
        """
        构建指令数据
        """
        command_data = {
            "name": message_event.get("commandName", ""),
            "id": str(message_event.get("commandId", 0)),
            "args": content.get("text", "").replace(f"/{message_event.get('commandName', '')}", "").strip()
        }
        
        if content_type == "form":
            command_data["form"] = content.get("formJson", {})
        
        return command_data
    