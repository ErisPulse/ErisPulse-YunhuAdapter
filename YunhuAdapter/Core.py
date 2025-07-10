import asyncio
import aiohttp
import uuid
import time
import io
from urllib.parse import quote
import json
from aiohttp import web
from typing import Dict, List, Optional, Any, AsyncGenerator
import filetype
from ErisPulse import sdk
from .Converter import Converter

class Main:
    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger

class YunhuAdapter(sdk.BaseAdapter):
    class Send(sdk.BaseAdapter.Send):
        def Text(self, text: str, buttons: List = None, parent_id: str = ""):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    raise ValueError("text 必须可转换为字符串")

            if isinstance(self._target_id, list):
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/batch_send",
                        recvIds=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": text, "buttons": buttons},
                        parentId=parent_id
                    )
                )
            else:
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

        def Html(self, html: str, buttons: List = None, parent_id: str = ""):
            if not isinstance(html, str):
                try:
                    html = str(html)
                except Exception:
                    raise ValueError("html 必须可转换为字符串")

            if isinstance(self._target_id, list):
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/batch_send",
                        recvIds=self._target_id,
                        recvType=self._target_type,
                        contentType="html",
                        content={"text": html, "buttons": buttons},
                        parentId=parent_id
                    )
                )
            else:
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/send",
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="html",
                        content={"text": html, "buttons": buttons},
                        parentId=parent_id
                    )
                )

        def Markdown(self, markdown: str, buttons: List = None, parent_id: str = ""):
            if not isinstance(markdown, str):
                try:
                    markdown = str(markdown)
                except Exception:
                    raise ValueError("markdown 必须可转换为字符串")

            if isinstance(self._target_id, list):
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/batch_send",
                        recvIds=self._target_id,
                        recvType=self._target_type,
                        contentType="markdown",
                        content={"text": markdown, "buttons": buttons},
                        parentId=parent_id
                    )
                )
            else:
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/send",
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="markdown",
                        content={"text": markdown, "buttons": buttons},
                        parentId=parent_id
                    )
                )

        def Image(self, file, buttons: List = None, parent_id: str = "", stream: bool = False, filename: str = None):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/image/upload",
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type="image",
                    buttons=buttons,
                    parent_id=parent_id,
                    stream=stream
                )
            )

        def Video(self, file, buttons: List = None, parent_id: str = "", stream: bool = False, filename: str = None):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/video/upload",
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type="video",
                    buttons=buttons,
                    parent_id=parent_id,
                    stream=stream
                )
            )

        def File(self, file, buttons: List = None, parent_id: str = "", stream: bool = False, filename: str = None):
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/file/upload",
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type="file",
                    buttons=buttons,
                    parent_id=parent_id,
                    stream=stream
                )
            )

        def Batch(self, target_ids: List[str], message: Any, content_type: str = "text", **kwargs):
            if content_type in ["text", "html", "markdown"]:
                self.logger.debug("批量发送文本/富文本消息时, 更推荐的方法是使用" \
                " Send.To('user'/'group', user_ids: list/group_ids: list).Text/Html/Markdown(message, buttons = None, parent_id = None)")
                
            if not isinstance(message, str):
                try:
                    message = str(message)
                except Exception:
                    raise ValueError("message 必须可转换为字符串")

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

        def Edit(self, msg_id: str, text: Any, content_type: str = "text", buttons: List = None):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    raise ValueError("text 必须可转换为字符串")

            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint="/bot/edit",
                    msgId=msg_id,
                    recvId=self._target_id,
                    recvType=self._target_type,
                    contentType=content_type,
                    content={"text": text, "buttons": buttons if buttons is not None else []},
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
                        chatId=self._target_id,
                        chatType=self._target_type,
                        contentType=kwargs.get("content_type", "text"),
                        content=content,
                        memberId=kwargs.get("member_id", None),
                        expireTime=kwargs.get("expire_time", 0)
                    )
                )
            else:
                return asyncio.create_task(
                    self._adapter.call_api(
                        endpoint="/bot/board-all",
                        contentType=kwargs.get("content_type", "text"),
                        content=content,
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

        async def CheckExist(self, message_id: str):
            endpoint = "/bot/messages"
            params = {
                "chat-id": self._target_id,
                "chat-type": self._target_type,
                "message-id": message_id,
                "before": 0,
                "after": 0
            }
            url = f"{self._adapter.base_url}{endpoint}?token={self._adapter.yhToken}"
            async with self._adapter.session.get(url, params=params) as response:
                data = await response.json()
                if data.get("code") != 1:
                    self.logger.warning(f"云湖API返回异常: {data}")
                    return False
                msg_list = data.get("data", {}).get("list", [])
                return any(msg["msgId"] == message_id for msg in msg_list)
        def _detect_document(self, sample_bytes):
            office_signatures = {
                b'PK\x03\x04\x14\x00\x06\x00': 'docx',  # DOCX
                b'PK\x03\x04\x14\x00\x00\x08': 'xlsx',  # XLSX
                b'PK\x03\x04\x14\x00\x00\x06': 'pptx'   # PPTX
            }
            
            for signature, extension in office_signatures.items():
                if sample_bytes.startswith(signature):
                    return extension
            return None

        async def _upload_file_and_call_api(self, upload_endpoint, file_name, file, endpoint, content_type, **kwargs):
            url = f"{self._adapter.base_url}{upload_endpoint}?token={self._adapter.yhToken}"
            
            # 使用不编码字段名的FormData
            data = aiohttp.FormData(quote_fields=False)
            
            if kwargs.get('stream', False):
                if not hasattr(file, '__aiter__'):
                    raise ValueError("stream=True时，file参数必须是异步生成器")
                
                temp_file = io.BytesIO()
                async for chunk in file:
                    temp_file.write(chunk)
                temp_file.seek(0)
                file_data = temp_file
            else:
                file_data = io.BytesIO(file) if isinstance(file, bytes) else file

            file_info = None
            file_extension = None
            
            try:
                if hasattr(file_data, 'seek'):
                    file_data.seek(0)
                    sample = file_data.read(1024)
                    file_data.seek(0)
                    
                    file_info = filetype.guess(sample)
                    
                    # 让我看看是哪个伪装成 zip 的文档
                    if file_info and file_info.mime == 'application/zip':
                        office_extension = self._detect_document(sample)
                        if office_extension:
                            file_extension = office_extension
                    elif file_info:
                        file_extension = file_info.extension
            except Exception as e:
                self._adapter.logger.warning(f"文件类型检测失败: {str(e)}")

            # 确定上传文件名
            if file_name is None:
                if file_extension:
                    upload_filename = f"{content_type}.{file_extension}"
                else:
                    upload_filename = f"{content_type}.bin"
            else:
                if file_extension and '.' not in file_name:
                    upload_filename = f"{file_name}.{file_extension}"
                else:
                    upload_filename = file_name

            sdk.logger.debug(f"上传文件: {upload_filename}")
            data.add_field(
                name=content_type,
                value=file_data,
                filename=upload_filename,
            )

            # 上传文件
            async with self._adapter.session.post(url, data=data) as response:
                upload_res = await response.json()
                self._adapter.logger.debug(f"上传响应: {upload_res}")

                if upload_res.get("code") != 1:
                    error_msg = upload_res.get("msg", "未知错误")
                    raise ValueError(f"文件上传失败: {upload_res}")

                key_map = {
                    "image": "imageKey",
                    "video": "videoKey",
                    "file": "fileKey"
                }
                
                key_name = key_map.get(content_type, "fileKey")
                if "data" not in upload_res or key_name not in upload_res["data"]:
                    raise ValueError("上传API返回的数据格式不正确")

            # 构造API调用负载
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
        super().__init__()
        self.sdk = sdk
        self.logger = sdk.logger
        self.config = self._load_config()
        self.yhToken = self.config.get("token", "")
        self.session: Optional[aiohttp.ClientSession] = None
        self.server: Optional[web.AppRunner] = None
        self.base_url = "https://chat-go.jwzhd.com/open-apis/v1"
        self._setup_event_mapping()
        
        # 事件接收模式配置
        self.mode = self.config.get("mode", "server")  # server或polling
        self.polling_config = self.config.get("polling", {})
        self.polling_task: Optional[asyncio.Task] = None
        self.last_event_id = ""

    def _load_config(self) -> Dict:
        config = self.sdk.env.get("YunhuAdapter", {})
        if not config:
            self.logger.warning("""云湖配置缺失，请在env.py中添加配置
sdk.env.set("YunhuAdapter", {
    "token": "",
    "mode": "server",  # server / polling
    "server": {
        "host": "0.0.0.0",
        "port": 25888,
        "path": "/yunhu/webhook"
    },
    
    "polling": {
        "url": "https://sse.bot.anran.xyz/sse",
    }
})""")
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
    async def _net_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        url = f"{self.base_url}{endpoint}?token={self.yhToken}"
        if not self.session:
            self.session = aiohttp.ClientSession()

        json_data = json.dumps(data) if data else None
        headers = {"Content-Type": "application/json; charset=utf-8"}

        self.logger.debug(f"[{endpoint}]|[{method}] 请求数据: {json_data} | 参数: {params}")

        async with self.session.request(
            method,
            url,
            data=json_data,
            params=params,
            headers=headers
        ) as response:
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                result = await response.json()
                self.logger.debug(f"[{endpoint}]|[{method}] 响应数据: {result}")
                return result
            else:
                text = await response.text()
                self.logger.warning(f"[{endpoint}] 非JSON响应，原始内容: {text[:500]}")
                return {"error": "Invalid content type", "content_type": content_type, "status": response.status, "raw": text}

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
            # 添加原始数据日志
            raw_data = await request.text()
            self.logger.debug(f"收到原始WebHook数据: {raw_data}")
            
            data = await request.json()
            self.logger.debug(f"解析后的WebHook数据: {json.dumps(data, indent=2)}")
            
            await self._process_webhook_event(data)
            return web.Response(text="OK", status=200)
        except Exception as e:
            self.logger.error(f"Webhook处理错误: {str(e)}", exc_info=True)
            return web.Response(text=f"ERROR: {str(e)}", status=500)
    async def _convert_to_onebot12(self, data: Dict) -> Optional[Dict]:
        header = data.get("header", {})
        event_data = data.get("event", {})
        convert = Converter()
        return convert.convert(event_data)
    
    async def _process_webhook_event(self, data: Dict):
        try:
            if not isinstance(data, dict):
                raise ValueError("事件数据必须是字典类型")

            if "header" not in data or "eventType" not in data["header"]:
                raise ValueError("无效的事件数据结构")

            event_type = data["header"]["eventType"]
            mapped_type = self.event_map.get(event_type, "unknown")

            self.logger.debug(f"事件 {event_type} -> {mapped_type}")
            
            await self.emit(mapped_type, data)
            
            if hasattr(self, "emit_onebot12"):
                onebot_event = await self._convert_to_onebot12(data)
                if onebot_event:
                    await self.emit_onebot12(onebot_event.get("type", "unknown"), onebot_event)

        except Exception as e:
            self.logger.error(f"处理事件错误: {str(e)}")
            self.logger.debug(f"原始事件数据: {json.dumps(data, ensure_ascii=False)}")

    async def _run_polling_client(self):
        if not self.polling_config.get("url"):
            self.logger.error("未配置SSE URL，无法启动轮询模式")
            return

        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }

        if self.last_event_id:
            headers["Last-Event-ID"] = self.last_event_id

        while True:
            try:
                async with self.session.get(
                    self.polling_config["url"],
                    headers=headers,
                    timeout=None
                ) as response:
                    if response.status != 200:
                        raise Exception(f"SSE连接失败，状态码: {response.status}")

                    current_event = None
                    buffer = ""

                    async for chunk in response.content:
                        buffer += chunk.decode('utf-8')
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            self.logger.debug(f"SSE数据: {line}")
                            if line.startswith("event:"):
                                current_event = line[6:].strip()
                            elif line.startswith("data:"):
                                try:
                                    data = json.loads(line[5:])
                                    if current_event == "message":
                                        await self._process_message_event(data)
                                    elif current_event == "system":
                                        self._process_system_event(data)
                                except json.JSONDecodeError as e:
                                    self.logger.error(f"JSON解析错误: {str(e)}")
                            elif line.startswith("id:"):
                                self.last_event_id = line[3:].strip()

            except asyncio.CancelledError:
                self.logger.info("SSE客户端被取消")
                break
            except Exception as e:
                self.logger.error(f"SSE连接错误: {str(e)}，详细异常：", exc_info=True)

    async def _process_message_event(self, data: Dict):
        try:
            if not isinstance(data, dict):
                raise ValueError("消息数据必须是字典类型")

            if isinstance(data.get("data"), str):
                try:
                    data["data"] = json.loads(data["data"])
                except json.JSONDecodeError:
                    pass
            if isinstance(data.get("data"), dict) and "header" in data["data"]:
                await self._process_webhook_event(data["data"])
            else:
                await self.emit("message", data)

        except Exception as e:
            self.logger.debug(f"原始消息数据: {json.dumps(data, ensure_ascii=False)}")

    def _process_system_event(self, data: Dict):
        try:
            event_type = data.get("type")
            if event_type == "init":
                self.logger.info(f"Yunhu-SSE初始化完成，状态: {data.get('status')}")
            elif event_type == "heartbeat":
                self.logger.debug(f"[SSE] heartbeat | {data.get('timestamp')}")
                pass
            else:
                self.logger.warning(f"未知系统事件: {event_type}")
        except Exception as e:
            self.logger.error(f"处理系统事件错误: {str(e)}")

    async def start_server(self):
        if not self.config.get("server"):
            self.logger.warning("Webhook服务器未配置，将不会启动")
            return

        server_config = self.config["server"]
        app = web.Application()
        app.router.add_post(server_config.get("path", "/"), self._handle_webhook)

        self.server = web.AppRunner(app)
        await self.server.setup()

        site = web.TCPSite(
            self.server,
            server_config.get("host", "127.0.0.1"),
            server_config.get("port", 8080)
        )
        await site.start()
        self.logger.info(f"Webhook服务器已启动: {site.name}{server_config.get('path')}")

    async def stop_server(self):
        if self.server:
            await self.server.cleanup()
            self.server = None
            self.logger.info("Webhook服务器已停止")

    async def start(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

        if self.mode == "server":
            await self.start_server()
        elif self.mode == "polling":
            if self.polling_config.get("url"):
                self.logger.info("启动SSE轮询客户端")
                self.polling_task = asyncio.create_task(self._run_polling_client())
            else:
                self.logger.error("polling模式需要配置polling.url参数")
        else:
            self.logger.error(f"未知的模式配置: {self.mode}")

    async def shutdown(self):
        await self.stop_server()
        if self.polling_task and not self.polling_task.done():
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()
            self.session = None
        self.logger.info("云湖适配器已关闭")