import asyncio
import aiohttp
from aiohttp import web
from typing import Dict, List, Optional, Any, Callable
from ErisPulse import sdk

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger

    def register_adapters(self):
        self.logger.debug("注册云湖适配器")
        return {
            "Yunhu": YunhuAdapter
        }

class YunhuAdapter(sdk.BaseAdapter):
    class Send(sdk.adapter.SendDSL):
        def Text(self, text: str, buttons: List = None, parent_id: str = ""):
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/send",
                    recvId=self._target_id,
                    recvType=self._target_type,
                    contentType="text",
                    content={"text": text, "buttons": buttons},
                    parentId=parent_id
                )
            )

        def Image(self, file: bytes, buttons: List = None, parent_id: str = ""):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/image/upload",
                    field_name="image",
                    file=file,
                    endpoint="/bot/send",
                    content_type="image",
                    buttons=buttons,
                    parent_id=parent_id
                )
            )

        def Video(self, file: bytes, buttons: List = None, parent_id: str = ""):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/video/upload",
                    field_name="video",
                    file=file,
                    endpoint="/bot/send",
                    content_type="video",
                    buttons=buttons,
                    parent_id=parent_id
                )
            )

        def File(self, file: bytes, buttons: List = None, parent_id: str = ""):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/file/upload",
                    field_name="file",
                    file=file,
                    endpoint="/bot/send",
                    content_type="file",
                    buttons=buttons,
                    parent_id=parent_id
                )
            )

        def Batch(self, target_ids: List[str], message: Any, content_type: str = "text", **kwargs):
            content = {"text": message} if isinstance(message, str) else {}
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/batch_send",
                    recvIds=target_ids,
                    recvType=self._target_type,
                    contentType=content_type,
                    content=content,
                    **kwargs
                )
            )

        def Edit(self, msg_id: str, text: str, buttons: List = None):
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/edit",
                    msgId=msg_id,
                    recvId=self._target_id,
                    recvType=self._target_type,
                    contentType="text",
                    content={"text": text, "buttons": buttons}
                )
            )

        def Recall(self, msg_id: str):
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/recall",
                    msgId=msg_id,
                    chatId=self._target_id,
                    chatType=self._target_type
                )
            )

        def Board(self, scope: str, content: str, **kwargs):
            if scope == "local":
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/board",
                        chatId=kwargs["chat_id"],
                        chatType=kwargs["chat_type"],
                        contentType=kwargs.get("content_type", "text"),
                        content={"text": content},
                        memberId=kwargs.get("member_id", ""),
                        expireTime=kwargs.get("expire_time", 0)
                    )
                )
            else:
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/board-all",
                        contentType=kwargs.get("content_type", "text"),
                        content={"text": content},
                        expireTime=kwargs.get("expire_time", 0)
                    )
                )

        def DismissBoard(self, scope: str, **kwargs):
            if scope == "local":
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/board-dismiss",
                        chatId=kwargs["chat_id"],
                        chatType=kwargs["chat_type"],
                        memberId=kwargs.get("member_id", "")
                    )
                )
            else:
                return asyncio.create_task(
                    self._adapter.call_api(endpoint="/bot/board-all-dismiss")
                )

        def Stream(self, content_type: str, content_generator, **kwargs):
            return asyncio.create_task(
                self._adapter.send_stream(
                    conversation_type=self._target_type,
                    target_id=self._target_id,
                    content_type=content_type,
                    content_generator=content_generator,
                    **kwargs
                )
            )

        async def _upload_file_and_call_api(self, upload_endpoint, field_name, file, endpoint, content_type, **kwargs):
            url = f"{self._adapter.base_url}{upload_endpoint}?token={self._adapter.yhToken}"
            data = aiohttp.FormData()
            data.add_field(
                field_name,
                file,
                filename=f"file.{field_name}",
                content_type="application/octet-stream"
            )

            async with self._adapter.session.post(url, data=data) as response:
                upload_res = await response.json()

            key_map = {
                "image": "imageKey",
                "video": "videoKey",
                "file": "fileKey"
            }
            key_name = key_map.get(field_name)

            payload = {
                "recvId": self._target_id,
                "recvType": self._target_type,
                "contentType": content_type,
                "content": {key_name: upload_res["data"][key_name]},
                "parentId": kwargs.get("parent_id", "")
            }

            if "buttons" in kwargs:
                payload["content"]["buttons"] = kwargs["buttons"]

            return await self._adapter.call_api(endpoint, **payload)

    def __init__(self, sdk):
        super().__init__(sdk)
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
        self.logger.debug(f"准备发送流式消息到 {target_id}，会话类型: {conversation_type}, 内容类型: {content_type}")
        if not self.session:
            self.session = aiohttp.ClientSession()
        headers = {"Content-Type": "text/plain"}
        async with self.session.post(full_url, headers=headers, data=content_generator) as response:
            return await response.json()

    async def call_api(self, endpoint: str, **params):
        self.logger.debug(f"调用API:{endpoint}")
        return await self._net_request("POST", endpoint, params)

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
