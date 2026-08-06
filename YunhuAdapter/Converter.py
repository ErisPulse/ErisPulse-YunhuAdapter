"""
云湖平台事件转换模块
严格遵循 OneBot 12 标准格式进行事件转换

{!--< tips >!--}
1. 继承 BaseConverter 基类，复用公共字段构建与消息段辅助方法
2. 云湖平台特有字段均添加 yunhu_ 前缀作为扩展字段
3. 原始数据完整保留在 yunhu_raw 字段（无损转换）
{!--< /tips >!--}
"""

import re
import time
import uuid
from typing import Dict, List, Optional

from ErisPulse.Core import logger
from ErisPulse.Core.Bases import BaseConverter


class YunhuConverter(BaseConverter):
    """
    云湖平台事件转换器

    将云湖原生事件（header/event 嵌套结构）转换为 OneBot12 标准格式。
    机器人 ID (bot_id) 不包含在云湖事件中，由适配器运行时探测后注入。
    """

    def __init__(self):
        super().__init__(platform="yunhu")
        self._setup_event_mapping()

    def _setup_event_mapping(self):
        """初始化事件类型映射 (符合 OneBot12 标准)"""
        self.event_map = {
            # 标准消息事件
            "message.receive.normal": "message",
            "message.receive.instruction": "message",
            # 标准通知事件
            "bot.followed": "notice.friend_increase",
            "bot.unfollowed": "notice.friend_decrease",
            "group.join": "notice.group_member_increase",
            "group.leave": "notice.group_member_decrease",
            # 云湖特有事件（添加 yunhu_ 前缀）
            "button.report.inline": "notice.yunhu_button_click",
            "a2ui.button.report": "notice.yunhu_a2ui_button",
            "bot.shortcut.menu": "notice.yunhu_shortcut_menu",
            "bot.setting": "notice.yunhu_bot_setting",
        }

    def _build_base(
        self, data: Dict, event_type: str, bot_id: Optional[str] = None
    ) -> Dict:
        """
        构建 OneBot12 公共字段

        云湖事件结构为 {version, header:{eventId,eventTime,eventType}, event:{...}}，
        与 BaseConverter.build_base_event 期望的扁平结构不同，故在此单独构建。

        :param data: 云湖原始事件
        :param event_type: 原始事件类型 (header.eventType)
        :param bot_id: 运行时探测的机器人 ID
        """
        header = data.get("header", {})
        event_time = header.get("eventTime", int(time.time() * 1000))
        # 云湖使用毫秒级时间戳，OneBot12 标准要求秒级
        if event_time and event_time > 10**12:
            event_time = int(event_time / 1000)

        return {
            "id": str(header.get("eventId", "") or uuid.uuid4()),
            "time": int(event_time or time.time()),
            "type": "",
            "detail_type": "",
            "sub_type": "",
            "platform": self.platform,
            "self": {
                "platform": self.platform,
                "user_id": bot_id if bot_id else "",
            },
            "user_nickname": "",
            "yunhu_raw": data,
            "yunhu_raw_type": event_type,
        }

    def convert(self, data: Dict, bot_id: str = None) -> Optional[Dict]:
        """
        主转换方法

        :param data: 原始事件数据
        :param bot_id: 机器人ID（运行时探测注入，用于设置 self.user_id）
        :return: 符合 OneBot12 标准的事件字典；无法识别时返回 None
        """
        if not isinstance(data, dict):
            raise ValueError("事件数据必须是字典类型")

        header = data.get("header", {})
        event_type = header.get("eventType", "")

        if not event_type:
            raise ValueError("事件数据缺少 eventType 字段")

        onebot_event = self._build_base(data, event_type, bot_id)

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
            "notice.yunhu_a2ui_button": self._handle_a2ui_button_event,
            "notice.yunhu_shortcut_menu": self._handle_menu_event,
            "notice.yunhu_bot_setting": self._handle_setting_event,
        }

        handler = handler_map.get(mapped_type)
        return (
            handler(event_type, data.get("event", {}), onebot_event)
            if handler
            else None
        )

    def _handle_message_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        msg_data = event_data.get("message", {})
        sender = event_data.get("sender", {})
        chat_info = event_data.get("chat", {})
        content_type = msg_data.get("contentType", "text")
        content = msg_data.get("content", {})

        at_user_ids: List[str] = content.get("at", [])
        raw_text = content.get("text", "") if content_type == "text" else ""
        at_names = re.findall(r"@([\S]+)", raw_text)
        mention_segments = []
        for i, uid in enumerate(at_user_ids):
            mention_segments.append(
                {
                    "type": "mention",
                    "data": {
                        "user_id": str(uid),
                        "user_name": at_names[i] if i < len(at_names) else "",
                    },
                }
            )

        message_segments: list = []
        alt_message: list = []

        if content_type == "text":
            text = raw_text
            if at_user_ids:
                text = self._strip_at_text(text)
            if text:
                message_segments.append(self.text(text))
                alt_message.append(text)

        elif content_type in ("markdown", "html"):
            # 从 markdown/html 中提取纯文本，用于命令解析
            rich_text = content.get("text", "")
            if rich_text:
                # 移除 markdown/html 标记，提取纯文本
                text = self._strip_markdown_html(rich_text)
                if at_user_ids:
                    text = self._strip_at_text(text)
                if text:
                    message_segments.append(self.text(text))
                    alt_message.append(text)

                # 同时保留原始的 markdown/html 内容
                message_segments.append(
                    {"type": f"yunhu_{content_type}", "data": {"content": rich_text}}
                )

        elif content_type == "image":
            media_data = self._build_media_data(content, "image")
            message_segments.append({"type": "image", "data": media_data})
            alt_message.append(f"[图片:{media_data.get('file_name', '')}]")

        elif content_type == "video":
            media_data = self._build_media_data(content, "video")
            message_segments.append({"type": "video", "data": media_data})
            alt_message.append(f"[视频:{media_data.get('file_name', '')}]")

        elif content_type == "file":
            media_data = self._build_media_data(content, "file")
            message_segments.append({"type": "file", "data": media_data})
            alt_message.append(f"[文件:{media_data.get('file_name', '')}]")

        elif content_type == "audio":
            media_data = self._build_media_data(content, "audio")
            message_segments.append({"type": "audio", "data": media_data})
            alt_message.append(f"[语音:{media_data.get('file_name', '')}]")

        elif content_type == "expression":
            expression_data = {
                "sticker_id": str(content.get("stickerId", "")),
                "sticker_pack_id": str(content.get("stickerPackId", "")),
                "expression_id": str(content.get("expressionId", "")),
                "image_name": content.get("imageName", ""),
            }
            if content.get("imageWidth"):
                expression_data["width"] = content.get("imageWidth", 0)
            if content.get("imageHeight"):
                expression_data["height"] = content.get("imageHeight", 0)
            message_segments.append(
                {"type": "yunhu_expression", "data": expression_data}
            )
            alt_message.append(f"[表情:{content.get('stickerId', '')}]")

        elif content_type == "form":
            form_data = self._build_form_data(content, msg_data)
            message_segments.append({"type": "yunhu_form", "data": form_data})
            alt_message.append(f"[表单:{form_data.get('name', '')}]")

        buttons = content.get("buttons")
        if buttons:
            message_segments.append(
                {"type": "yunhu_button", "data": {"buttons": buttons}}
            )
            alt_message.append("[按钮]")

        parent_id = msg_data.get("parentId", "")
        if parent_id:
            reply_segments = [{"type": "reply", "data": {"message_id": parent_id}}]
            message_segments = reply_segments + mention_segments + message_segments
        else:
            message_segments = mention_segments + message_segments

        chat_type = chat_info.get("chatType", "")
        base_event["detail_type"] = "private" if chat_type == "bot" else "group"

        # 云湖 senderUserLevel → OneBot12 标准 role（owner/admin/member）
        sender_level = sender.get("senderUserLevel", "")
        base_event["yunhu_sender_level"] = sender_level

        base_event.update(
            {
                "type": "message",
                "message_id": msg_data.get("msgId", ""),
                "message": message_segments,
                "alt_message": "".join(alt_message),
                "user_id": sender.get("senderId", ""),
                "user_nickname": sender.get("senderNickname", ""),
                "user_avatar": sender.get("senderAvatarUrl", ""),
            }
        )

        if base_event["detail_type"] == "group":
            base_event["group_id"] = chat_info.get("chatId", "")
            # 群消息携带标准 role 字段（标签/头衔的语义映射见 EventMixin）
            base_event["role"] = self._map_role(sender_level)

        if "receive.instruction" in event_type:
            command_data = self._build_command_data(
                content=content,
                message_event=msg_data,
                content_type=content_type,
            )
            logger.debug(f"Received command: {command_data}")
            base_event["yunhu_command"] = command_data

            if command_data:
                command_name = command_data.get("name", "")
                args = command_data.get("args", "")
                if command_name:
                    base_event["alt_message"] = f"/{command_name} {args}".strip()

        return base_event

    @staticmethod
    def _map_role(sender_level: str) -> str:
        """云湖 senderUserLevel → OneBot12 标准 role"""
        return {
            "owner": "owner",
            "administrator": "admin",
            "member": "member",
        }.get(sender_level, "member")

    @staticmethod
    def _strip_at_text(text: str) -> str:
        """移除文本中的 @昵称 部分"""
        return re.sub(r"@[\S]+\s*", "", text).strip()

    @staticmethod
    def _strip_markdown_html(rich_text: str) -> str:
        """
        从 Markdown/Html 中提取纯文本
        用于命令解析和降级处理
        """
        if not rich_text:
            return ""

        # 移除 HTML 标记
        text = re.sub(r"<[^>]+>", "", rich_text)

        # 移除 Markdown 标记
        # 标题 (# ## ### 等)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # 粗体 (**text** 或 __text__)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        # 斜体 (*text* 或 _text_)
        text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)", r"\1", text)
        text = re.sub(r"(?<!_)_(?!_)([^_]+)(?<!_)_(?!_)", r"\1", text)
        # 删除线 (~~text~~)
        text = re.sub(r"~~([^~]+)~~", r"\1", text)
        # 行内代码 (`code`)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # 代码块 (```code```)
        text = re.sub(r"```[\s\S]*?```", "", text)
        # 链接 [text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # 图片 ![alt](url) -> [图片]
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
        # 引用 (> text)
        text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
        # 无序列表 (- text 或 * text 或 + text)
        text = re.sub(r"^[\-\*+]\s+", "", text, flags=re.MULTILINE)
        # 有序列表 (1. text)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)

        # 清理多余的空格和换行
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _handle_friend_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        """
        处理机器人订阅关系变更事件
        """
        base_event.update(
            {
                "type": "notice",
                "detail_type": "friend_increase"
                if event_type == "bot.followed"
                else "friend_decrease",
                "user_id": event_data.get("userId", ""),
                "user_nickname": event_data.get("nickname", ""),
            }
        )
        return base_event

    def _handle_group_member_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        """
        处理群成员变更事件
        """
        base_event.update(
            {
                "type": "notice",
                "detail_type": "group_member_increase"
                if event_type == "group.join"
                else "group_member_decrease",
                "sub_type": "invite" if event_type == "group.join" else "leave",
                "group_id": event_data.get("chatId", ""),
                "user_id": event_data.get("userId", ""),
                "user_nickname": event_data.get("nickname", ""),
                "operator_id": "",
            }
        )
        return base_event

    def _handle_button_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        """
        处理按钮点击事件
        """
        base_event.update(
            {
                "type": "notice",
                "detail_type": "yunhu_button_click",
                "user_id": event_data.get("userId", ""),
                "user_nickname": event_data.get("nickname", ""),
                "message_id": event_data.get("msgId", ""),
                "yunhu_button": {
                    "id": event_data.get("buttonId", ""),
                    "value": event_data.get("value", ""),
                },
            }
        )
        return base_event

    def _handle_a2ui_button_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        base_event.update(
            {
                "type": "notice",
                "detail_type": "yunhu_a2ui_button",
                "user_id": event_data.get("userId", ""),
                "user_nickname": event_data.get("nickname", ""),
                "message_id": event_data.get("msgId", ""),
                "yunhu_a2ui": {
                    "recv_id": event_data.get("recvId", ""),
                    "recv_type": event_data.get("recvType", ""),
                    "action_name": event_data.get("actionName", ""),
                    "source_component_id": event_data.get("sourceComponentId", ""),
                    "form_context": event_data.get("formContext", {}),
                    "interaction_json": event_data.get("interactionJson", ""),
                },
            }
        )
        return base_event

    def _handle_menu_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        """
        处理快捷菜单事件
        """
        base_event.update(
            {
                "type": "notice",
                "detail_type": "yunhu_shortcut_menu",
                "user_id": event_data.get("senderId", ""),
                "user_nickname": event_data.get("nickname", ""),
                "group_id": event_data.get("chatId", "")
                if event_data.get("chatType") == "group"
                else "",
                "yunhu_menu": {
                    "id": event_data.get("menuId", ""),
                    "type": event_data.get("menuType", 1),
                    "action": event_data.get("menuAction", 1),
                },
            }
        )
        return base_event

    def _handle_setting_event(
        self, event_type: str, event_data: Dict, base_event: Dict
    ) -> Dict:
        """
        处理机器人设置事件
        """
        base_event.update(
            {
                "type": "notice",
                "detail_type": "yunhu_bot_setting",
                "group_id": event_data.get("groupId", ""),
                "user_nickname": event_data.get("nickname", ""),
                "yunhu_setting": event_data.get("settingJson", {}),
            }
        )
        return base_event

    def _build_media_data(self, content: Dict, media_type: str) -> Dict:
        """构建标准媒体数据 (OneBot12 兼容)"""
        media_map = {
            "image": ("imageUrl", "imageName", "imageWidth", "imageHeight"),
            "video": (
                "videoUrl",
                "videoName",
                "videoWidth",
                "videoHeight",
                "videoDuration",
            ),
            "audio": ("audioUrl", "audioName", "audioDuration"),
            "file": ("fileUrl", "fileName", "fileSize"),
        }

        url_key, name_key, *extra_keys = media_map[media_type]
        raw_url = content.get(url_key, "")

        url_prefixes = {
            "image": "",
            "video": "https://chat-video1.jwznb.com/",
            "file": "https://chat-file.jwznb.com/",
            "audio": "",
        }
        prefix = url_prefixes.get(media_type, "")
        if raw_url and prefix and not raw_url.startswith("http"):
            raw_url = prefix + raw_url

        media_data = {
            "file_id": raw_url,
            "url": raw_url,
            "file_name": content.get(name_key, ""),
        }

        # 添加类型特定字段
        if media_type == "image":
            media_data.update(
                {
                    "width": content.get(extra_keys[0], 0),
                    "height": content.get(extra_keys[1], 0),
                }
            )
        elif media_type == "video":
            media_data.update(
                {
                    "width": content.get(extra_keys[0], 0),
                    "height": content.get(extra_keys[1], 0),
                    "duration": content.get(extra_keys[2], 0),
                }
            )
        elif media_type == "audio":
            media_data["duration"] = content.get(extra_keys[0], 0)
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
                field_value = ",".join(
                    [
                        v
                        for i, v in enumerate(values)
                        if i < len(selected) and selected[i]
                    ]
                )
            elif field_type == "textarea":
                field_value = field_data.get("value", "")
            elif field_type == "select":
                field_value = field_data.get("selectValue", "")
            elif field_type == "radio":
                field_value = field_data.get("selectValue", "")

            form_data.append(
                {
                    "id": field_id,
                    "type": field_type,
                    "label": field_data.get("label", ""),
                    "value": field_value,
                }
            )

        return {
            "id": message_event.get("instructionId", ""),
            "name": message_event.get("instructionName", ""),
            "fields": form_data,
        }

    def _build_command_data(
        self, content: Dict, message_event: Dict, content_type: str
    ) -> Dict:
        """
        构建指令数据
        """
        command_data = {
            "name": message_event.get("commandName", ""),
            "id": str(message_event.get("commandId", 0)),
            "args": content.get("text", "")
            .replace(f"/{message_event.get('commandName', '')}", "")
            .strip(),
        }

        if content_type == "form":
            command_data["form"] = content.get("formJson", {})

        return command_data
