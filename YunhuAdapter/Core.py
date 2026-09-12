import asyncio
import io
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import filetype
from ErisPulse import sdk
from ErisPulse.Core import BaseAdapter, ClientWebSocket, client, router
from ErisPulse.Core.Bases import BaseConfig, BaseI18n, BotAccountConfig, I18nKey
from ErisPulse.Core.Bases.errors import (
    ClientConnectionError,
    ClientError,
    ClientTimeoutError,
)
from ErisPulse.Core.Bases.websocket import WSMessage

try:
    from ErisPulse.runtime.tasks import spawn_background
except ImportError:  # pragma: no cover
    spawn_background = None

__version__ = "4.4.0"

# 软依赖的框架最低版本（运行时检测，仅提示不强制）
MIN_FRAMEWORK_VERSION = (2, 7, 1)


def _mask_token(url: str) -> str:
    return re.sub(r"([?&]token=)[^&]*", r"\1***", url)


# 用于自动探测 bot_id 的空群聊：向该群发送消息会返回包含机器人ID的错误信息。
# 该群不包含任何机器人，因此请求始终被拒绝，不会产生实际副作用。
PROBE_GROUP_ID = "112869497"

# OneBot12 标准动作名：Yunhu 不支持的（调用时返回 retcode=10002）
_UNSUPPORTED_STANDARD_ACTIONS = {
    "get_friend_list",
    "get_group_list",
    "get_group_member_info",
    "get_group_member_list",
    "set_group_name",
    "leave_group",
}


@dataclass
class YunhuGlobalConfig(BaseConfig):
    """云湖适配器全局配置（API 地址，一般无需修改）"""

    base_url: str = field(
        default="https://chat-go.jwzhd.com/open-apis/v1",
        metadata={
            "description": {"i18n": "yunhu.base_url", "default": "Bot 开放 API 地址"},
            "required": False,
            "ui": {"widget": "text", "group": "connection", "order": 1},
        },
    )
    web_api_base_url: str = field(
        default="https://chat-web-go.jwzhd.com",
        metadata={
            "description": {
                "i18n": "yunhu.web_api_base_url",
                "default": "公开 Web API 地址（非官方，用于信息查询）",
            },
            "required": False,
            "ui": {"widget": "text", "group": "connection", "order": 2},
        },
    )
    ws_base_url: str = field(
        default="wss://ws.jwzhd.com/subscribe",
        metadata={
            "description": {"i18n": "yunhu.ws_base_url", "default": "WebSocket 订阅地址"},
            "required": False,
            "ui": {"widget": "text", "group": "connection", "order": 3},
        },
    )


@dataclass
class YunhuBotConfig(BotAccountConfig):
    """云湖机器人账户配置"""

    token: str = field(
        default="",
        metadata={
            "description": {"i18n": "yunhu.token", "default": "机器人 Token"},
            "required": True,
            "secret": True,
            "ui": {"widget": "password", "group": "basic", "order": 2},
        },
    )
    mode: str = field(
        default="ws",
        metadata={
            "description": {"i18n": "yunhu.mode", "default": "事件接收模式"},
            "required": False,
            "ui": {
                "widget": "select",
                "group": "connection",
                "order": 3,
                "options": [
                    {"label": {"i18n": "yunhu.mode.ws", "default": "WebSocket"}, "value": "ws"},
                    {"label": {"i18n": "yunhu.mode.webhook", "default": "Webhook"}, "value": "webhook"},
                ],
            },
        },
    )
    webhook_path: str = field(
        default="/webhook",
        metadata={
            "description": {"i18n": "yunhu.webhook_path", "default": "Webhook 路径（仅 webhook 模式）"},
            "required": False,
            "ui": {"widget": "text", "group": "connection", "order": 4},
        },
    )


# 分组显示名（WebUI 用）
YunhuGlobalConfig._schema_meta = {
    "group_labels": {
        "connection": {"i18n": "yunhu.group.connection", "default": "连接设置"},
    }
}


class YunhuAdapter(BaseAdapter):
    """
    云湖平台适配器实现

    {!--< tips >!--}
    1. 使用统一适配器服务器系统管理 Webhook 路由
    2. 提供完整的消息发送 DSL 接口与标准 Api 动作
    3. 使用 AccountConfigClass 声明式管理多账户配置
    4. 标准 Api 动作（get_self_info/get_user_info/get_group_info 等）跨平台可用
    {!--< /tips >!--}
    """

    ConfigClass = YunhuGlobalConfig
    AccountConfigClass = YunhuBotConfig

    class I18nClass(BaseI18n):
        """云湖适配器翻译键声明"""

        base_url: I18nKey = I18nKey(
            default="Bot Open API URL",
            zh_CN="Bot 开放 API 地址",
            en="Bot Open API URL",
        )
        web_api_base_url: I18nKey = I18nKey(
            default="Public Web API URL (unofficial, for info queries)",
            zh_CN="公开 Web API 地址（非官方，用于信息查询）",
            en="Public Web API URL (unofficial, for info queries)",
        )
        ws_base_url: I18nKey = I18nKey(
            default="WebSocket subscribe URL",
            zh_CN="WebSocket 订阅地址",
            en="WebSocket subscribe URL",
        )
        token: I18nKey = I18nKey(
            default="Bot Token",
            zh_CN="机器人 Token",
            en="Bot Token",
        )
        mode: I18nKey = I18nKey(
            default="Event receive mode",
            zh_CN="事件接收模式",
            en="Event receive mode",
        )
        mode_ws: I18nKey = I18nKey(
            default="WebSocket",
            zh_CN="WebSocket",
            en="WebSocket",
        )
        mode_webhook: I18nKey = I18nKey(
            default="Webhook",
            zh_CN="Webhook",
            en="Webhook",
        )
        webhook_path: I18nKey = I18nKey(
            default="Webhook path (webhook mode only)",
            zh_CN="Webhook 路径（仅 webhook 模式）",
            en="Webhook path (webhook mode only)",
        )
        group_connection: I18nKey = I18nKey(
            default="Connection",
            zh_CN="连接设置",
            en="Connection",
        )

    class EventMixin:
        """
        云湖平台事件扩展方法

        注册到事件包装类后，可在事件处理器中直接调用：
        ``event.get_sender_role()`` / ``event.get_button_value()`` 等。
        所有方法均从 ``yunhu_raw`` / 标准字段安全读取，缺失时返回空值。
        """

        def get_raw_event(self) -> dict:
            """获取云湖原始事件数据（yunhu_raw）"""
            return self.get("yunhu_raw", {}) or {}

        def get_sender_level(self) -> str:
            """获取发送者在云湖的原生级别（owner/administrator/member/unknown）"""
            raw = self.get_raw_event()
            sender = raw.get("event", {}).get("sender", {}) if "event" in raw else {}
            return sender.get("senderUserLevel", "") or self.get("yunhu_sender_level", "")

        def get_sender_role(self) -> str:
            """获取发送者的 OneBot12 标准 role（owner/admin/member）"""
            return self.get("role", "") or "member"

        def get_sender_title(self) -> str:
            """
            获取发送者头衔（云湖标签的语义映射）

            云湖 bot 事件本身不携带成员标签；此方法预留为标准 title 字段访问器，
            未来若事件/查询返回头衔数据会填充到 ``title`` 字段。
            """
            return self.get("title", "")

        def get_sender_avatar(self) -> str:
            """获取发送者头像 URL"""
            if self.get("user_avatar"):
                return self.get("user_avatar", "")
            raw = self.get_raw_event()
            sender = raw.get("event", {}).get("sender", {}) if "event" in raw else {}
            return sender.get("senderAvatarUrl", "")

        def get_command(self) -> dict:
            """获取指令数据（仅指令消息事件，yunhu_command）"""
            return self.get("yunhu_command", {}) or {}

        def get_button_value(self) -> str:
            """获取按钮点击事件的 value（yunhu_button.value）"""
            return self.get("yunhu_button", {}).get("value", "")

        def get_a2ui_action(self) -> str:
            """获取 A2UI 按钮事件的 actionName（yunhu_a2ui.action_name）"""
            return self.get("yunhu_a2ui", {}).get("action_name", "")

        def get_a2ui_form_context(self) -> dict:
            """获取 A2UI 按钮事件的表单上下文（yunhu_a2ui.form_context）"""
            return self.get("yunhu_a2ui", {}).get("form_context", {}) or {}

        def get_menu_id(self) -> str:
            """获取快捷菜单事件 ID（yunhu_menu.id）"""
            return self.get("yunhu_menu", {}).get("id", "")

        def get_setting(self) -> dict:
            """获取机器人设置事件的设置数据（yunhu_setting）"""
            return self.get("yunhu_setting", {}) or {}

        def is_command_message(self) -> bool:
            """是否为指令消息"""
            return bool(self.get("yunhu_command"))

        def is_button_click(self) -> bool:
            """是否为按钮点击事件"""
            return self.get("detail_type") == "yunhu_button_click"

        def is_a2ui_button(self) -> bool:
            """是否为 A2UI 按钮事件"""
            return self.get("detail_type") == "yunhu_a2ui_button"

    class Api(BaseAdapter.Api):
        """
        云湖标准 API 动作实现（ApiDSL）

        {!--< tips >!--}
        1. get_self_info / get_user_info / get_group_info 通过非官方公开 Web API 实现（chat-web-go.jwzhd.com）
        2. upload_file 自动判定 image/video/file 类别上传到对应端点
        3. delete_message 需额外提供 chat_id + chat_type（云湖 /bot/recall 要求）
        4. 平台扩展动作通过 call("yunhu.xxx", ...) 调用
        5. 不支持的标准动作返回 retcode=10002
        {!--< /tips >!--}
        """

        async def _web_request(
            self, path: str, payload: Optional[dict] = None, method: str = "POST"
        ) -> dict:
            """
            调用非官方公开 Web API（chat-web-go.jwzhd.com）

            始终返回原始 {code, msg, data} 结构；异常时返回 {"code": -1, "msg": ...}，
            由调用方统一标准化。

            :param path: API 路径（如 "/v1/group/group-info"）
            :param payload: 请求体（GET 时作为 query）
            """
            base = self._adapter.cfg.web_api_base_url.rstrip("/")
            url = f"{base}{path}"
            try:
                if method.upper() == "GET":
                    resp = await client.get(url, params=payload or {})
                else:
                    resp = await client.post(url, json=payload or {})
                return await resp.json()
            except ClientTimeoutError:
                return {"code": -1, "msg": f"Web API 请求超时: {path}"}
            except ClientError as e:
                return {"code": -1, "msg": f"Web API 网络错误: {e}"}
            except Exception as e:
                return {"code": -1, "msg": f"Web API 请求异常: {e}"}

        async def get_self_info(self) -> dict:
            """获取机器人自身信息（通过公开 bot-info 接口）"""
            bot_name, _ = self._adapter._resolve_account(self._account_id)
            bot_id = self._adapter._bot_ids.get(bot_name, "")
            if not bot_id:
                return self._adapter.make_error(
                    retcode=35000, message="机器人 ID 尚未探测到"
                )
            raw = await self._web_request(
                "/v1/bot/bot-info", {"botId": str(bot_id)}
            )
            if raw.get("code") != 1:
                return self._adapter.make_error(
                    retcode=34001, message=raw.get("msg", "获取机器人信息失败"), raw=raw
                )
            bot = raw.get("data", {}).get("bot", {})
            user_id = str(bot.get("botId", bot_id))
            user_name = bot.get("nickname", "")
            data = {
                "user_id": user_id,
                "user_name": user_name,
                "user_displayname": user_name,
                "user_avatar": bot.get("avatarUrl", ""),
                "introduction": bot.get("introduction", ""),
                "headcount": bot.get("headcount", 0),
                "private": bot.get("private", 0),
            }
            self._adapter.logger.info(
                f"Api.get_self_info: bot_id={user_id}, nickname={user_name}, "
                f"headcount={data['headcount']}"
            )
            return self._adapter.make_response(data=data, raw=raw)

        async def get_user_info(self, user_id: str) -> dict:
            """获取用户信息（通过公开 user/homepage 接口，任意用户可查）"""
            raw = await self._web_request(
                "/v1/user/homepage", {"userId": str(user_id)}, method="GET"
            )
            if raw.get("code") != 1:
                return self._adapter.make_error(
                    retcode=34001, message=raw.get("msg", "获取用户信息失败"), raw=raw
                )
            u = raw.get("data", {}).get("user", {})
            data = {
                "user_id": str(u.get("userId", user_id)),
                "user_name": u.get("nickname", ""),
                "user_displayname": u.get("nickname", ""),
                "user_remark": "",
                "user_avatar": u.get("avatarUrl", ""),
                "register_time": u.get("registerTime", 0),
                "is_vip": u.get("isVip", 0),
            }
            self._adapter.logger.info(
                f"Api.get_user_info: user_id={data['user_id']}, "
                f"nickname={data['user_name']}"
            )
            return self._adapter.make_response(data=data, raw=raw)

        async def get_group_info(self, group_id: str) -> dict:
            """获取群信息（通过公开 group-info 接口）"""
            raw = await self._web_request(
                "/v1/group/group-info", {"groupId": str(group_id)}
            )
            if raw.get("code") != 1:
                return self._adapter.make_error(
                    retcode=34001, message=raw.get("msg", "获取群信息失败"), raw=raw
                )
            g = raw.get("data", {}).get("group", {})
            data = {
                "group_id": str(g.get("groupId", group_id)),
                "group_name": g.get("name", ""),
                "group_avatar": g.get("avatarUrl", ""),
                "group_introduction": g.get("introduction", ""),
                "group_member_count": g.get("headcount", 0),
                "group_create_by": g.get("createBy", ""),
            }
            self._adapter.logger.info(
                f"Api.get_group_info: group_id={data['group_id']}, "
                f"name={data['group_name']}, member_count={data['group_member_count']}"
            )
            return self._adapter.make_response(data=data, raw=raw)

        async def upload_file(
            self,
            *,
            type: str,
            name: str,
            url: str | None = None,
            path: str | None = None,
            data: bytes | None = None,
            headers: dict[str, str] | None = None,
            sha256: str | None = None,
        ) -> dict:
            """
            上传文件（自动判定 image/video/file 类别）

            :param type: 来源类型（url/path/data）
            :param name: 文件名（用于类别判定，如 "a.jpg"）
            """
            adapter = self._adapter
            try:
                file_bytes, _ = await adapter._read_upload_bytes(
                    type=type, url=url, path=path, data=data, headers=headers
                )
            except Exception as e:
                return adapter.make_error(retcode=10003, message=f"读取文件失败: {e}")

            category = adapter._detect_category(name, file_bytes)
            upload_endpoint_map = {
                "image": "/image/upload",
                "video": "/video/upload",
                "file": "/file/upload",
            }
            upload_endpoint = upload_endpoint_map[category]

            # 构建完整文件名（补全扩展名）
            ext = adapter._detect_extension(file_bytes, name)
            filename = adapter._build_upload_filename(name, category, ext)

            bot_name, bot = adapter._resolve_account(self._account_id)
            upload_url = f"{adapter.base_url}{upload_endpoint}?token={bot.token}"

            try:
                resp_json = await adapter._perform_upload(
                    upload_url, category, file_bytes, filename
                )
            except Exception as e:
                return adapter.make_error(retcode=34000, message=f"上传失败: {e}")

            try:
                file_id = adapter._extract_upload_key(resp_json, category)
            except ValueError as e:
                return adapter.make_error(retcode=34000, message=str(e), raw=resp_json)

            return adapter.make_response(
                data={"file_id": file_id, "name": name}, raw=resp_json
            )

        async def get_file(self, file_id: str, type: str = "url") -> dict:
            """获取文件（云湖 file_id 本身即下载 URL）"""
            return self._adapter.make_response(
                data={"name": "", "url": str(file_id)}
            )

        async def delete_message(
            self, message_id: str, *, chat_id: str = None, chat_type: str = None
        ) -> dict:
            """
            撤回消息

            云湖 /bot/recall 必须提供 chat_id + chat_type。
            缺省时返回参数错误（retcode=10003）。
            """
            if not chat_id or not chat_type:
                return self._adapter.make_error(
                    retcode=10003,
                    message="云湖撤回消息需要 chat_id 与 chat_type（如 chat_type='group'/'user'）",
                )
            return await self._adapter.call_api(
                "/bot/recall",
                _account_id=self._account_id,
                msgId=str(message_id),
                chatId=str(chat_id),
                chatType=str(chat_type),
            )

        # ==================== 官方服务端 API 扩展 ====================

        async def _bot_request(
            self, path: str, payload: Optional[dict] = None, method: str = "POST", query: Optional[dict] = None
        ) -> dict:
            """
            调用官方服务端 API（chat-go.jwzhd.com/open-apis，token 鉴权）

            始终返回原始 {code, msg, data} 结构（code==1 为成功）。
            """
            adapter = self._adapter
            bot_name, bot = adapter._resolve_account(self._account_id)
            url = f"{adapter.base_url}{path}?token={bot.token}"
            try:
                if method.upper() == "GET":
                    resp = await client.get(url, params=query or {})
                else:
                    resp = await client.post(url, json=payload or {})
                return await resp.json()
            except ClientTimeoutError:
                return {"code": -1, "msg": f"官方API请求超时: {path}"}
            except ClientError as e:
                return {"code": -1, "msg": f"官方API网络错误: {e}"}
            except Exception as e:
                return {"code": -1, "msg": f"官方API请求异常: {e}"}

        async def edit_message(
            self, message_id: str, recv_id: str, recv_type: str,
            content_type: str = "text", content: Any = None,
        ) -> dict:
            """编辑已发送消息（POST /bot/edit）"""
            return await self._adapter.call_api(
                "/bot/edit", _account_id=self._account_id,
                msgId=str(message_id), recvId=str(recv_id), recvType=str(recv_type),
                contentType=content_type, content=content or {"text": " "},
            )

        async def batch_send(
            self, user_ids: List[str], content_type: str = "text", content: Any = None
        ) -> dict:
            """批量给机器人用户发送消息（POST /bot/batch_send）"""
            return await self._adapter.call_api(
                "/bot/batch_send", _account_id=self._account_id,
                userIds=[str(u) for u in user_ids],
                contentType=content_type, content=content or {"text": " "},
            )

        async def get_message_list(
            self, chat_id: str, chat_type: str,
            message_id: Optional[str] = None, before: Optional[int] = None, after: Optional[int] = None,
        ) -> dict:
            """获取消息列表（GET /bot/messages，支持 before/after 翻页）"""
            query: Dict[str, Any] = {"chat-id": str(chat_id), "chat-type": str(chat_type)}
            if message_id:
                query["message-id"] = str(message_id)
            if before is not None:
                query["before"] = int(before)
            if after is not None:
                query["after"] = int(after)
            raw = await self._bot_request("/bot/messages", method="GET", query=query)
            return self._adapter._standardize_web_result(raw)

        async def set_user_board(
            self, chat_id: str, chat_type: str, content: str,
            content_type: str = "text", expire_time: int = 0,
        ) -> dict:
            """设置用户/群看板（POST /bot/board）"""
            payload: Dict[str, Any] = {
                "chatId": str(chat_id), "chatType": str(chat_type),
                "contentType": content_type, "content": content,
            }
            if expire_time:
                payload["expireTime"] = int(expire_time)
            return await self._adapter.call_api("/bot/board", _account_id=self._account_id, **payload)

        async def dismiss_user_board(self, chat_id: str, chat_type: str) -> dict:
            """取消用户/群看板（POST /bot/board-dismiss）"""
            return await self._adapter.call_api(
                "/bot/board-dismiss", _account_id=self._account_id,
                chatId=str(chat_id), chatType=str(chat_type),
            )

        async def set_global_board(self, content: str, content_type: str = "text", expire_time: int = 0) -> dict:
            """设置全局看板（POST /bot/board-all）"""
            payload: Dict[str, Any] = {"contentType": content_type, "content": content}
            if expire_time:
                payload["expireTime"] = int(expire_time)
            return await self._adapter.call_api("/bot/board-all", _account_id=self._account_id, **payload)

        async def dismiss_global_board(self) -> dict:
            """取消全部看板（POST /bot/board-all-dismiss）"""
            return await self._adapter.call_api("/bot/board-all-dismiss", _account_id=self._account_id)

        async def gag_group_member(self, group_id: str, user_id: str, gag_seconds: int) -> dict:
            """群成员禁言（POST /group/gag-member，gag 为禁言秒数，0 为解除）"""
            return await self._adapter.call_api(
                "/group/gag-member", _account_id=self._account_id,
                groupId=str(group_id), userId=str(user_id), gag=int(gag_seconds),
            )

        async def remove_group_member(self, group_id: str, user_id: str) -> dict:
            """移除群成员（POST /group/remove-member）"""
            return await self._adapter.call_api(
                "/group/remove-member", _account_id=self._account_id,
                groupId=str(group_id), userId=str(user_id),
            )

        async def set_group_msg_type_limit(self, group_id: str, allow_types: str) -> dict:
            """设置群允许发送的消息类型（POST /group/msg-type-limit，如 "text,image,video"）"""
            return await self._adapter.call_api(
                "/group/msg-type-limit", _account_id=self._account_id,
                groupId=str(group_id), type=str(allow_types),
            )

        async def create_group_tag(
            self, group_id: str, tag: str, color: str = "", desc: str = "", sort: int = 1
        ) -> dict:
            """创建群标签（POST /group/tag/create）"""
            payload: Dict[str, Any] = {"groupId": str(group_id), "tag": tag, "sort": int(sort)}
            if color:
                payload["color"] = color
            if desc:
                payload["desc"] = desc
            return await self._adapter.call_api("/group/tag/create", _account_id=self._account_id, **payload)

        async def list_group_tags(self, group_id: str) -> dict:
            """获取群标签列表（GET /group/tag/list）"""
            raw = await self._bot_request("/group/tag/list", method="GET", query={"groupId": str(group_id)})
            return self._adapter._standardize_web_result(raw)

        async def edit_group_tag(
            self, group_id: str, tag_id: str, tag: str = "", color: str = "", desc: str = "", sort: int = 1
        ) -> dict:
            """修改群标签（POST /group/tag/edit）"""
            payload: Dict[str, Any] = {"groupId": str(group_id), "tagId": str(tag_id), "sort": int(sort)}
            if tag:
                payload["tag"] = tag
            if color:
                payload["color"] = color
            if desc:
                payload["desc"] = desc
            return await self._adapter.call_api("/group/tag/edit", _account_id=self._account_id, **payload)

        async def delete_group_tag(self, group_id: str, tag_id: str) -> dict:
            """删除群标签（POST /group/tag/delete）"""
            return await self._adapter.call_api(
                "/group/tag/delete", _account_id=self._account_id,
                groupId=str(group_id), tagId=str(tag_id),
            )

        async def add_user_tag(self, group_id: str, user_id: str, tag: str) -> dict:
            """给用户添加标签（POST /group/tag/user-relate）"""
            return await self._adapter.call_api(
                "/group/tag/user-relate", _account_id=self._account_id,
                groupId=str(group_id), userId=str(user_id), tag=tag,
            )

        async def remove_user_tag(self, group_id: str, user_id: str, tag: str) -> dict:
            """给用户移除标签（POST /group/tag/user-relate-cancel）"""
            return await self._adapter.call_api(
                "/group/tag/user-relate-cancel", _account_id=self._account_id,
                groupId=str(group_id), userId=str(user_id), tag=tag,
            )

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
            self._board_expire: int = 0
            self._board_expire_at: int = 0
            self._board_member_id: Optional[str] = None

        def Buttons(self, buttons: List):
            """
            附加按钮（键盘）

            :param buttons: 兼容两种输入：
                - 通用标准结构：[[{"label": "..", "type": "callback|link", "data": ".."}]]
                - 原生结构：[{"label": "..", "action_type": 1|2, "url"/"action"/"value": ..}]
            :return: Send 实例，支持链式调用

            :example:
            >>> rows = [[{"label": "官网", "type": "link", "data": "https://example.com"}]]
            >>> await yunhu.Send.To("group", group_id).Buttons(rows).Text("请选择")
            """
            self._buttons = self._normalize_yunhu_buttons(buttons)
            return self

        def Keyboard(self, buttons: List):
            """`.Buttons()` 的标准别名（跨平台交互组件标准）"""
            return self.Buttons(buttons)

        @staticmethod
        def _normalize_yunhu_buttons(buttons):
            """
            按钮结构归一化：通用标准 rows → 云湖原生 buttons；原生结构原样透传（向后兼容）

            - callback → {"label", "action_type": 2, "action": "button_click", "value": data}
            - link     → {"label", "action_type": 1, "url": data}
            """
            if not isinstance(buttons, list):
                return buttons
            try:
                if buttons and isinstance(buttons[0], list):
                    flat = [b for row in buttons for b in row]
                else:
                    flat = buttons
                if not flat or not isinstance(flat[0], dict):
                    return buttons
                if all("action_type" in b or "label" not in b for b in flat):
                    return buttons  # 原生结构
                normalized = []
                for b in flat:
                    if not isinstance(b, dict):
                        continue
                    label = b.get("label", "")
                    if b.get("type") == "link":
                        normalized.append({"label": label, "action_type": 1, "url": b.get("data", "")})
                    else:
                        normalized.append({
                            "label": label,
                            "action_type": 2,
                            "action": b.get("action", "button_click"),
                            "value": b.get("value", b.get("data", "")),
                        })
                return normalized
            except (TypeError, AttributeError):
                return buttons

        def Expire(self, duration: int):
            self._board_expire = duration
            return self

        def ExpireAt(self, timestamp: int):
            self._board_expire_at = timestamp
            return self

        def ForMember(self, member_id: str):
            self._board_member_id = member_id
            return self

        def _reset_modifiers(self):
            self._buttons = None
            self._board_expire = 0
            self._board_expire_at = 0
            self._board_member_id = None
            self._keyboard_rows = None

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

        def _make_dismiss_task(self, is_local: bool, member_id: Optional[str], kwargs: dict):
            endpoint = "/bot/board-dismiss" if is_local else "/bot/board-all-dismiss"
            params = {}
            if is_local:
                params["chatId"] = self._target_id
                params["chatType"] = self._target_type
                if member_id is not None:
                    params["memberId"] = member_id
            params.update(kwargs)

            self._reset_modifiers()
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    _account_id=self._account_id,
                    **params,
                )
            )

        def Board(self, scope_or_content, content=None, content_type="text", **kwargs):
            """
            发布看板（终止方法）

            支持两种调用风格：

            1. 链式风格（推荐）：作用域由 To() 自动推断
               - 指定了 To(target_type, target_id) -> 本地看板（/bot/board）
               - 未指定 To() -> 全局看板（/bot/board-all）
               - 可选链式修饰：.Expire(duration) 相对过期、.ExpireAt(timestamp) 绝对过期、.ForMember(member_id) 群成员看板
               - 内容为空时自动转为撤销看板（等价于 DismissBoard）

               >>> await yunhu.Send.To("group", "123").Board("公告")
               >>> await yunhu.Send.To("group", "123").Expire(60).Board("60秒后过期", content_type="markdown")
               >>> await yunhu.Send.To("group", "123").ExpireAt(1785208268).Board("指定时间戳过期")
               >>> await yunhu.Send.To("group", "123").ForMember("uid").Board("仅你可见")
               >>> await yunhu.Send.To("group", "123").Board("")        # 清空本地看板
               >>> await yunhu.Send.Board("全局公告")

            2. 旧式风格（兼容）：显式传入 scope
               >>> await yunhu.Send.To("group", "123").Board("local", "公告")
               >>> await yunhu.Send.Board("global", "全局公告", expire_time=60)
            """
            if content is not None:
                scope = scope_or_content
                is_local = scope == "local"
            else:
                content = scope_or_content
                is_local = bool(self._target_id and self._target_type)

            member_id = kwargs.pop("member_id", None) or self._board_member_id

            # 内容为空 → 自动撤销看板
            if not content:
                return self._make_dismiss_task(is_local, member_id, kwargs)

            endpoint = "/bot/board" if is_local else "/bot/board-all"
            if "expire_time" in kwargs:
                # 旧式 kwarg：绝对时间戳（秒级），直接透传
                expire_time = kwargs.pop("expire_time")
            elif self._board_expire_at:
                # 新式 .ExpireAt(timestamp)：绝对时间戳
                expire_time = self._board_expire_at
            elif self._board_expire:
                # 新式 .Expire(duration)：相对时长（秒）→ 绝对时间戳
                expire_time = int(time.time()) + self._board_expire
            else:
                expire_time = 0

            params = {
                "contentType": content_type,
                "content": content,
                "expireTime": expire_time,
            }
            if is_local:
                params["chatId"] = self._target_id
                params["chatType"] = self._target_type
                if member_id is not None:
                    params["memberId"] = member_id
            params.update(kwargs)

            self._reset_modifiers()
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    _account_id=self._account_id,
                    **params,
                )
            )

        def DismissBoard(self, scope=None, **kwargs):
            """
            撤销看板（终止方法）

            支持两种调用风格：

            1. 链式风格（推荐）：作用域由 To() 自动推断
               >>> await yunhu.Send.To("group", "123").DismissBoard()
               >>> await yunhu.Send.To("group", "123").ForMember("uid").DismissBoard()
               >>> await yunhu.Send.DismissBoard()

            2. 旧式风格（兼容）：显式传入 scope
               >>> await yunhu.Send.To("group", "123").DismissBoard("local")
               >>> await yunhu.Send.DismissBoard("global")
            """
            if scope is not None:
                is_local = scope == "local"
            else:
                is_local = bool(self._target_id and self._target_type)

            member_id = kwargs.pop("member_id", None) or self._board_member_id
            return self._make_dismiss_task(is_local, member_id, kwargs)

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

            # 标准 keyboard 段（跨平台通用）→ 云湖 buttons
            keyboard_rows = [
                seg for seg in message if isinstance(seg, dict) and seg.get("type") == "keyboard"
            ]
            if keyboard_rows:
                self._buttons = self._normalize_yunhu_buttons(
                    keyboard_rows[-1].get("data", {}).get("rows", [])
                )
                message = [
                    seg for seg in message
                    if not (isinstance(seg, dict) and seg.get("type") == "keyboard")
                ]

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
            """（已迁移至 YunhuAdapter._detect_extension）保留以兼容旧调用"""
            return self._adapter._OFFICE_SIGNATURES.get(
                next(
                    (sig for sig in self._adapter._OFFICE_SIGNATURES if sample_bytes.startswith(sig)),
                    b"",
                ),
                None,
            )

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

                # sdk.client 在返回前已 eager-read 缓冲整个响应体，
                # 直接读取内存中的 bytes，避免流式读取连接被关闭的问题。
                file_data = await resp.read()
                downloaded_size = len(file_data)
                if downloaded_size > max_size:
                    self._adapter.logger.warning(
                        f"下载文件过大: {downloaded_size / 1024 / 1024:.2f}MB (限制: {max_size / 1024 / 1024:.0f}MB)"
                    )
                    return None, None

                file_buffer = io.BytesIO(file_data)
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

        async def _send_file_fail_text(self, subject: str, reason: str, kwargs: dict):
            """上传失败时向目标发送文本说明消息"""
            error_msg = f"[文件发送失败] 无法发送文件: {subject}\n原因: {reason}"
            return await self._adapter.call_api(
                endpoint="/bot/send",
                _account_id=self._account_id,
                recvId=self._target_id,
                recvType=self._target_type,
                contentType="text",
                content={"text": error_msg},
                parentId=kwargs.get("parent_id", ""),
            )

        async def _upload_file_and_call_api(
            self, upload_endpoint, file_name, file, endpoint, content_type, **kwargs
        ):
            bot_name, bot = self._adapter._resolve_account(self._account_id)

            # 1. 将 file 归一化为 bytes（支持 URL / 本地路径 / bytes / 文件对象 / 异步生成器）
            if isinstance(file, str) and (
                file.startswith("http://") or file.startswith("https://")
            ):
                self._adapter.logger.info(f"检测到URL，开始下载: {file}")
                file_buffer, downloaded_filename = await self._download_file_from_url(file)
                if file_buffer is None:
                    return await self._send_file_fail_text(
                        file, "文件过大(超过100MB)或下载失败", kwargs
                    )
                if file_name is None and downloaded_filename:
                    file_name = downloaded_filename
                file_bytes = file_buffer.getvalue()

            elif isinstance(file, str):
                import os

                if os.path.exists(file) and os.path.isfile(file):
                    self._adapter.logger.info(f"检测到本地文件路径，开始读取: {file}")
                    file_data, local_filename = self._read_local_file(file)
                    if file_data is None:
                        return await self._send_file_fail_text(
                            file, "文件不存在、过大或读取失败", kwargs
                        )
                    if file_name is None and local_filename:
                        file_name = local_filename
                    file_bytes = file_data
                else:
                    return await self._send_file_fail_text(file, "文件路径不存在", kwargs)

            elif isinstance(file, (bytes, bytearray)):
                file_bytes = bytes(file)

            elif hasattr(file, "__aiter__"):
                # 异步生成器（流式）
                temp_buffer = io.BytesIO()
                async for chunk in file:
                    temp_buffer.write(chunk)
                file_bytes = temp_buffer.getvalue()

            elif hasattr(file, "read") and callable(file.read):
                # BytesIO / 文件对象
                file_bytes = file.read()
            else:
                raise ValueError("无法识别的文件类型")

            # 2. 类型检测 + 构建上传文件名
            ext = self._adapter._detect_extension(file_bytes, file_name)
            upload_filename = self._adapter._build_upload_filename(
                file_name, content_type, ext
            )

            # 3. 执行上传
            upload_url = f"{self._adapter.base_url}{upload_endpoint}?token={bot.token}"
            try:
                upload_res = await self._adapter._perform_upload(
                    upload_url, content_type, file_bytes, upload_filename
                )
            except ValueError as e:
                self._adapter.logger.error(f"文件上传被拒绝: {_mask_token(upload_url)}: {e}")
                return await self._send_file_fail_text(upload_filename, str(e), kwargs)
            except (ClientTimeoutError, ClientError) as e:
                self._adapter.logger.error(
                    f"文件上传失败: {_mask_token(upload_url)}, 错误: {str(e)}"
                )
                return await self._send_file_fail_text(upload_filename, "网络错误或上传超时", kwargs)
            except Exception as e:
                self._adapter.logger.error(
                    f"文件上传异常: {_mask_token(upload_url)}, 错误: {str(e)}"
                )
                raise

            # 4. 提取媒体 key 并调用发送接口
            key_name = {"image": "imageKey", "video": "videoKey", "file": "fileKey"}.get(
                content_type, "fileKey"
            )
            try:
                media_value = self._adapter._extract_upload_key(upload_res, content_type)
            except ValueError as e:
                self._adapter.logger.error(f"上传响应异常: {e}")
                return await self._send_file_fail_text(upload_filename, str(e), kwargs)

            return await self._send_media_payload(
                endpoint, key_name, media_value, content_type, kwargs
            )

        async def _send_media_payload(
            self, endpoint, key_name, media_value, content_type, kwargs
        ):
            """构造媒体发送 payload 并调用发送接口"""
            payload = {
                "recvId": self._target_id,
                "recvType": self._target_type,
                "contentType": content_type,
                "content": {key_name: media_value},
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
        # 从全局配置读取 API 地址（默认值见 YunhuGlobalConfig）
        cfg = self.cfg
        self.base_url = cfg.base_url
        self.web_api_base_url = cfg.web_api_base_url
        self.ws_base_url = cfg.ws_base_url
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        self._ws_connections: Dict[str, ClientWebSocket] = {}
        self._bot_ids: Dict[str, str] = {}
        self._is_running = False

        self.convert = self._setup_converter()

        self._check_framework_version()
        self._get_logger().info(f"YunhuAdapter v{__version__} 已加载")

    @staticmethod
    def _parse_version(version_str: str) -> tuple:
        """解析版本号为可比较的三元组（忽略 dev/预发布后缀，如 2.8.0-dev.3 → (2, 8, 0)）"""
        parts = []
        for piece in str(version_str).split("."):
            digits = "".join(ch for ch in piece if ch.isdigit())
            parts.append(int(digits) if digits else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def _check_framework_version(self):
        """软依赖检测：框架版本过低时打警告（不阻断加载）"""
        try:
            from importlib.metadata import version as _pkg_version

            raw = _pkg_version("ErisPulse")
        except Exception:
            return
        try:
            if self._parse_version(raw) < MIN_FRAMEWORK_VERSION:
                self._get_logger().warning(
                    f"当前 ErisPulse 版本 {raw} 过低：YunhuAdapter v{__version__} 需要 >= "
                    f"{'.'.join(map(str, MIN_FRAMEWORK_VERSION))}"
                    "（BaseConverter / Api DSL / spawn_background 等特性），"
                    "部分功能可能不可用，建议升级框架"
                )
        except Exception:
            pass

    def _setup_converter(self):
        from .Converter import YunhuConverter

        convert = YunhuConverter()
        return convert.convert

    def on_config_update(self, old_config, new_config):
        """配置热更新：API 地址变更时同步实例属性"""
        if new_config is None:
            return
        self.base_url = new_config.base_url
        self.web_api_base_url = new_config.web_api_base_url
        self.ws_base_url = new_config.ws_base_url
        if old_config and (
            old_config.base_url != new_config.base_url
            or old_config.ws_base_url != new_config.ws_base_url
        ):
            self.logger.info("API 地址配置已更新，下次连接生效")

    # ==================== 文件上传辅助（供 Api.upload_file 使用） ====================

    async def _read_upload_bytes(
        self,
        *,
        type: str,
        url: str | None = None,
        path: str | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str]:
        """
        按来源读取文件为 bytes

        :return: (文件字节数据, 文件名)
        """
        if type == "data":
            if data is None:
                raise ValueError("type=data 时必须提供 data")
            return data, ""

        if type == "path":
            if not path:
                raise ValueError("type=path 时必须提供 path")
            import os

            if not os.path.exists(path):
                raise FileNotFoundError(f"文件不存在: {path}")
            with open(path, "rb") as f:
                return f.read(), os.path.basename(path)

        if type == "url":
            if not url:
                raise ValueError("type=url 时必须提供 url")
            from urllib.parse import urlparse, unquote

            resp = await client.get(url, headers=headers or {}, timeout=300)
            # sdk.client 返回前已 eager-read 缓冲整个响应体，直接读取内存 bytes
            file_data = await resp.read()
            filename = unquote(urlparse(url).path.split("/")[-1]) or ""
            return file_data, filename

        raise ValueError(f"不支持的 type: {type}")

    @staticmethod
    def _detect_category(filename: str, file_bytes: bytes) -> str:
        """
        自动判定上传类别：image / video / file

        优先用 filetype 探测 MIME，其次用文件名后缀兜底。
        """
        mime = ""
        try:
            sample = file_bytes[:1024] if file_bytes else b""
            info = filetype.guess(sample) if sample else None
            if info:
                mime = info.mime
        except Exception:
            pass

        if mime.startswith("image/"):
            return "image"
        if mime.startswith("video/"):
            return "video"

        # 后缀兜底
        lower = (filename or "").lower()
        image_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico")
        video_exts = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv", ".webm")
        if lower.endswith(image_exts):
            return "image"
        if lower.endswith(video_exts):
            return "video"
        return "file"

    # Office 文档魔数签名（filetype 会把 docx/xlsx/pptx 识别为 zip）
    _OFFICE_SIGNATURES = {
        b"PK\x03\x04\x14\x00\x06\x00": "docx",
        b"PK\x03\x04\x14\x00\x00\x08": "xlsx",
        b"PK\x03\x04\x14\x00\x00\x06": "pptx",
    }

    @classmethod
    def _detect_extension(cls, file_bytes: bytes, filename: str = "") -> Optional[str]:
        """
        检测文件扩展名（含 Office 文档特殊处理）。

        优先 filetype 探测，其次文件名后缀兜底。
        """
        try:
            sample = file_bytes[:1024] if file_bytes else b""
            info = filetype.guess(sample) if sample else None
            if info:
                if info.mime == "application/zip":
                    for signature, ext in cls._OFFICE_SIGNATURES.items():
                        if sample.startswith(signature):
                            return ext
                return info.extension
        except Exception:
            pass
        lower = (filename or "").lower()
        if "." in lower:
            return lower.rsplit(".", 1)[-1] or None
        return None

    @staticmethod
    def _build_upload_filename(
        file_name: Optional[str], content_type: str, file_extension: Optional[str]
    ) -> str:
        """构建上传文件名（补全扩展名，便于服务端识别）"""
        if not file_name:
            return f"{content_type}.{file_extension}" if file_extension else f"{content_type}.bin"
        if file_extension and "." not in file_name:
            return f"{file_name}.{file_extension}"
        return file_name

    async def _perform_upload(
        self, upload_url: str, content_type: str, file_bytes: bytes, filename: str
    ) -> dict:
        """
        执行 multipart/form-data 文件上传，返回云湖上传响应 {code, data, msg}。

        :raises ValueError: 上传被服务器拒绝（413 过大 / 非 JSON 响应 / code != 1）
        :raises ClientError / ClientTimeoutError: 网络层错误（由调用方决定处理策略）
        """
        import aiohttp  # 仅用于 FormData（ErisPulse 已内置 aiohttp）

        form = aiohttp.FormData(quote_fields=False)
        form.add_field(
            name=content_type,
            value=io.BytesIO(file_bytes),
            filename=filename or f"{content_type}.bin",
        )
        resp = await client.post(upload_url, data=form, timeout=300)
        if resp.status == 413:
            raise ValueError("文件过大，超过云湖服务器限制")
        try:
            upload_res = await resp.json()
        except (json.JSONDecodeError, ValueError):
            error_text = (await resp.text())[:500]
            raise ValueError(f"服务器返回错误 (状态码: {resp.status}): {error_text}")
        if upload_res.get("code") != 1:
            raise ValueError(f"文件上传失败: {upload_res}")
        return upload_res

    @staticmethod
    def _extract_upload_key(upload_res: dict, content_type: str) -> str:
        """从上传响应中提取媒体 key（imageKey / videoKey / fileKey）"""
        key_map = {"image": "imageKey", "video": "videoKey", "file": "fileKey"}
        key_name = key_map.get(content_type, "fileKey")
        data = upload_res.get("data", {})
        if key_name not in data:
            raise ValueError(f"上传API返回的数据格式不正确，缺少 {key_name}")
        return data[key_name]


    async def _net_request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        params: Dict = None,
        bot_token: str = None,
        max_retries: int = 2,
    ) -> Dict:
        import aiohttp  # 仅用于捕获底层异常（ErisPulse 已内置 aiohttp）

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

    # yunhu.* 扩展动作 → 平台端点映射表
    # 值为 (endpoint, [(ob12_param, yunhu_param), ...]) ；ob12_param 缺省时原样保留
    _EXTENSION_MAP: Dict[str, tuple] = {
        "yunhu.recall": ("/bot/recall", [("msg_id", "msgId"), ("chat_id", "chatId"), ("chat_type", "chatType")]),
        "yunhu.kick": ("/group/remove-member", [("user_id", "userId"), ("group_id", "groupId")]),
        "yunhu.ban": ("/group/gag-member", [("user_id", "userId"), ("group_id", "groupId"), ("duration", "gag")]),
        "yunhu.unban": ("/group/gag-member", [("user_id", "userId"), ("group_id", "groupId")]),
        "yunhu.tag.create": ("/group/tag/create", [("group_id", "groupId"), ("new_tag", "newTag")]),
        "yunhu.tag.edit": ("/group/tag/edit", [("group_id", "groupId"), ("new_tag", "newTag")]),
        "yunhu.tag.delete": ("/group/tag/delete", [("group_id", "groupId")]),
        "yunhu.tag.list": ("/group/tag/list", [("group_id", "groupId")]),
        # 成员头衔语义别名（标签 ≈ 头衔）→ 映射到 user-relate
        "yunhu.set_member_title": ("/group/tag/user-relate", [("user_id", "userId"), ("title", "tag"), ("group_id", "groupId")]),
        "yunhu.unset_member_title": ("/group/tag/user-relate-cancel", [("user_id", "userId"), ("title", "tag"), ("group_id", "groupId")]),
        "yunhu.tag.relate": ("/group/tag/user-relate", [("user_id", "userId"), ("group_id", "groupId")]),
        "yunhu.tag.relate_cancel": ("/group/tag/user-relate-cancel", [("user_id", "userId"), ("group_id", "groupId")]),
        "yunhu.msg_type_limit": ("/group/msg-type-limit", [("group_id", "groupId")]),
    }

    def _map_extension_action(self, endpoint: str, params: dict) -> Optional[str]:
        """
        将 yunhu.* 扩展动作名映射为平台端点，并翻译参数键名。

        :return: 映射后的端点；非扩展动作返回 None
        """
        if endpoint not in self._EXTENSION_MAP:
            return None

        platform_endpoint, key_map = self._EXTENSION_MAP[endpoint]

        # yunhu.unban: 设置 gag=0（解除禁言）
        if endpoint == "yunhu.unban":
            params.setdefault("gag", 0)

        # 翻译参数键名（OB12 风格 → 云湖风格）
        if key_map:
            for ob12_key, yunhu_key in key_map:
                if ob12_key in params:
                    params[yunhu_key] = params.pop(ob12_key)

        return platform_endpoint

    def _standardize_web_result(self, raw) -> dict:
        """
        将公开 Web API 的原始响应（{code, msg, data}）标准化为标准响应格式。

        已标准化（含 status 键）的响应原样返回。
        """
        if isinstance(raw, dict) and raw.get("status") in ("ok", "failed"):
            return raw
        if isinstance(raw, dict) and raw.get("code") == 1:
            self.logger.debug(f"Web API 查询成功: {json.dumps(raw.get('data'), ensure_ascii=False)[:300]}")
            return self.make_response(data=raw.get("data"), raw=raw)
        self.logger.warning(f"Web API 查询失败: {raw.get('msg', '未知错误') if isinstance(raw, dict) else raw}")
        return self.make_error(
            retcode=34001,
            message=raw.get("msg", "Web API 请求失败") if isinstance(raw, dict) else str(raw),
            raw=raw,
        )

    async def call_api(self, endpoint: str, _account_id: str = None, **params):
        bot_name, bot = self._resolve_account(_account_id)

        # 从 ApiDSL._merge_context 等来源可能带入 account_id，需从业务参数中剔除
        params.pop("account_id", None)

        # 1. 不支持的 OneBot12 标准动作 → retcode=10002
        if endpoint in _UNSUPPORTED_STANDARD_ACTIONS:
            return self.make_error(
                retcode=10002,
                message=f"云湖适配器不支持的标准动作: {endpoint}",
            )

        # 2. 特殊扩展动作（非 POST / 走 web API）
        if endpoint == "yunhu.get_messages":
            # OB12 风格参数 → 云湖 hyphen 风格查询参数
            msg_params = {}
            for k, v in params.items():
                if k == "chat_id":
                    msg_params["chat-id"] = str(v)
                elif k == "chat_type":
                    msg_params["chat-type"] = str(v)
                elif k == "message_id":
                    msg_params["message-id"] = str(v)
                else:
                    msg_params[k] = v
            return await self.get_messages(_account_id=_account_id, **msg_params)
        if endpoint == "yunhu.bot_info":
            raw = await self.Api._web_request(
                "/v1/bot/bot-info", {"botId": str(params.get("bot_id", ""))}
            )
            resp = self._standardize_web_result(raw)
            resp["self"] = {"user_id": self._bot_ids.get(bot_name, "")}
            return resp
        if endpoint == "yunhu.user_homepage":
            raw = await self.Api._web_request(
                "/v1/user/homepage",
                {"userId": str(params.get("user_id", ""))},
                method="GET",
            )
            resp = self._standardize_web_result(raw)
            resp["self"] = {"user_id": self._bot_ids.get(bot_name, "")}
            return resp

        # 3. yunhu.* 平台扩展动作 → 路由到对应 POST 端点
        mapped_endpoint = self._map_extension_action(endpoint, params)
        if mapped_endpoint is not None:
            endpoint = mapped_endpoint

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
                data = raw_response.get("data", {}) or {}
                message_id = (
                    data.get("messageInfo", {}).get("msgId", "")
                    if "messageInfo" in data
                    else data.get("msgId", "")
                )
                # 保留平台返回的真实 data（如标签列表 / 历史消息 / 看板等），
                # 发送类响应（含 messageInfo）额外注入 message_id/time 便于调用方读取。
                if isinstance(data, dict):
                    data = dict(data)  # 浅拷贝，避免改动 raw
                    if message_id:
                        data.setdefault("message_id", message_id)
                        data.setdefault("time", time.time())
                resp = self.make_response(
                    data=data,
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
            coro = self._ws_connect(bot_name)
            # 生命周期任务使用 spawn_background（owner 归属，shutdown 自动回收）
            self._ws_tasks[bot_name] = (
                spawn_background(coro) if spawn_background is not None else asyncio.create_task(coro)
            )

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
