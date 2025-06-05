# YunhuAdapter/Core.py
import asyncio
import aiohttp
from aiohttp import web
from typing import Dict, List, Optional, Any
from ErisPulse import sdk
from ErisPulse.adapter import BaseAdapter

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger

    def register_adapters(self):
        return {
            "Yunhu": YunhuAdapter
        }

class YunhuAdapter(BaseAdapter):
    """云湖协议适配器
    支持功能:
    1. 消息发送 (单条/批量)
    2. 公告看板管理
    3. 消息编辑
    4. 历史消息查询
    5. 事件监听 (Webhook)
    """
    def __init__(self, sdk):
        super().__init__()
        self.sdk = sdk
        self.logger = sdk.logger
        self.config = self._load_config()
        self.yhToken = self.config.get("token", "")
        self.session: Optional[aiohttp.ClientSession] = None
        self.server: Optional[web.AppRunner] = None

        # 初始化API端点
        self.base_url = "https://chat-go.jwzhd.com/open-apis/v1"
        self._setup_event_mapping()

    def _load_config(self) -> Dict:
        config = self.sdk.env.get("YunhuAdapter", {})
        if not config:
            self.logger.warning("""
            云湖配置缺失，请在env.py中添加配置:
            sdk.env.set("YunhuAdapter", {
                "token": "your_token",
                "server": {
                    "host": "127.0.0.1",
                    "port": 8080,
                    "path": "/"
                }
            })
            """)
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
        """基础网络请求方法"""
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
        """文件上传方法"""
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

        async with self.session.post(url, data=data) as response:
            return await response.json()

    # 消息发送相关方法
    async def send(self, conversation_type: str, target_id: str, message: Any, **kwargs):
        """发送单条消息"""
        endpoint = "/bot/send"
        buttons = kwargs.get("buttons", [])
        parent_id = kwargs.get("parent_id", "")

        if isinstance(message, str):
            content_type = "text"
            content = {"text": message, "buttons": buttons}
        elif isinstance(message, bytes):
            # 判断文件类型并上传
            if kwargs.get("content_type") == "image":
                upload_res = await self._upload_file("/image/upload", "image", message)
                content_type = "image"
                content = {"imageKey": upload_res["data"]["imageKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "video":
                upload_res = await self._upload_file("/video/upload", "video", message)
                content_type = "video"
                content = {"videoKey": upload_res["data"]["videoKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "file":
                upload_res = await self._upload_file("/file/upload", "file", message)
                content_type = "file"
                content = {"fileKey": upload_res["data"]["fileKey"], "buttons": buttons}
            else:
                raise ValueError("Unsupported binary content type")
        else:
            raise ValueError("Unsupported message type")

        payload = {
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type,
            "content": content,
            "parentId": parent_id
        }

        return await self._net_request("POST", endpoint, payload)

    async def batch_send(self, conversation_type: str, target_ids: List[str], message: Any, **kwargs):
        """批量发送消息"""
        endpoint = "/bot/batch_send"
        buttons = kwargs.get("buttons", [])
        parent_id = kwargs.get("parent_id", "")

        if isinstance(message, str):
            content_type = "text"
            content = {"text": message, "buttons": buttons}
        elif isinstance(message, bytes):
            # 文件上传逻辑与send方法相同
            if kwargs.get("content_type") == "image":
                upload_res = await self._upload_file("/image/upload", "image", message)
                content_type = "image"
                content = {"imageKey": upload_res["data"]["imageKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "video":
                upload_res = await self._upload_file("/video/upload", "video", message)
                content_type = "video"
                content = {"videoKey": upload_res["data"]["videoKey"], "buttons": buttons}
            elif kwargs.get("content_type") == "file":
                upload_res = await self._upload_file("/file/upload", "file", message)
                content_type = "file"
                content = {"fileKey": upload_res["data"]["fileKey"], "buttons": buttons}
            else:
                raise ValueError("Unsupported binary content type")
        else:
            raise ValueError("Unsupported message type")

        payload = {
            "recvIds": target_ids,
            "recvType": conversation_type,
            "contentType": content_type,
            "content": content,
            "parentId": parent_id
        }

        return await self._net_request("POST", endpoint, payload)

    # 公告看板相关方法
    async def publish_board(self, scope: str, content: str, **kwargs):
        """发布公告看板"""
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
        else:
            endpoint = "/bot/board-all"
            payload = {
                "contentType": kwargs.get("content_type", "text"),
                "content": content,
                "expireTime": kwargs.get("expire_time", 0)
            }

        return await self._net_request("POST", endpoint, payload)

    async def dismiss_board(self, scope: str, **kwargs):
        """撤销公告看板"""
        if scope == "local":
            endpoint = "/bot/board-dismiss"
            payload = {
                "chatId": kwargs["chat_id"],
                "chatType": kwargs["chat_type"],
                "memberId": kwargs.get("member_id", "")
            }
        else:
            endpoint = "/bot/board-all-dismiss"
            payload = {}

        return await self._net_request("POST", endpoint, payload)

    # 消息编辑方法
    async def edit(self, msg_id: str, conversation_type: str, target_id: str, message: Any, **kwargs):
        """编辑已发送消息"""
        endpoint = "/bot/edit"
        buttons = kwargs.get("buttons", [])

        if isinstance(message, str):
            content_type = "text"
            content = {"text": message, "buttons": buttons}
        else:
            raise ValueError("Currently only text editing is supported")

        payload = {
            "msgId": msg_id,
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type,
            "content": content
        }

        return await self._net_request("POST", endpoint, payload)

    # 历史消息相关方法
    async def recall(self, msg_id: str, conversation_type: str, target_id: str):
        """撤回消息"""
        endpoint = "/bot/recall"
        payload = {
            "msgId": msg_id,
            "chatId": target_id,
            "chatType": conversation_type
        }

        return await self._net_request("POST", endpoint, payload)

    async def get_history(self, conversation_type: str, target_id: str, **kwargs):
        """查询历史消息"""
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

        return await self._net_request("GET", url)

    # Webhook服务器相关方法
    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """处理Webhook请求"""
        try:
            data = await request.json()
            event_type = data["header"]["eventType"]
            mapped_type = self.event_map.get(event_type, "unknown")

            await self.emit(mapped_type, data)
            return web.Response(text="OK", status=200)
        except Exception as e:
            self.logger.error(f"Webhook处理错误: {str(e)}")
            return web.Response(text=f"ERROR: {str(e)}", status=500)

    async def start_server(self):
        """启动Webhook服务器"""
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
        self.logger.info(f"Webhook服务器已启动: http://{site.name}")

    async def stop_server(self):
        """停止Webhook服务器"""
        if self.server:
            await self.server.cleanup()
            self.server = None
            self.logger.info("Webhook服务器已停止")

    async def start(self):
        """启动适配器"""
        if self.config.get("server"):
            await self.start_server()

    async def shutdown(self):
        """关闭适配器"""
        await self.stop_server()
        if self.session:
            await self.session.close()
            self.session = None
        self.logger.info("云湖适配器已关闭")

    async def call_api(self, endpoint: str, **params) -> Any:
        """调用API"""
        return await self._net_request("POST", endpoint, params)