"""
云湖平台事件转换模块
将云湖平台事件转换为OneBot12标准格式

{!--< tips >!--}
注意：部分字段为云湖平台特有，非OneBot12标准字段，已添加yunhu_前缀
{!--< /tips >!--}
"""

import time
import uuid
from typing import Dict, Optional, Tuple

class Converter:
    def __init__(self):
        print("Converter init")
    
    def convert(self, data: Dict) -> Optional[Dict]:
        """
        主转换方法，根据事件类型分发到具体处理器
        
        :param event_type: [str] 云湖平台事件类型
        :param data: [Dict] 原始事件数据
        
        :return: 
            Optional[Dict]: 转换后的OneBot12格式事件，None表示不支持的事件类型
        
        :raises ValueError: 当事件数据格式错误时抛出
        """
        header = data.get("header", {})
        event_data = data.get("event", {})
        event_type = header.get("eventType", "")

        # 基础事件结构
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
            }
        }
        
        # 根据事件类型分发处理
        if event_type.startswith("message.receive"):
            return self._handle_message_event(event_type, event_data, onebot_event)
        elif event_type in ["bot.followed", "bot.unfollowed"]:
            return self._handle_friend_event(event_type, event_data, onebot_event)
        elif event_type in ["group.join", "group.leave"]:
            return self._handle_group_member_event(event_type, event_data, onebot_event)
        elif event_type == "button.report.inline":
            return self._handle_button_event(event_data, onebot_event)
        elif event_type == "bot.shortcut.menu":
            return self._handle_menu_event(event_data, onebot_event)
        
        return None

    def _handle_message_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理消息类型事件
        
        {!--< tips >!--}
        包含云湖特有字段：
        - yunhu_command_form: 表单类型指令数据
        - yunhu_message_form: 表单消息类型
        {!--< /tips >!--}
        
        :param event_type: [str] 消息事件类型
        :param event_data: [Dict] 事件数据
        :param base_event: [Dict] 基础事件结构
        
        :return: [Dict] 转换后的消息事件
        """
        message_event = event_data.get("message", {})
        sender = event_data.get("sender", {})
        chat_info = event_data.get("chat", {})
        content_type = message_event.get("contentType", "text")
        content = message_event.get("content", {})
        
        message_segments = []
        
        # 处理不同内容类型的消息
        if content_type == "text":
            message_segments.append({
                "type": "text",
                "data": {"text": content.get("text", "")}
            })
        elif content_type == "image":
            message_segments.append({
                "type": "image",
                "data": self._build_image_data(content)
            })
        elif content_type == "video":
            message_segments.append({
                "type": "video",
                "data": self._build_video_data(content)
            })
        elif content_type == "file":
            message_segments.append({
                "type": "file",
                "data": self._build_file_data(content)
            })
        elif content_type == "form":
            message_segments.append({
                "type": "yunhu_form",
                "data": self._build_form_data(content, message_event)
            })
        
        # 处理按钮
        if content.get("buttons"):
            message_segments.append({
                "type": "yunhu_button",
                "data": {"buttons": content["buttons"]}
            })
        
        # 构建最终事件
        base_event.update({
            "type": "message",
            "detail_type": "private" if chat_info.get("chatType") == "bot" else "group",
            "sub_type": "command" if event_type == "message.receive.instruction" else "",
            "message_id": message_event.get("msgId", ""),
            "message": message_segments,
            "alt_message": content.get("text", ""),
            "user_id": sender.get("senderId", ""),
            "group_id": chat_info.get("chatId", "") if chat_info.get("chatType") == "group" else "",
            "self": {
                "platform": "yunhu",
                "user_id": chat_info.get("chatId", "") if chat_info.get("chatType") == "bot" else ""
            }
        })
        
        # 处理指令消息
        if event_type == "message.receive.instruction":
            command_data = self._build_command_data(content, message_event, content_type)
            if content_type == "form":
                base_event["yunhu_command_form"] = command_data.pop("form")
            base_event["command"] = command_data
        
        return base_event

    def _handle_friend_event(self, event_type: str, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理机器人订阅关系变更事件
        
        :param event_type: [str] 事件类型
        :param event_data: [Dict] 事件数据
        :param base_event: [Dict] 基础事件结构
        
        :return: [Dict] 转换后的机器人订阅事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "friend_" + ("increase" if event_type == "bot.followed" else "decrease"),
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
        
        {!--< tips >!--}
        注意：云湖平台的群成员变更事件与OneBot12标准略有不同
        {!--< /tips >!--}
        
        :param event_type: [str] 事件类型
        :param event_data: [Dict] 事件数据
        :param base_event: [Dict] 基础事件结构
        
        :return: [Dict] 转换后的群成员事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "group_member_" + ("increase" if event_type == "group.join" else "decrease"),
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

    def _handle_button_event(self, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理按钮点击事件
        
        {!--< tips >!--}
        注意：此事件类型为云湖平台特有，非OneBot12标准
        {!--< /tips >!--}
        
        :param event_data: [Dict] 事件数据
        :param base_event: [Dict] 基础事件结构
        
        :return: [Dict] 转换后的按钮事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "yunhu_button_click",
            "user_id": event_data.get("userId", ""),
            "message_id": event_data.get("msgId", ""),
            "yunhu_button": {
                "id": "",
                "value": event_data.get("value", "")
            }
        })
        return base_event

    def _handle_menu_event(self, event_data: Dict, base_event: Dict) -> Dict:
        """
        处理快捷菜单事件
        
        {!--< tips >!--}
        注意：此事件类型为云湖平台特有，非OneBot12标准
        {!--< /tips >!--}
        
        :param event_data: [Dict] 事件数据
        :param base_event: [Dict] 基础事件结构
        
        :return: [Dict] 转换后的菜单事件
        """
        base_event.update({
            "type": "notice",
            "detail_type": "yunhu_shortcut_menu",
            "user_id": event_data.get("senderId", ""),
            "yunhu_menu": {
                "id": event_data.get("menuId", ""),
                "type": event_data.get("menuType", 1),
                "action": event_data.get("menuAction", 1)
            }
        })
        return base_event

    def _build_image_data(self, content: Dict) -> Dict:
        """
        构建图片消息数据
        
        :param content: [Dict] 原始图片内容数据
        
        :return: [Dict] 标准化的图片数据
        """
        return {
            "file_id": content.get("imageUrl", ""),
            "url": content.get("imageUrl", ""),
            "file_name": content.get("imageName", ""),
            "size": None,
            "width": content.get("imageWidth", 0),
            "height": content.get("imageHeight", 0)
        }

    def _build_video_data(self, content: Dict) -> Dict:
        """
        构建视频消息数据
        
        :param content: [Dict] 原始视频内容数据
        
        :return: [Dict] 标准化的视频数据
        """
        return {
            "file_id": content.get("videoUrl", ""),
            "url": content.get("videoUrl", ""),
            "file_name": content.get("videoUrl", "").split("/")[-1],
            "size": None,
            "duration": content.get("videoDuration", 0)
        }

    def _build_file_data(self, content: Dict) -> Dict:
        """
        构建文件消息数据
        
        :param content: [Dict] 原始文件内容数据
        
        :return: [Dict] 标准化的文件数据
        """
        return {
            "file_id": content.get("fileUrl", ""),
            "url": content.get("fileUrl", ""),
            "file_name": content.get("fileName", ""),
            "size": content.get("fileSize", 0)
        }

    def _build_form_data(self, content: Dict, message_event: Dict) -> Dict:
        """
        构建表单消息数据
        
        {!--< tips >!--}
        注意：表单消息类型为云湖平台特有，非OneBot12标准
        {!--< /tips >!--}
        
        :param content: [Dict] 原始表单内容数据
        :param message_event: [Dict] 消息事件数据
        
        :return: [Dict] 标准化的表单数据
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
        
        {!--< tips >!--}
        注意：表单类型指令为云湖平台特有，非OneBot12标准
        {!--< /tips >!--}
        
        :param content: [Dict] 消息内容数据
        :param message_event: [Dict] 消息事件数据
        :param content_type: [str] 内容类型
        
        :return: [Dict] 标准化的指令数据
        """
        command_data = {
            "name": message_event.get("commandName", ""),
            "id": str(message_event.get("commandId", 0)),
            "args": content.get("text", "").replace(f"/{message_event.get('commandName', '')}", "").strip()
        }
        
        if content_type == "form":
            command_data["yunhu_form"] = content.get("formJson", {})
        
        return command_data