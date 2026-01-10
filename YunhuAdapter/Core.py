import asyncio
import aiohttp
import io
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import filetype
from ErisPulse import sdk
from ErisPulse.Core import router

@dataclass
class YunhuBotConfig:
    """云湖机器人账户配置"""
    bot_id: str  # 机器人ID（必填）
    token: str  # 机器人token
    webhook_path: str = "/webhook"  # Webhook路径
    enabled: bool = True  # 是否启用
    name: str = ""  # 账户名称

class YunhuAdapter(sdk.BaseAdapter):
    """
    云湖平台适配器实现
    
    {!--< tips >!--}
    1. 使用统一适配器服务器系统管理Webhook路由
    2. 提供完整的消息发送DSL接口
    {!--< /tips >!--}
    """
    
    class Send(sdk.BaseAdapter.Send):
        """
        消息发送DSL实现
        
        {!--< tips >!--}
        1. 支持文本、富文本、文件等多种消息类型
        2. 支持批量发送和消息编辑
        3. 内置文件类型自动检测
        {!--< /tips >!--}
        """
        
        def Text(self, text: str, buttons: List = None, parent_id: str = ""):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    raise ValueError("text 必须可转换为字符串")

            endpoint = "/bot/batch_send" if isinstance(self._target_id, list) else "/bot/send"
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    recvIds=self._target_id if isinstance(self._target_id, list) else None,
                    recvId=None if isinstance(self._target_id, list) else self._target_id,
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

            endpoint = "/bot/batch_send" if isinstance(self._target_id, list) else "/bot/send"
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    recvIds=self._target_id if isinstance(self._target_id, list) else None,
                    recvId=None if isinstance(self._target_id, list) else self._target_id,
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

            endpoint = "/bot/batch_send" if isinstance(self._target_id, list) else "/bot/send"
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    recvIds=self._target_id if isinstance(self._target_id, list) else None,
                    recvId=None if isinstance(self._target_id, list) else self._target_id,
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
            endpoint = "/bot/board" if scope == "local" else "/bot/board-all"
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    chatId=self._target_id if scope == "local" else None,
                    chatType=self._target_type if scope == "local" else None,
                    contentType=kwargs.get("content_type", "text"),
                    content=content,
                    memberId=kwargs.get("member_id", None),
                    expireTime=kwargs.get("expire_time", 0)
                )
            )

        def DismissBoard(self, scope: str, **kwargs):
            endpoint = "/bot/board-dismiss" if scope == "local" else "/bot/board-all-dismiss"
            return asyncio.create_task(
                self._adapter.call_api(
                    endpoint=endpoint,
                    chatId=kwargs.get("chat_id") if scope == "local" else None,
                    chatType=kwargs.get("chat_type") if scope == "local" else None,
                    memberId=kwargs.get("member_id", "")
                )
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
            # 确定使用的bot
            bot_name = self._account_id
            bot = None
            if bot_name and bot_name in self._adapter.bots:
                bot = self._adapter.bots[bot_name]
                if not bot.enabled:
                    raise ValueError(f"Bot {bot_name} 已禁用")
            else:
                # 使用第一个启用的bot
                enabled_bots = [b for b in self._adapter.bots.values() if b.enabled]
                if not enabled_bots:
                    raise ValueError("没有配置任何启用的机器人")
                bot = enabled_bots[0]
                bot_name = next((name for name, b in self._adapter.bots.items() if b == bot), "")
            
            url = f"{self._adapter.base_url}{upload_endpoint}?token={bot.token}"
            
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
                    
                    # 检测Office文档
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
        self.adapter = sdk.adapter

        # 加载多bot配置
        self.bots: Dict[str, YunhuBotConfig] = self._load_bots_config()
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = "https://chat-go.jwzhd.com/open-apis/v1"
        
        self.convert = self._setup_coverter()

    def _setup_coverter(self):
        from .Converter import YunhuConverter
        convert = YunhuConverter()
        return convert.convert

    def _load_bots_config(self) -> Dict[str, YunhuBotConfig]:
        """加载多bot配置"""
        bots = {}
        
        # 检查新格式的bot配置
        bot_configs = self.sdk.config.getConfig("Yunhu_Adapter.bots", {})
        
        if not bot_configs:
            # 检查旧配置格式，进行兼容性处理
            old_config = self.sdk.config.getConfig("Yunhu_Adapter")
            if old_config and "token" in old_config:
                self.logger.warning("检测到旧格式配置，正在迁移到新格式...")
                self.logger.warning("旧配置已兼容，但建议迁移到新配置格式以获得更好的多bot支持。")
                self.logger.warning("迁移方法：将现有配置移动到 Yunhu_Adapter.bots.default 下")
                
                # 临时使用旧配置，创建默认bot
                server_config = old_config.get("server", {})
                temp_config = {
                    "default": {
                        "bot_id": "default",  # 默认bot_id，用户需修改
                        "token": old_config.get("token", ""),
                        "webhook_path": server_config.get("path", "/webhook"),
                        "enabled": True
                    }
                }
                bot_configs = temp_config

                self.logger.warning("已临时加载旧配置为默认bot，请尽快迁移到新格式并设置正确的bot_id")
                
            else:
                # 创建默认bot配置
                self.logger.info("未找到配置文件，创建默认bot配置")
                default_config = {
                    "default": {
                        "bot_id": "default",  # 用户需修改为实际的机器人ID
                        "token": "",
                        "webhook_path": "/webhook",
                        "enabled": True
                    }
                }
                
                try:
                    self.sdk.config.setConfig("Yunhu_Adapter.bots", default_config)
                    bot_configs = default_config
                except Exception as e:
                    self.logger.error(f"保存默认bot配置失败: {str(e)}")
                    # 即使保存失败也使用内存中的配置
                    bot_configs = default_config

        # 创建bot配置对象
        for bot_name, config in bot_configs.items():
            # 检查必填字段
            if "bot_id" not in config or not config["bot_id"]:
                self.logger.error(f"Bot {bot_name} 缺少bot_id配置，已跳过")
                continue
            
            if "token" not in config:
                self.logger.error(f"Bot {bot_name} 缺少token配置，已跳过")
                continue
            
            # 使用内置默认值
            merged_config = {
                "bot_id": config["bot_id"],
                "token": config.get("token", ""),
                "webhook_path": config.get("webhook_path", "/webhook"),
                "enabled": config.get("enabled", True),
                "name": bot_name
            }
            
            bots[bot_name] = YunhuBotConfig(**merged_config)
        
        self.logger.info(f"云湖适配器初始化完成，共加载 {len(bots)} 个机器人")
        return bots
    
    async def _net_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None, bot_token: str = None) -> Dict:
        """网络请求基础方法"""
        # 确定使用的token
        token = bot_token if bot_token else ""
        url = f"{self.base_url}{endpoint}?token={token}"
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
        """
        发送流式消息并返回标准 OneBot12 响应格式
        """
        # 确定使用的bot
        bot_name = kwargs.get("_account_id")
        if bot_name and bot_name in self.bots:
            bot = self.bots[bot_name]
            if not bot.enabled:
                raise ValueError(f"Bot {bot_name} 已禁用")
            bot_token = bot.token
        else:
            # 使用第一个启用的bot
            enabled_bots = [b for b in self.bots.values() if b.enabled]
            if not enabled_bots:
                raise ValueError("没有配置任何启用的机器人")
            bot = enabled_bots[0]
            bot_token = bot.token
            bot_name = list(self.bots.keys())[0]

        endpoint = "/bot/send-stream"
        params = {
            "recvId": target_id,
            "recvType": conversation_type,
            "contentType": content_type
        }
        if "parent_id" in kwargs:
            params["parentId"] = kwargs["parent_id"]
        url = f"{self.base_url}{endpoint}?token={bot_token}"
        query_params = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}&{query_params}"
        self.logger.debug(f"Bot {bot_name} 准备发送流式消息到 {target_id}，会话类型: {conversation_type}, 内容类型: {content_type}")
        if not self.session:
            self.session = aiohttp.ClientSession()
        headers = {"Content-Type": "text/plain"}
        async with self.session.post(full_url, headers=headers, data=content_generator) as response:
            raw_response = await response.json()
            
            # 标准化为 OneBot12 响应格式
            standardized = {
                "status": "ok" if raw_response.get("code") == 1 else "failed",
                "retcode": 0 if raw_response.get("code") == 1 else 34000 + (raw_response.get("code") or 0),
                "data": raw_response.get("data"),
                "message": raw_response.get("msg", ""),
                "yunhu_raw": raw_response,
                "self": {"user_id": bot.bot_id}  # 使用bot_id标识机器人账号
            }
            
            # 如果成功，提取消息ID
            if raw_response.get("code") == 1:
                data = raw_response.get("data", {})
                standardized["message_id"] = (
                    data.get("messageInfo", {}).get("msgId", "") 
                    if "messageInfo" in data 
                    else data.get("msgId", "")
                )
            else:
                standardized["message_id"] = ""
                
            if "echo" in kwargs:
                standardized["echo"] = kwargs["echo"]
                
            return standardized

    async def call_api(self, endpoint: str, _account_id: str = None, **params):
        """
        调用云湖API
        
        :param endpoint: API端点
        :param _account_id: 指定使用的机器人账户名称
        :param params: 其他API参数
        :return: 标准化的响应
        """
        # 确定使用的bot
        if _account_id and _account_id in self.bots:
            bot = self.bots[_account_id]
            if not bot.enabled:
                raise ValueError(f"Bot {_account_id} 已禁用")
        else:
            # 使用第一个启用的bot
            enabled_bots = [b for b in self.bots.values() if b.enabled]
            if not enabled_bots:
                raise ValueError("没有配置任何启用的机器人")
            bot = enabled_bots[0]
            _account_id = next((name for name, b in self.bots.items() if b == bot), "")
        
        self.logger.debug(f"Bot {_account_id} 调用API:{endpoint} 参数:{params}")
        
        raw_response = await self._net_request("POST", endpoint, params, bot_token=bot.token)
        
        is_batch = "batch" in endpoint or isinstance(params.get('recvIds'), list)
        
        standardized = {
            "status": "ok" if raw_response.get("code") == 1 else "failed",
            "retcode": 0 if raw_response.get("code") == 1 else 34000 + (raw_response.get("code") or 0),
            "data": raw_response.get("data"),
            "message": raw_response.get("msg", ""),
            "yunhu_raw": raw_response,
            "self": {"user_id": bot.bot_id}  # 使用bot_id标识机器人账号
        }
        
        if raw_response.get("code") == 1:
            if is_batch:
                standardized["message_id"] = [
                    msg.get("msgId", "") 
                    for msg in raw_response.get("data", {}).get("successList", []) 
                    if isinstance(msg, dict) and msg.get("msgId")
                ] if "successList" in raw_response.get("data", {}) else []
            else:
                data = raw_response.get("data", {})
                standardized["message_id"] = (
                    data.get("messageInfo", {}).get("msgId", "") 
                    if "messageInfo" in data 
                    else data.get("msgId", "")
                )
        else:
            standardized["message_id"] = [] if is_batch else ""
        
        if "echo" in params:
            standardized["echo"] = params["echo"]
        
        return standardized
    
    async def _process_webhook_event(self, data: Dict, bot_name: str = None):
        """处理webhook事件"""
        try:
            if not isinstance(data, dict):
                raise ValueError("事件数据必须是字典类型")

            if "header" not in data or "eventType" not in data["header"]:
                raise ValueError("无效的事件数据结构")
            
            if hasattr(self.adapter, "emit"):
                # 获取对应的bot配置
                bot = None
                if bot_name and bot_name in self.bots:
                    bot = self.bots[bot_name]
                
                onebot_event = self.convert(data, bot.bot_id if bot else None)
                self.logger.debug(f"Bot {bot_name} OneBot12事件数据: {json.dumps(onebot_event, ensure_ascii=False)}")
                if onebot_event:
                    await self.adapter.emit(onebot_event)

        except Exception as e:
            self.logger.error(f"Bot {bot_name} 处理事件错误: {str(e)}")
            self.logger.debug(f"原始事件数据: {json.dumps(data, ensure_ascii=False)}")

    async def register_webhook(self):
        """为每个启用的bot注册webhook路由"""
        enabled_bots = {name: bot for name, bot in self.bots.items() if bot.enabled}
        
        if not enabled_bots:
            self.logger.warning("没有配置任何启用的机器人，将不会注册webhook")
            return
        
        # 为每个bot注册独立的webhook路由
        for bot_name, bot in enabled_bots.items():
            path = bot.webhook_path
            
            # 创建特定bot的处理器
            def make_webhook_handler(bot_name):
                async def webhook_handler(data: Dict):
                    return await self._process_webhook_event(data, bot_name)
                return webhook_handler
            
            # 注册路由（使用bot_name作为模块名以避免冲突）
            router.register_http_route(
                f"yunhu_{bot_name}",  # 使用bot特定的路由名称
                path,
                make_webhook_handler(bot_name),
                methods=["POST"]
            )
            
            self.logger.info(f"已注册Bot {bot_name} (ID: {bot.bot_id}) 的Webhook路由: {path}")
        
    async def start(self):
        """启动云湖适配器"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        enabled_bots = [name for name, bot in self.bots.items() if bot.enabled]
        
        if enabled_bots:
            await self.register_webhook()
            self.logger.info(f"云湖适配器已启动，启用的Bot: {', '.join(enabled_bots)}")
        else:
            self.logger.warning("没有配置任何启用的机器人，适配器启动但无可用Bot")

    async def shutdown(self):
        """关闭云湖适配器"""
        if self.session:
            await self.session.close()
            self.session = None
        self.logger.info("云湖适配器已关闭")
