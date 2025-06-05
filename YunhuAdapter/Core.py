import asyncio
import aiohttp
from aiohttp import web
from typing import Dict, List, Optional, Any
from ErisPulse.adapter import BaseAdapter

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger

    def register_adapters(self):
        self.logger.debug("注册云湖适配器")
        return {
            "Yunhu": YunhuAdapter
        }

class YunhuAdapter(BaseAdapter):
    def __init__(self, sdk):
        super().__init__()
        self.sdk = sdk
        self.logger = sdk.logger
        self.config = self._load_config()
        self.yhToken = self.config.get("token", "")
        self.session: Optional[aiohttp.ClientSession] = None
        self.server: Optional[web.AppRunner] = None
        self.base_url = "https://chat-go.jwzhd.com/open-apis/v1"
        self._setup_event_mapping()

    def _load_config(self) -> Dict:
        config = self.sdk.env.get("YunhuAdapter", {})
        if not config:
            self.logger.warning("云湖配置缺失，请在env.py中添加配置")
        return config

    def _setup_event_mapping(self):
        self.event_map = {
            "message.receive.normal": "message",
            "message.receive.instruction": "command",
            "bot.followed": "follow",
            "bot.unfollowed": "unfollow",
            "group.join": "group_join",
            "group.leave": "group_leave",
            "button.report.inline": "button_click",
            "bot.shortcut.menu": "shortcut_menu"
        }

    async def _net_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}{endpoint}?token={self.yhToken}"
        if not self.session:
            self.session = aiohttp.ClientSession()

        async with self.session.request(
            method,
            url,
            json=data,
            headers={"Content-Type": "application/json"}
        ) as response:
            return await response.json()

    async def _upload_file(self, endpoint: str, field_name: str, content: bytes) -> Dict:
        url = f"{self.base_url}{endpoint}?token={self.yhToken}"
        if not self.session:
            self.session = aiohttp.ClientSession()

        filename = f"file.{field_name}"
        data = aiohttp.FormData()
        data.add_field(
            field_name,
            content,
            filename=filename,
            content_type="application/octet-stream"
        )

        self.logger.debug(f"上传文件到{url}")
        async with self.session.post(url, data=data) as response:
            return await response.json()

    async def send(self, conversation_type: str, target_id: str, message: Any, **kwargs):
        endpoint = "/bot/send"
        buttons = kwargs.get("buttons", [])
        parent_id = kwargs.get("parent_id", "")

        self.logger.debug(f"准备发送消息到 {target_id}， 会话类型: {conversation_type},  内容: {message}")
        if isinstance(message, str):
            content_type = kwargs.get("content_type", "text")
            content = {"text": message, "buttons": buttons}
        elif isinstance(message, bytes):
            if kwargs.get("content_type") == "image":
                self.logger.debug("开始上传图片")
                upload_res = await self._upload_file("/image/upload", "image", message)
                content_type = "image"
                content = {"imageKey": upload_res["data"]["imageKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "video":
                self.logger.debug("开始上传视频")
                upload_res = await self._upload_file("/video/upload", "video", message)
                content_type = "video"
                content = {"videoKey": upload_res["data"]["videoKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "file":
                self.logger.debug("开始上传文件")
                upload_res = await self._upload_file("/file/upload", "file", message)
                content_type = "file"
                content = {"fileKey": upload_res["data"]["fileKey"], "buttons": buttons}
            else:
                self.logger.error("不支持的二进制内容类型")
                raise ValueError("Unsupported binary content type")
        else:
            self.logger.error("不支持的消息类型")
            raise ValueError("Unsupported message type")

        payload = {
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type,
            "content": content,
            "parentId": parent_id
        }

        self.logger.debug(f"发送Call到`{endpoint}`")
        return await self._net_request("POST", endpoint, payload)
    async def send_stream(self, conversation_type: str, target_id: str, content_type: str, content_generator, **kwargs) -> Dict:
        endpoint = "/bot/send-stream"
        params = {
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type
        }
        if "parent_id" in kwargs:
            params["parentId"] = kwargs["parent_id"]
        url = f"{self.base_url}{endpoint}?token={self.yhToken}"
        query_params = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}&{query_params}"
        self.logger.debug(f"准备发送流式消息到 {target_id}， 会话类型: {conversation_type}, 内容类型: {content_type}")
        if not self.session:
            self.session = aiohttp.ClientSession()
        headers = {
            "Content-Type": "text/plain"
        }
        async with self.session.post(full_url, headers=headers, data=content_generator) as response:
            return await response.json()
    async def batch_send(self, conversation_type: str, target_ids: List[str], message: Any, **kwargs):
        endpoint = "/bot/batch_send"
        buttons = kwargs.get("buttons", [])
        parent_id = kwargs.get("parent_id", "")

        self.logger.debug(f"准备批量发送消息到{len(target_ids)}个目标")
        if isinstance(message, str):
            content_type = "text"
            content = {"text": message, "buttons": buttons}
        elif isinstance(message, bytes):
            if kwargs.get("content_type") == "image":
                self.logger.debug("开始批量上传图片")
                upload_res = await self._upload_file("/image/upload", "image", message)
                content_type = "image"
                content = {"imageKey": upload_res["data"]["imageKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "video":
                self.logger.debug("开始批量上传视频")
                upload_res = await self._upload_file("/video/upload", "video", message)
                content_type = "video"
                content = {"videoKey": upload_res["data"]["videoKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "file":
                self.logger.debug("开始批量上传文件")
                upload_res = await self._upload_file("/file/upload", "file", message)
                content_type = "file"
                content = {"fileKey": upload_res["data"]["fileKey"], "buttons": buttons}
            else:
                self.logger.error("不支持的二进制内容类型")
                raise ValueError("Unsupported binary content type")
        else:
            self.logger.error("不支持的消息类型")
            raise ValueError("Unsupported message type")

        payload = {
            "recvIds": target_ids,
            "recvType": conversation_type,
            "contentType": content_type,
            "content": content,
            "parentId": parent_id
        }

        self.logger.debug(f"批量发送消息到{endpoint}")
        return await self._net_request("POST", endpoint, payload)

    async def publish_board(self, scope: str, content: str, **kwargs):
        if scope == "local":
            endpoint = "/bot/board"
            payload = {
                "chatId": kwargs["chat_id"],
                "chatType": kwargs["chat_type"],
                "contentType": kwargs.get("content_type", "text"),
                "content": content,
                "memberId": kwargs.get("member_id", ""),
                "expireTime": kwargs.get("expire_time", 0)
            }
            self.logger.debug("发布局部公告看板")
        else:
            endpoint = "/bot/board-all"
            payload = {
                "contentType": kwargs.get("content_type", "text"),
                "content": content,
                "expireTime": kwargs.get("expire_time", 0)
            }
            self.logger.debug("发布全局公告看板")

        return await self._net_request("POST", endpoint, payload)

    async def dismiss_board(self, scope: str, **kwargs):
        if scope == "local":
            endpoint = "/bot/board-dismiss"
            payload = {
                "chatId": kwargs["chat_id"],
                "chatType": kwargs["chat_type"],
                "memberId": kwargs.get("member_id", "")
            }
            self.logger.debug("撤销局部公告看板")
        else:
            endpoint = "/bot/board-all-dismiss"
            payload = {}
            self.logger.debug("撤销全局公告看板")

        return await self._net_request("POST", endpoint, payload)

    async def edit(self, msg_id: str, conversation_type: str, target_id: str, message: Any, **kwargs):
        endpoint = "/bot/edit"
        buttons = kwargs.get("buttons", [])

        self.logger.debug(f"准备编辑消息{msg_id}")
        if isinstance(message, str):
            content_type = "text"
            content = {"text": message, "buttons": buttons}
        else:
            self.logger.error("当前仅支持文本编辑")
            raise ValueError("Currently only text editing is supported")

        payload = {
            "msgId": msg_id,
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type,
            "content": content
        }

        return await self._net_request("POST", endpoint, payload)

    async def recall(self, msg_id: str, conversation_type: str, target_id: str):
        endpoint = "/bot/recall"
        payload = {
            "msgId": msg_id,
            "chatId": str(target_id),
            "chatType": conversation_type
        }

        self.logger.debug(f"准备撤回消息{msg_id}")
        return await self._net_request("POST", endpoint, payload)

    async def get_history(self, conversation_type: str, target_id: str, **kwargs):
        endpoint = "/bot/messages"
        params = {
            "chat-id": target_id,
            "chat-type": conversation_type
        }

        if "before" in kwargs:
            params["before"] = kwargs["before"]
        if "after" in kwargs:
            params["after"] = kwargs["after"]
        if "msg_id" in kwargs:
            params["message-id"] = kwargs["msg_id"]

        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{endpoint}?token={self.yhToken}&{query}"

        self.logger.debug(f"查询历史消息:{query}")
        return await self._net_request("GET", url)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            event_type = data["header"]["eventType"]
            mapped_type = self.event_map.get(event_type, "unknown")

            self.logger.debug(f"处理Webhook事件:{event_type} -> {mapped_type}")
            await self.emit(mapped_type, data)
            return web.Response(text="OK", status=200)
        except Exception as e:
            self.logger.error(f"Webhook处理错误: {str(e)}")
            return web.Response(text=f"ERROR: {str(e)}", status=500)

    async def start_server(self):
        if not self.config.get("server"):
            self.logger.warning("Webhook服务器未配置，将不会启动")
            return

        server_config = self.config["server"]
        app = web.Application()
        app.router.add_post(
            server_config.get("path", "/"),
            self._handle_webhook
        )

        self.server = web.AppRunner(app)
        await self.server.setup()

        site = web.TCPSite(
            self.server,
            server_config.get("host", "127.0.0.1"),
            server_config.get("port", 8080)
        )
        await site.start()
        self.logger.info(f"Webhook服务器已启动: {site.name}")

    async def stop_server(self):
        if self.server:
            await self.server.cleanup()
            self.server = None
            self.logger.info("Webhook服务器已停止")

    async def start(self):
        if self.config.get("server"):
            self.logger.info("启动云湖适配器")
            await self.start_server()

    async def shutdown(self):
        await self.stop_server()
        if self.session:
            await self.session.close()
            self.session = None
        self.logger.info("云湖适配器已关闭")

    async def call_api(self, endpoint: str, **params) -> Any:
        self.logger.debug(f"调用API:{endpoint}")
        return await self._net_request("POST", endpoint, params)