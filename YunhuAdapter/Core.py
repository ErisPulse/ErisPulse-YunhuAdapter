import asyncio
import io
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
import filetype
from ErisPulse import sdk
from ErisPulse.Core import ClientWebSocket, client, router
from ErisPulse.Core.Bases.errors import (
    ClientConnectionError,
    ClientError,
    ClientTimeoutError,
)
from ErisPulse.Core.Bases.websocket import WSMessage
from ErisPulse.runtime.config_schema import BotAccountConfig


def _mask_token(url: str) -> str:
    return re.sub(r"([?&]token=)[^&]*", r"\1***", url)


# 用于自动探测 bot_id 的空群聊：向该群发送消息会返回包含机器人ID的错误信息。
# 该群不包含任何机器人，因此请求始终被拒绝，不会产生实际副作用。
PROBE_GROUP_ID = "112869497"


@dataclass
class YunhuBotConfig(BotAccountConfig):
    """云湖机器人账户配置"""

    token: str = field(
        default="",
        metadata={
            "description": "机器人Token",
            "required": True,
            "secret": True,
            "webui": {"widget": "password", "group": "basic", "order": 2},
        },
    )
    mode: str = field(
        default="ws",
        metadata={
            "description": "接收模式",
            "webui": {
                "widget": "select",
                "group": "connection",
                "order": 3,
                "options": [
                    {"label": "WebSocket", "value": "ws"},
                    {"label": "Webhook", "value": "webhook"},
                ],
            },
        },
    )
    webhook_path: str = field(
        default="/webhook",
        metadata={
            "description": "Webhook路径（仅webhook模式）",
            "webui": {"widget": "text", "group": "connection", "order": 4},
        },
    )


class YunhuAdapter(sdk.BaseAdapter):
    """
    云湖平台适配器实现

    {!--< tips >!--}
    1. 使用统一适配器服务器系统管理Webhook路由
    2. 提供完整的消息发送DSL接口
    3. 使用 AccountConfigClass 声明式管理多账户配置
    {!--< /tips >!--}
    """

    AccountConfigClass = YunhuBotConfig

    class Send(sdk.BaseAdapter.Send):
        """
        消息发送DSL实现

        {!--< tips >!--}
        1. 支持文本、富文本、文件等多种消息类型
        2. 支持批量发送和消息编辑
        3. 内置文件类型自动检测
        4. 支持链式修饰（At、Reply、Buttons）
        {!--< /tips >!--}
        """

        def __init__(self, adapter, target_type=None, target_id=None, account_id=None):
            super().__init__(adapter, target_type, target_id, account_id)
            self._buttons = None

        def Buttons(self, buttons: List):
            self._buttons = buttons
            return self

        def _reset_modifiers(self):
            self._buttons = None

        def _build_content_with_modifiers(
            self, text: str, content_type: str, buttons: List = None
        ) -> Dict:
            result = {"text": text}
            if self._at_user_ids:
                at_text = " ".join([f"@{uid}" for uid in self._at_user_ids])
                result["text"] = at_text + " " + result["text"]
            resolved_buttons = self._buttons if self._buttons is not None else buttons
            if resolved_buttons is not None:
                result["buttons"] = resolved_buttons
            return result

        def _get_parent_id(self, param_parent_id: str = "") -> str:
            return (
                self._reply_message_id
                if self._reply_message_id is not None
                else param_parent_id
            )

        def _get_buttons(self, param_buttons: List = None):
            return self._buttons if self._buttons is not None else param_buttons

        def Text(self, text: str):
            return self.Raw_ob12(
                [
                    {
                        "type": "text",
                        "data": {
                            "text": text,
                        },
                    }
                ]
            )

        def Html(self, html: str):
            return self.Raw_ob12(
                [
                    {
                        "type": "html",
                        "data": {
                            "html": html,
                        },
                    }
                ]
            )

        def Markdown(self, markdown: str):
            return self.Raw_ob12(
                [
                    {
                        "type": "markdown",
                        "data": {
                            "markdown": markdown,
                        },
                    }
                ]
            )

        def A2UI(self, text: str):
            return self.Raw_ob12(
                [
                    {
                        "type": "a2ui",
                        "data": {
                            "a2ui": text,
                        },
                    }
                ]
            )

        def Image(
            self,
            file,
            stream: bool = False,
            filename: str = None,
        ):
            return self.Raw_ob12(
                [
                    {
                        "type": "image",
                        "data": {
                            "file": file,
                            "stream": stream,
                            "filename": filename,
                        },
                    }
                ]
            )

        def Video(
            self,
            file,
            stream: bool = False,
            filename: str = None,
        ):
            return self.Raw_ob12(
                [
                    {
                        "type": "video",
                        "data": {
                            "file": file,
                            "stream": stream,
                            "filename": filename,
                        },
                    }
                ]
            )

        def File(
            self,
            file,
            stream: bool = False,
            filename: str = None,
        ):
            return self.Raw_ob12(
                [
                    {
                        "type": "file",
                        "data": {
                            "file": file,
                            "stream": stream,
                            "filename": filename,
                        },
                    }
                ]
            )

        def Batch(
            self,
            target_ids: List[str],
            message: Any,
            content_type: str = "text",
            **kwargs,
        ):
            if content_type in ["text", "html", "markdown"]:
                sdk.logger.debug(
                    "批量发送文本/富文本消息时, 更推荐的方法是使用"
                    " Send.To('user'/'group', user_ids: list/group_ids: list).Text/Html/Markdown(message, buttons = None, parent_id = None)"
                )

            if not isinstance(message, str):
                try:
                    message = str(message)
                except Exception:
                    raise ValueError("message 必须可转换为字符串")

            content = {"text": message} if isinstance(message, str) else {}
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/batch_send",
                    _account_id=self._account_id,
                    recvIds=target_ids,
                    recvType=self._target_type,
                    contentType=content_type,
                    content=content,
                    **kwargs,
                )
            )

        def Edit(
            self,
            msg_id: str,
            text: Any,
            content_type: str = "text",
            buttons: List = None,
        ):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    raise ValueError("text 必须可转换为字符串")

            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/edit",
                    _account_id=self._account_id,
                    msgId=msg_id,
                    recvId=self._target_id,
                    recvType=self._target_type,
                    contentType=content_type,
                    content={
                        "text": text,
                        "buttons": buttons if buttons is not None else [],
                    },
                )
            )

        def Recall(self, msg_id: str):
            if not self._target_id or not self._target_type:
                raise ValueError(
                    "Recall必须使用To(target_type, target_id)指定目标。例如: Send.To('group', '123').Recall('msg_id')"
                )

            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/recall",
                    _account_id=self._account_id,
                    msgId=msg_id,
                    chatId=self._target_id,
                    chatType=self._target_type,
                )
            )

        def Board(self, scope: str, content: str, **kwargs):
            endpoint = "/bot/board" if scope == "local" else "/bot/board-all"
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    _account_id=self._account_id,
                    chatId=self._target_id if scope == "local" else None,
                    chatType=self._target_type if scope == "local" else None,
                    contentType=kwargs.get("content_type", "text"),
                    content=content,
                    expireTime=kwargs.get("expire_time", 0),
                )
            )

        def DismissBoard(self, scope: str, **kwargs):
            endpoint = (
                "/bot/board-dismiss" if scope == "local" else "/bot/board-all-dismiss"
            )
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    _account_id=self._account_id,
                    chatId=self._target_id if scope == "local" else None,
                    chatType=self._target_type if scope == "local" else None,
                )
            )

        def Kick(self, user_id: str):
            if self._target_type != "group":
                raise ValueError("Kick必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/remove-member",
                    _account_id=self._account_id,
                    userId=user_id,
                    groupId=self._target_id,
                )
            )

        def Ban(self, user_id: str, duration: int = 600):
            if self._target_type != "group":
                raise ValueError("Ban必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/gag-member",
                    _account_id=self._account_id,
                    userId=user_id,
                    groupId=self._target_id,
                    gag=duration,
                )
            )

        def CreateTag(
            self,
            tag: str,
            color: str = None,
            desc: str = None,
            sort: int = None,
        ):
            if self._target_type != "group":
                raise ValueError("CreateTag必须使用To('group', group_id)指定群组")
            params = {"groupId": self._target_id, "tag": tag}
            if color is not None:
                params["color"] = color
            if desc is not None:
                params["desc"] = desc
            if sort is not None:
                params["sort"] = sort
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/tag/create",
                    _account_id=self._account_id,
                    **params,
                )
            )

        def EditTag(
            self,
            tag: str,
            new_tag: str = None,
            color: str = None,
            desc: str = None,
            sort: int = None,
        ):
            if self._target_type != "group":
                raise ValueError("EditTag必须使用To('group', group_id)指定群组")
            params = {"groupId": self._target_id, "tag": tag}
            if new_tag is not None:
                params["newTag"] = new_tag
            if color is not None:
                params["color"] = color
            if desc is not None:
                params["desc"] = desc
            if sort is not None:
                params["sort"] = sort
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/tag/edit",
                    _account_id=self._account_id,
                    **params,
                )
            )

        def DeleteTag(self, tag: str):
            if self._target_type != "group":
                raise ValueError("DeleteTag必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/tag/delete",
                    _account_id=self._account_id,
                    tag=tag,
                    groupId=self._target_id,
                )
            )

        def GetTagList(self):
            if self._target_type != "group":
                raise ValueError("GetTagList必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/tag/list",
                    _account_id=self._account_id,
                    groupId=self._target_id,
                )
            )

        def AddUserTag(self, user_id: str, tag: str):
            if self._target_type != "group":
                raise ValueError("AddUserTag必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/tag/user-relate",
                    _account_id=self._account_id,
                    userId=user_id,
                    tag=tag,
                    groupId=self._target_id,
                )
            )

        def RemoveUserTag(self, user_id: str, tag: str):
            if self._target_type != "group":
                raise ValueError("RemoveUserTag必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/tag/user-relate-cancel",
                    _account_id=self._account_id,
                    userId=user_id,
                    tag=tag,
                    groupId=self._target_id,
                )
            )

        def SetMsgTypeLimit(self, types: str):
            if self._target_type != "group":
                raise ValueError("SetMsgTypeLimit必须使用To('group', group_id)指定群组")
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/group/msg-type-limit",
                    _account_id=self._account_id,
                    groupId=self._target_id,
                    type=types,
                )
            )

        def GetMessages(self, message_id: str = None, before: int = 0, after: int = 0):
            if not self._target_id or not self._target_type:
                raise ValueError(
                    "GetMessages必须使用To(target_type, target_id)指定目标。"
                    "例如: Send.To('group', '123').GetMessages(before=10)"
                )
            if not before and not after:
                raise ValueError(
                    "GetMessages必须指定 before 或 after (>0)，"
                    "否则服务器不会返回任何消息。"
                    "例如: Send.To('group', '123').GetMessages(before=10)"
                )
            query = {
                "chat-id": self._target_id,
                "chat-type": self._target_type,
            }
            if message_id is not None:
                query["message-id"] = message_id
            if before:
                query["before"] = before
            if after:
                query["after"] = after
            return asyncio.create_task(
                self._adapter.get_messages(_account_id=self._account_id, **query)
            )

        def Stream(self, content_type: str, content_generator, **kwargs):
            return asyncio.create_task(
                self._adapter.send_stream(
                    conversation_type=self._target_type,
                    target_id=self._target_id,
                    content_type=content_type,
                    content_generator=content_generator,
                    **kwargs,
                )
            )

        def Raw_ob12(self, message, **kwargs):
            if isinstance(message, dict):
                message = [message]

            grouped_messages = self._group_ob12_messages(message)

            async def _send_grouped_messages():
                results = []
                for msg_group in grouped_messages:
                    result = await self._send_ob12_group(msg_group)
                    results.append(result)
                self._reset_modifiers()
                return results[-1] if results else None

            return asyncio.create_task(_send_grouped_messages())

        def _group_ob12_messages(self, message: List[Dict]) -> List[List[Dict]]:
            groups = []
            current_group = []
            text_mergeable_types = ["text", "mention"]

            for segment in message:
                seg_type = segment.get("type", "")

                if seg_type == "reply":
                    current_group.append(segment)
                    continue

                if seg_type in text_mergeable_types:
                    if not current_group or all(
                        s.get("type") in text_mergeable_types
                        or s.get("type") == "reply"
                        for s in current_group
                    ):
                        current_group.append(segment)
                    else:
                        if current_group:
                            groups.append(current_group)
                        current_group = [segment]
                else:
                    if current_group:
                        groups.append(current_group)
                    groups.append([segment])
                    current_group = []

            if current_group:
                groups.append(current_group)

            return groups

        async def _send_ob12_group(self, msg_group: List[Dict]) -> Dict:
            if not msg_group:
                return None

            first_segment = msg_group[0]
            seg_type = first_segment.get("type", "")

            parent_id = self._reply_message_id
            buttons = self._buttons
            at_user_ids = self._at_user_ids.copy() if self._at_user_ids else []

            if seg_type in ["text", "mention"]:
                text_parts = []
                for segment in msg_group:
                    s_type = segment.get("type", "")
                    s_data = segment.get("data", {})
                    if s_type == "text":
                        text_parts.append(s_data.get("text", ""))
                    elif s_type == "mention":
                        user_id = s_data.get("user_id", "")
                        text_parts.append(f"@{user_id}")
                    elif s_type == "reply":
                        parent_id = s_data.get("message_id", "")

                if at_user_ids:
                    at_text = " ".join([f"@{uid}" for uid in at_user_ids])
                    text_parts.insert(0, at_text)

                text = " ".join(text_parts) or " "
                seg_data = first_segment.get("data", {})
                param_buttons = (
                    buttons if buttons is not None else seg_data.get("buttons")
                )
                param_parent_id = (
                    parent_id
                    if parent_id is not None
                    else seg_data.get("parent_id", "")
                )

                return await self._do_send_text(
                    text, buttons=param_buttons, parent_id=param_parent_id
                )

            seg_data = first_segment.get("data", {})
            param_buttons = buttons if buttons is not None else seg_data.get("buttons")
            param_parent_id = (
                parent_id if parent_id is not None else seg_data.get("parent_id", "")
            )

            if seg_type == "image":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._do_send_media(
                    "/image/upload",
                    file_url,
                    "image",
                    buttons=param_buttons,
                    parent_id=param_parent_id,
                    stream=seg_data.get("stream", False),
                    filename=seg_data.get("filename"),
                )

            elif seg_type == "audio":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._do_send_media(
                    "/video/upload",
                    file_url,
                    "video",
                    buttons=param_buttons,
                    parent_id=param_parent_id,
                    stream=seg_data.get("stream", False),
                    filename=seg_data.get("filename"),
                )

            elif seg_type == "video":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._do_send_media(
                    "/video/upload",
                    file_url,
                    "video",
                    buttons=param_buttons,
                    parent_id=param_parent_id,
                    stream=seg_data.get("stream", False),
                    filename=seg_data.get("filename"),
                )

            elif seg_type == "file":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self._do_send_media(
                    "/file/upload",
                    file_url,
                    "file",
                    buttons=param_buttons,
                    parent_id=param_parent_id,
                    stream=seg_data.get("stream", False),
                    filename=seg_data.get("filename"),
                )

            elif seg_type == "markdown":
                markdown_text = seg_data.get("markdown", "")
                return await self._do_send_text_like(
                    markdown_text,
                    "markdown",
                    buttons=param_buttons,
                    parent_id=param_parent_id,
                )

            elif seg_type == "html":
                html_text = seg_data.get("html", "")
                return await self._do_send_text_like(
                    html_text, "html", buttons=param_buttons, parent_id=param_parent_id
                )

            elif seg_type == "a2ui":
                a2ui_text = seg_data.get("a2ui", "")
                return await self._do_send_text_like(
                    a2ui_text, "a2ui", parent_id=param_parent_id
                )

            elif seg_type == "reply":
                parent_id = seg_data.get("message_id", "")
                return await self._do_send_text(
                    "", buttons=buttons, parent_id=parent_id
                )

            elif seg_type.startswith("yunhu_"):
                return await self._do_send_text(
                    str(seg_data), buttons=buttons, parent_id=parent_id
                )

            else:
                return await self._do_send_text(
                    str(seg_data), buttons=buttons, parent_id=parent_id
                )

        def _do_send_text(self, text: str, buttons: List = None, parent_id: str = ""):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    raise ValueError("text 必须可转换为字符串")

            endpoint = (
                "/bot/batch_send" if isinstance(self._target_id, list) else "/bot/send"
            )
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    _account_id=self._account_id,
                    recvIds=self._target_id
                    if isinstance(self._target_id, list)
                    else None,
                    recvId=None
                    if isinstance(self._target_id, list)
                    else self._target_id,
                    recvType=self._target_type,
                    contentType="text",
                    content=self._build_content_with_modifiers(
                        text, "text", buttons=buttons
                    ),
                    parentId=self._get_parent_id(parent_id),
                )
            )

        def _do_send_text_like(
            self,
            text: str,
            content_type: str,
            buttons: List = None,
            parent_id: str = "",
        ):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    raise ValueError("text 必须可转换为字符串")

            endpoint = (
                "/bot/batch_send" if isinstance(self._target_id, list) else "/bot/send"
            )
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    _account_id=self._account_id,
                    recvIds=self._target_id
                    if isinstance(self._target_id, list)
                    else None,
                    recvId=None
                    if isinstance(self._target_id, list)
                    else self._target_id,
                    recvType=self._target_type,
                    contentType=content_type,
                    content=self._build_content_with_modifiers(
                        text, content_type, buttons=buttons
                    ),
                    parentId=self._get_parent_id(parent_id),
                )
            )

        def _do_send_media(
            self,
            upload_endpoint,
            file,
            content_type,
            buttons=None,
            parent_id="",
            stream=False,
            filename=None,
        ):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    upload_endpoint,
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type=content_type,
                    buttons=self._get_buttons(buttons),
                    parent_id=self._get_parent_id(parent_id),
                    stream=stream,
                )
            )

        def _detect_document(self, sample_bytes):
            office_signatures = {
                b"PK\x03\x04\x14\x00\x06\x00": "docx",
                b"PK\x03\x04\x14\x00\x00\x08": "xlsx",
                b"PK\x03\x04\x14\x00\x00\x06": "pptx",
            }

            for signature, extension in office_signatures.items():
                if sample_bytes.startswith(signature):
                    return extension
            return None

        async def _download_file_from_url(
            self, url: str, max_size: int = 100 * 1024 * 1024
        ) -> tuple[Optional[io.BytesIO], Optional[str]]:
            if not url:
                return None, None

            try:
                from urllib.parse import unquote, urlparse

                parsed_url = urlparse(url)
                filename = unquote(parsed_url.path.split("/")[-1]) or "downloaded_file"

                self._adapter.logger.debug(f"开始下载文件: {url}")

                headers = {}
                if "jwznb.com" in url:
                    headers["Referer"] = "http://myapp.jwznb.com"
                    headers["User-Agent"] = "ErisPulse-Worker"

                resp = await client.get(url, headers=headers, timeout=300)
                content_length = resp.headers.get("Content-Length")
                if content_length:
                    size = int(content_length)
                    if size > max_size:
                        self._adapter.logger.warning(
                            f"文件过大: {size / 1024 / 1024:.2f}MB (限制: {max_size / 1024 / 1024:.0f}MB)"
                        )
                        return None, None

                file_buffer = io.BytesIO()
                downloaded_size = 0

                async for chunk in resp.raw.content.iter_chunked(1048576):
                    downloaded_size += len(chunk)
                    if downloaded_size > max_size:
                        self._adapter.logger.warning(
                            f"下载文件过大: {downloaded_size / 1024 / 1024:.2f}MB (限制: {max_size / 1024 / 1024:.0f}MB)"
                        )
                        return None, None
                    file_buffer.write(chunk)

                file_buffer.seek(0)

                self._adapter.logger.debug(
                    f"文件下载完成: {downloaded_size} bytes, 文件名: {filename}"
                )
                return file_buffer, filename

            except Exception as e:
                self._adapter.logger.error(
                    f"下载文件失败: {_mask_token(url)}, 错误: {str(e)}"
                )
                return None, None

        def _read_local_file(
            self, file_path: str, max_size: int = 100 * 1024 * 1024
        ) -> tuple[Optional[bytes], Optional[str]]:
            import os

            try:
                if not os.path.exists(file_path):
                    self._adapter.logger.error(f"文件不存在: {file_path}")
                    return None, None

                if not os.path.isfile(file_path):
                    self._adapter.logger.error(f"路径不是文件: {file_path}")
                    return None, None

                filename = os.path.basename(file_path)

                file_size = os.path.getsize(file_path)
                if file_size > max_size:
                    self._adapter.logger.warning(
                        f"文件过大: {file_size / 1024 / 1024:.2f}MB (限制: {max_size / 1024 / 1024:.0f}MB)"
                    )
                    return None, None

                with open(file_path, "rb") as f:
                    file_data = f.read()

                self._adapter.logger.debug(
                    f"文件读取完成: {len(file_data)} bytes, 文件名: {filename}"
                )
                return file_data, filename

            except Exception as e:
                self._adapter.logger.error(f"读取文件失败: {file_path}, 错误: {str(e)}")
                return None, None

        async def _upload_file_and_call_api(
            self, upload_endpoint, file_name, file, endpoint, content_type, **kwargs
        ):
            bot_name, bot = self._adapter._resolve_account(self._account_id)

            if isinstance(file, str) and (
                file.startswith("http://") or file.startswith("https://")
            ):
                self._adapter.logger.info(f"检测到URL，开始下载: {file}")
                file_data, downloaded_filename = await self._download_file_from_url(
                    file
                )

                if file_data is None:
                    error_msg = f"[文件发送失败] 无法发送文件: {file}\n原因: 文件过大(超过100MB)或下载失败"
                    return await self._adapter.call_api(
                        endpoint="/bot/send",
                        _account_id=self._account_id,
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": error_msg},
                        parentId=kwargs.get("parent_id", ""),
                    )

                if file_name is None and downloaded_filename:
                    file_name = downloaded_filename

                file = file_data

            elif isinstance(file, str):
                import os

                if os.path.exists(file) and os.path.isfile(file):
                    self._adapter.logger.info(f"检测到本地文件路径，开始读取: {file}")
                    file_data, local_filename = self._read_local_file(file)

                    if file_data is None:
                        error_msg = f"[文件发送失败] 无法发送文件: {file}\n原因: 文件不存在、过大或读取失败"
                        return await self._adapter.call_api(
                            endpoint="/bot/send",
                            _account_id=self._account_id,
                            recvId=self._target_id,
                            recvType=self._target_type,
                            contentType="text",
                            content={"text": error_msg},
                            parentId=kwargs.get("parent_id", ""),
                        )

                    if file_name is None and local_filename:
                        file_name = local_filename

                    file = file_data

            url = f"{self._adapter.base_url}{upload_endpoint}?token={bot.token}"

            import aiohttp

            data = aiohttp.FormData(quote_fields=False)

            if kwargs.get("stream", False):
                if not hasattr(file, "__aiter__"):
                    raise ValueError("stream=True时，file参数必须是异步生成器")

                temp_file = io.BytesIO()
                async for chunk in file:
                    temp_file.write(chunk)
                temp_file.seek(0)
                file_data = temp_file
            else:
                if isinstance(file, bytes):
                    file_data = io.BytesIO(file)
                elif isinstance(file, io.BytesIO):
                    file_data = file
                else:
                    file_data = io.BytesIO(file)

            file_info = None
            file_extension = None

            try:
                if hasattr(file_data, "seek"):
                    file_data.seek(0)
                    sample = file_data.read(1024)
                    file_data.seek(0)

                    file_info = filetype.guess(sample)

                    if file_info and file_info.mime == "application/zip":
                        office_extension = self._detect_document(sample)
                        if office_extension:
                            file_extension = office_extension
                    elif file_info:
                        file_extension = file_info.extension
            except Exception as e:
                self._adapter.logger.warning(f"文件类型检测失败: {str(e)}")

            if file_name is None:
                if file_extension:
                    upload_filename = f"{content_type}.{file_extension}"
                else:
                    upload_filename = f"{content_type}.bin"
            else:
                if file_extension and "." not in file_name:
                    upload_filename = f"{file_name}.{file_extension}"
                else:
                    upload_filename = file_name

            self._adapter.logger.debug(
                f"Bot {bot_name} (bot_id: {self._adapter._bot_ids.get(bot_name, '')}) 上传文件: {upload_filename}"
            )
            data.add_field(
                name=content_type,
                value=file_data,
                filename=upload_filename,
            )

            try:
                resp = await client.post(url, data=data, timeout=300)

                if resp.status == 413:
                    error_msg = f"[文件发送失败] 文件过大: {upload_filename}\n原因: 超过云湖服务器限制"
                    return await self._adapter.call_api(
                        endpoint="/bot/send",
                        _account_id=self._account_id,
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": error_msg},
                        parentId=kwargs.get("parent_id", ""),
                    )

                try:
                    upload_res = await resp.json()
                except (json.JSONDecodeError, ValueError) as e:
                    error_text = (await resp.text())[:500]
                    self._adapter.logger.error(f"上传响应非JSON格式: {error_text}")
                    error_msg = f"[文件发送失败] 上传失败: {upload_filename}\n原因: 服务器返回错误 (状态码: {resp.status})"
                    return await self._adapter.call_api(
                        endpoint="/bot/send",
                        _account_id=self._account_id,
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": error_msg},
                        parentId=kwargs.get("parent_id", ""),
                    )

                self._adapter.logger.debug(f"上传响应: {upload_res}")

                if upload_res.get("code") != 1:
                    raise ValueError(f"文件上传失败: {upload_res}")

                key_map = {"image": "imageKey", "video": "videoKey", "file": "fileKey"}

                key_name = key_map.get(content_type, "fileKey")
                if "data" not in upload_res or key_name not in upload_res["data"]:
                    raise ValueError("上传API返回的数据格式不正确")

            except ClientTimeoutError:
                self._adapter.logger.error(f"文件上传超时: {_mask_token(url)}")
                error_msg = f"[文件发送失败] 上传超时: {upload_filename}"
                return await self._adapter.call_api(
                    endpoint="/bot/send",
                    _account_id=self._account_id,
                    recvId=self._target_id,
                    recvType=self._target_type,
                    contentType="text",
                    content={"text": error_msg},
                    parentId=kwargs.get("parent_id", ""),
                )
            except ClientError as e:
                self._adapter.logger.error(
                    f"文件上传失败: {_mask_token(url)}, 错误: {str(e)}"
                )
                error_msg = (
                    f"[文件发送失败] 上传失败: {upload_filename}\n原因: 网络错误"
                )
                return await self._adapter.call_api(
                    endpoint="/bot/send",
                    _account_id=self._account_id,
                    recvId=self._target_id,
                    recvType=self._target_type,
                    contentType="text",
                    content={"text": error_msg},
                    parentId=kwargs.get("parent_id", ""),
                )
            except Exception as e:
                if isinstance(e, (ValueError,)):
                    raise
                self._adapter.logger.error(
                    f"文件上传异常: {_mask_token(url)}, 错误: {str(e)}"
                )
                raise

            payload = {
                "recvId": self._target_id,
                "recvType": self._target_type,
                "contentType": content_type,
                "content": {key_name: upload_res["data"][key_name]},
                "parentId": kwargs.get("parent_id", ""),
            }

            if "buttons" in kwargs:
                payload["content"]["buttons"] = kwargs["buttons"]

            return await self._adapter.call_api(
                endpoint, _account_id=self._account_id, **payload
            )

    def _get_config_key(self) -> str:
        return "Yunhu_Adapter"

    def _load_accounts(self) -> dict:
        from ErisPulse.Core.config import config as config_mgr
        from ErisPulse.runtime.config_schema import dict_to_dataclass

        key = f"{self._get_config_key()}.accounts"
        data = config_mgr.getConfig(key)

        # 过滤掉无 token 的账户（可能是 _ensure_accounts_exist 自动生成的默认模板）
        if data:
            data = {
                name: cfg for name, cfg in data.items()
                if isinstance(cfg, dict) and cfg.get("token")
            }

        if not data:
            # 尝试从旧 .bots 配置迁移
            old_bots_key = f"{self._get_config_key()}.bots"
            old_bots_data = config_mgr.getConfig(old_bots_key)
            if old_bots_data:
                migrated = {
                    name: cfg for name, cfg in old_bots_data.items()
                    if isinstance(cfg, dict) and cfg.get("token")
                }
                if migrated:
                    config_mgr.setConfig(key, migrated, immediate=True)
                    self.logger.info(f"已将旧配置 {old_bots_key} 自动迁移到 {key}")
                    data = migrated

        if not data:
            # 尝试从旧顶层格式迁移（Yunhu_Adapter.token）
            old_config = config_mgr.getConfig(self._get_config_key())
            if old_config and "token" in old_config:
                self.logger.warning("检测到旧格式配置，建议迁移到新格式")
                self.logger.warning(
                    "迁移方法：将现有配置移动到 Yunhu_Adapter.accounts.default 下"
                )

                server_config = old_config.get("server", {})
                data = {
                    "default": {
                        "token": old_config.get("token", ""),
                        "mode": "ws",
                        "webhook_path": server_config.get("path", "/webhook"),
                        "enabled": True,
                    }
                }
                config_mgr.setConfig(key, data, immediate=True)
                self.logger.warning(
                    "已临时加载旧配置为默认账户，请尽快迁移到新格式"
                )

        if not data:
            self.logger.info("未找到配置文件，创建默认账户配置")
            data = {
                "default": {
                    "token": "",
                    "mode": "ws",
                    "webhook_path": "/webhook",
                    "enabled": True,
                }
            }
            try:
                config_mgr.setConfig(key, data)
            except Exception as e:
                self.logger.error(f"保存默认账户配置失败: {str(e)}")

        accounts = {}
        for name, account_data in data.items():
            if not isinstance(account_data, dict):
                continue
            if not account_data.get("token"):
                self.logger.error(f"账户 {name} 缺少token配置，已跳过")
                continue

            instance = dict_to_dataclass(YunhuBotConfig, account_data)
            instance.name = name
            accounts[name] = instance

        self.logger.info(f"云湖适配器初始化完成，共加载 {len(accounts)} 个机器人")
        return accounts

    def __init__(self, sdk_instance=None):
        super().__init__(sdk_instance)

        self.adapter = sdk.adapter
        self.base_url = "https://chat-go.jwzhd.com/open-apis/v1"
        self.ws_base_url = "wss://ws.jwzhd.com/subscribe"
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        self._ws_connections: Dict[str, ClientWebSocket] = {}
        self._bot_ids: Dict[str, str] = {}
        self._is_running = False

        self.convert = self._setup_converter()

    def _setup_converter(self):
        from .Converter import YunhuConverter

        convert = YunhuConverter()
        return convert.convert

    async def _net_request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        params: Dict = None,
        bot_token: str = None,
        max_retries: int = 2,
    ) -> Dict:
        token = bot_token if bot_token else ""
        url = f"{self.base_url}{endpoint}?token={token}"

        json_data = json.dumps(data) if data else None
        headers = {"Content-Type": "application/json; charset=utf-8"}

        self.logger.debug(
            f"[{endpoint}]|[{method}] 请求数据: {json_data} | 参数: {params}"
        )

        # 瞬态错误（连接被关闭/重置、超时）自动重试。
        # "Connection closed" 常见于连接池中的 keep-alive 连接已被服务端关闭，
        # 此时请求实际并未送达，重试是安全的。
        last_exc: Optional[BaseException] = None
        for attempt in range(max_retries + 1):
            try:
                resp = await client.request(
                    method, url, data=json_data, params=params, headers=headers
                )
                if "application/json" in (resp.content_type or ""):
                    result = await resp.json()
                    self.logger.debug(f"[{endpoint}]|[{method}] 响应数据: {result}")
                    return result
                else:
                    text = await resp.text()
                    self.logger.warning(
                        f"[{endpoint}] 非JSON响应，原始内容: {text[:500]}"
                    )
                    return {
                        "error": "Invalid content type",
                        "content_type": resp.content_type,
                        "status": resp.status,
                        "raw": text,
                    }
            except (
                ClientTimeoutError,
                ClientConnectionError,
                aiohttp.ClientError,
            ) as e:
                # 捕获 ErisPulse 包装的瞬态错误，以及未被转换而直接泄漏的底层
                # aiohttp 异常（某些版本下响应体读取阶段抛出的异常不会被转换）。
                last_exc = e
                if attempt < max_retries:
                    wait = min(2**attempt, 4)
                    self.logger.warning(
                        f"[{endpoint}] 请求失败（第 {attempt + 1}/{max_retries + 1} 次），"
                        f"{wait}s 后重试: {type(e).__name__}: {e}"
                    )
                    await asyncio.sleep(wait)
                    continue
                self.logger.error(
                    f"[{endpoint}] 重试 {max_retries} 次后仍失败 "
                    f"({type(e).__name__}): {_mask_token(url)}"
                )
                raise
            except ClientError as e:
                self.logger.error(f"网络请求失败: {_mask_token(url)}, 错误: {str(e)}")
                raise
            except Exception as e:
                # 非瞬态错误（如 JSON 解码失败），不重试
                self.logger.error(
                    f"请求异常: {_mask_token(url)}, 错误: {type(e).__name__}: {str(e)}"
                )
                raise

        # 理论上不可达：重试耗尽时循环内已 raise
        raise last_exc  # type: ignore[misc]

    async def send_stream(
        self,
        conversation_type: str,
        target_id: str,
        content_type: str,
        content_generator,
        **kwargs,
    ) -> Dict:
        bot_name, bot = self._resolve_account(kwargs.get("_account_id"))

        endpoint = "/bot/send-stream"
        params = {
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type,
        }
        if "parent_id" in kwargs:
            params["parentId"] = kwargs["parent_id"]
        url = f"{self.base_url}{endpoint}?token={bot.token}"
        query_params = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}&{query_params}"
        self.logger.debug(
            f"Bot {bot_name} (bot_id: {self._bot_ids.get(bot_name, '')}) 准备发送流式消息到 {target_id}，会话类型: {conversation_type}, 内容类型: {content_type}"
        )
        headers = {"Content-Type": "text/plain"}
        try:
            resp = await client.post(
                full_url, headers=headers, data=content_generator, timeout=300
            )
            raw_response = await resp.json()
        except ClientTimeoutError:
            self.logger.error(f"流式消息发送超时: {_mask_token(url)}")
            raise
        except ClientError as e:
            self.logger.error(f"流式消息发送失败: {_mask_token(url)}, 错误: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"流式消息发送异常: {_mask_token(url)}, 错误: {str(e)}")
            raise

        is_ok = raw_response.get("code") == 1
        message_id = ""
        if is_ok:
            data = raw_response.get("data", {})
            message_id = (
                data.get("messageInfo", {}).get("msgId", "")
                if "messageInfo" in data
                else data.get("msgId", "")
            )

        resp = self.make_response(
            status="ok" if is_ok else "failed",
            retcode=0 if is_ok else 34000 + (raw_response.get("code") or 0),
            data=raw_response.get("data") if is_ok else None,
            message_id=message_id,
            message=raw_response.get("msg", ""),
            raw=raw_response,
        )
        resp["self"] = {"user_id": self._bot_ids.get(bot_name, "")}

        if "echo" in kwargs:
            resp["echo"] = kwargs["echo"]

        return resp

    async def call_api(self, endpoint: str, _account_id: str = None, **params):
        bot_name, bot = self._resolve_account(_account_id)

        self.logger.debug(
            f"Bot {bot_name} (bot_id: {self._bot_ids.get(bot_name, '')}) 调用API:{endpoint} 参数:{params}"
        )

        raw_response = await self._net_request(
            "POST", endpoint, params, bot_token=bot.token
        )

        is_batch = "batch" in endpoint or isinstance(params.get("recvIds"), list)
        is_ok = raw_response.get("code") == 1

        if is_ok:
            if is_batch:
                message_ids = (
                    [
                        msg.get("msgId", "")
                        for msg in raw_response.get("data", {}).get("successList", [])
                        if isinstance(msg, dict) and msg.get("msgId")
                    ]
                    if "successList" in raw_response.get("data", {})
                    else []
                )
                resp = self.make_response(
                    data={"message_ids": message_ids},
                    message_id=message_ids,
                    raw=raw_response,
                )
            else:
                data = raw_response.get("data", {})
                message_id = (
                    data.get("messageInfo", {}).get("msgId", "")
                    if "messageInfo" in data
                    else data.get("msgId", "")
                )
                resp = self.make_response(
                    data={"message_id": message_id, "time": time.time()},
                    message_id=message_id,
                    raw=raw_response,
                )
        else:
            resp = self.make_error(
                retcode=34000 + (raw_response.get("code") or 0),
                message=raw_response.get("msg", ""),
                raw=raw_response,
            )
            if is_batch:
                resp["message_id"] = []

        resp["self"] = {"user_id": self._bot_ids.get(bot_name, "")}

        if "echo" in params:
            resp["echo"] = params["echo"]

        return resp

    async def get_messages(self, _account_id: str = None, **params):
        bot_name, bot = self._resolve_account(_account_id)

        self.logger.debug(
            f"Bot {bot_name} (bot_id: {self._bot_ids.get(bot_name, '')}) 获取消息列表 参数:{params}"
        )

        raw_response = await self._net_request(
            "GET", "/bot/messages", params=params, bot_token=bot.token
        )

        is_ok = raw_response.get("code") == 1
        if is_ok:
            resp = self.make_response(data=raw_response.get("data"), raw=raw_response)
        else:
            resp = self.make_error(
                retcode=34000 + (raw_response.get("code") or 0),
                message=raw_response.get("msg", ""),
                raw=raw_response,
            )
        resp["self"] = {"user_id": self._bot_ids.get(bot_name, "")}

        return resp

    async def _process_webhook_event(self, data: Dict, bot_name: str = None):
        try:
            if not isinstance(data, dict):
                raise ValueError("事件数据必须是字典类型")

            if "header" not in data or "eventType" not in data["header"]:
                raise ValueError("无效的事件数据结构")

            if hasattr(self.adapter, "emit"):
                bot = None
                if bot_name:
                    bot = self.accounts.get(bot_name)

                onebot_event = self.convert(data, self._bot_ids.get(bot_name) if bot_name else None)
                self.logger.debug(
                    f"Bot {bot_name} OneBot12事件数据: {json.dumps(onebot_event, ensure_ascii=False)}"
                )
                if onebot_event:
                    await self.adapter.emit(onebot_event)

        except Exception as e:
            self.logger.error(f"Bot {bot_name} 处理事件错误: {str(e)}")
            self.logger.debug(f"原始事件数据: {json.dumps(data, ensure_ascii=False)}")

    async def _ws_connect(self, bot_name: str):
        bot = self.accounts.get(bot_name)
        if not bot:
            return

        ws_url = f"{self.ws_base_url}?token={bot.token}"

        retry_interval = 5

        while self._is_running:
            try:
                self.logger.info(
                    f"Bot {bot_name} (ID: {self._bot_ids.get(bot_name, '')}) 正在连接WebSocket: {_mask_token(ws_url)}"
                )
                ws = await client.ws_connect(ws_url, heartbeat=30)
                self._ws_connections[bot_name] = ws
                self.logger.info(
                    f"Bot {bot_name} (ID: {self._bot_ids.get(bot_name, '')}) WebSocket连接已建立"
                )
                await self.emit_meta("connect", self._bot_ids.get(bot_name, ""))
                self._ws_tasks[bot_name] = asyncio.create_task(
                    self._ws_listen(bot_name)
                )
                return
            except Exception as e:
                self.logger.error(f"Bot {bot_name} WebSocket连接失败: {str(e)}")
                await asyncio.sleep(retry_interval)

    async def _ws_listen(self, bot_name: str):
        ws = self._ws_connections.get(bot_name)
        bot = self.accounts.get(bot_name)
        if not ws or not bot:
            return

        try:
            while True:
                msg = await ws.receive()
                if msg.type == WSMessage.TEXT:
                    asyncio.create_task(self._ws_handle_message(msg.data, bot_name))
                elif msg.type == WSMessage.CLOSE:
                    self.logger.info(f"Bot {bot_name} WebSocket连接已关闭")
                    break
                elif msg.type == WSMessage.ERROR:
                    self.logger.error(f"Bot {bot_name} WebSocket错误")
                    break
        except Exception as e:
            self.logger.error(f"Bot {bot_name} WebSocket监听异常: {str(e)}")
        finally:
            try:
                await self.emit_meta("disconnect", self._bot_ids.get(bot_name, ""))
            except Exception:
                pass
            if bot_name in self._ws_connections:
                ws = self._ws_connections[bot_name]
                try:
                    if not ws.closed:
                        await ws.close()
                except Exception:
                    pass
                del self._ws_connections[bot_name]

            if self._is_running and bot.enabled and bot.mode == "ws":
                self.logger.info(f"Bot {bot_name} 开始重连WebSocket...")
                self._ws_tasks[bot_name] = asyncio.create_task(
                    self._ws_connect(bot_name)
                )

    async def _ws_handle_message(self, raw_msg: str, bot_name: str):
        try:
            data = json.loads(raw_msg)
            await self._process_webhook_event(data, bot_name)
        except json.JSONDecodeError:
            self.logger.warning(f"Bot {bot_name} 收到非JSON的WS消息: {raw_msg[:200]}")
        except Exception as e:
            self.logger.error(f"Bot {bot_name} 处理WS消息错误: {str(e)}")

    async def register_webhook(self):
        enabled_bots = self.enabled_accounts

        if not enabled_bots:
            self.logger.warning("没有配置任何启用的机器人，将不会注册webhook")
            return

        for bot_name, bot in enabled_bots.items():
            path = bot.webhook_path

            def make_webhook_handler(bot_name):
                async def webhook_handler(data: Dict):
                    return await self._process_webhook_event(data, bot_name)

                return webhook_handler

            router.register_http_route(
                f"yunhu_{bot_name}",
                path,
                make_webhook_handler(bot_name),
                methods=["POST"],
            )

            self.logger.info(
                f"已注册Bot {bot_name} (ID: {self._bot_ids.get(bot_name, '')}) 的Webhook路由: {path}"
            )

    async def _detect_bot_id(self, token: str) -> Optional[str]:
        """向空群发送消息，从拒绝错误中解析出机器人ID。"""
        try:
            resp = await self._net_request(
                "POST", "/bot/send",
                {"recvId": PROBE_GROUP_ID, "recvType": "group",
                 "contentType": "text", "content": {"text": "."}},
                bot_token=token, max_retries=1,
            )
            msg = resp.get("msg", "") if isinstance(resp, dict) else ""
            match = re.search(r"机器人\(ID:\s*([^)\s]+)\)", msg)
            if match:
                self.logger.info(f"自动探测到机器人ID: {match.group(1)}")
                return match.group(1)
        except Exception as e:
            self.logger.error(f"自动探测bot_id失败: {e}")
        return None

    async def start(self):
        self._is_running = True
        enabled_bots = self.enabled_accounts

        if not enabled_bots:
            self.logger.warning("没有配置任何启用的机器人，适配器启动但无可用Bot")
            return

        # 统一探测所有机器人的bot_id（运行时数据）
        for bot_name, bot in enabled_bots.items():
            if not self._bot_ids.get(bot_name):
                self._bot_ids[bot_name] = await self._detect_bot_id(bot.token) or ""

        webhook_bots = {n: b for n, b in enabled_bots.items() if b.mode != "ws"}
        ws_bots = {n: b for n, b in enabled_bots.items() if b.mode == "ws"}

        if webhook_bots:
            for bot_name, bot in webhook_bots.items():
                path = bot.webhook_path

                def make_webhook_handler(bot_name):
                    async def webhook_handler(data: Dict):
                        return await self._process_webhook_event(data, bot_name)

                    return webhook_handler

                router.register_http_route(
                    f"yunhu_{bot_name}",
                    path,
                    make_webhook_handler(bot_name),
                    methods=["POST"],
                )
                self.logger.info(
                    f"已注册Bot {bot_name} (ID: {self._bot_ids.get(bot_name, '')}) 的Webhook路由: {path}"
                )
                await self.emit_meta("connect", self._bot_ids.get(bot_name, ""))

        for bot_name in ws_bots:
            self._ws_tasks[bot_name] = asyncio.create_task(self._ws_connect(bot_name))

        mode_summary = []
        if webhook_bots:
            mode_summary.append(f"Webhook: {', '.join(webhook_bots.keys())}")
        if ws_bots:
            mode_summary.append(f"WebSocket: {', '.join(ws_bots.keys())}")
        self.logger.info(f"云湖适配器已启动 [{'; '.join(mode_summary)}]")

    async def shutdown(self):
        self._is_running = False

        tasks_to_cancel = list(self._ws_tasks.values())
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        self._ws_tasks.clear()

        connections_to_close = list(self._ws_connections.items())
        for bot_name, ws in connections_to_close:
            try:
                if not ws.closed:
                    await ws.close()
            except Exception:
                pass
        self._ws_connections.clear()

        try:
            await client.close()
        except Exception:
            pass

        for bot_name, bot in self.enabled_accounts.items():
            try:
                await self.emit_meta("disconnect", self._bot_ids.get(bot_name, ""))
            except Exception:
                pass
        self.logger.info("云湖适配器已关闭")
