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
        4. 支持链式修饰（At、Reply、Buttons）
        {!--< /tips >!--}
        """
        
        # 方法名映射表（全小写 -> 实际方法名）
        _METHOD_MAP = {
            # 消息发送方法
            "text": "Text",
            "html": "Html",
            "markdown": "Markdown",
            "image": "Image",
            "video": "Video",
            "file": "File",
            
            # 批量和其他方法
            "batch": "Batch",
            "edit": "Edit",
            "recall": "Recall",
            "board": "Board",
            "dismissboard": "DismissBoard",
            "stream": "Stream",
            
            # 原始消息和转换
            "raw_ob12": "Raw_ob12",
            
            # 链式修饰方法
            "at": "At",
            "reply": "Reply",
            "buttons": "Buttons",
        }
        
        def __init__(self, adapter, target_type=None, target_id=None, account_id=None):
            super().__init__(adapter, target_type, target_id, account_id)
            self._at_user_ids = []       # @的用户列表
            self._reply_message_id = None # 回复的消息ID (parent_id)
            self._buttons = None         # 按钮数据
        
        def __getattr__(self, name):
            """
            处理未定义的发送方法（支持大小写不敏感）
            
            当调用不存在的消息类型方法时：
            1. 通过映射表查找对应的方法
            2. 如果找到则调用该方法
            3. 如果找不到，则发送文本提示不支持
            """
            name_lower = name.lower()
            
            # 查找映射
            if name_lower in self._METHOD_MAP:
                actual_method_name = self._METHOD_MAP[name_lower]
                return getattr(self, actual_method_name)
            
            # 方法不存在，返回文本提示
            def unsupported_method(*args, **kwargs):
                params_info = []
                for i, arg in enumerate(args):
                    if isinstance(arg, bytes):
                        params_info.append(f"args[{i}]: <bytes: {len(arg)} bytes>")
                    else:
                        params_info.append(f"args[{i}]: {repr(arg)[:100]}")
                
                for k, v in kwargs.items():
                    if isinstance(v, bytes):
                        params_info.append(f"{k}: <bytes: {len(v)} bytes>")
                    else:
                        params_info.append(f"{k}: {repr(v)[:100]}")
                
                params_str = ", ".join(params_info)
                error_msg = f"[不支持的发送类型] 方法名: {name}, 参数: [{params_str}]"
                
                return self.Text(error_msg)
            
            return unsupported_method
        
        def At(self, user_id: str) -> 'Send':
            """
            @用户（可多次调用）
            
            云湖不支持真正的艾特，使用 @+用户ID 格式
            
            :param user_id: 用户ID
            :return: self，支持链式调用
            """
            self._at_user_ids.append(str(user_id))
            return self
        
        def Reply(self, message_id: str) -> 'Send':
            """
            回复消息
            
            :param message_id: 消息ID
            :return: self，支持链式调用
            """
            self._reply_message_id = str(message_id)
            return self
        
        def Buttons(self, buttons: List) -> 'Send':
            """
            设置按钮（云湖特有）
            
            :param buttons: 按钮列表
            :return: self，支持链式调用
            """
            self._buttons = buttons
            return self
        
        def _build_content_with_modifiers(self, text: str, content_type: str) -> Dict:
            """
            构建包含链式修饰的内容
            
            :param text: 文本内容
            :param content_type: 内容类型（text/html/markdown）
            :return: 构建好的内容字典
            """
            result = {"text": text}
            
            # 处理@用户
            if self._at_user_ids:
                at_text = " ".join([f"@{uid}" for uid in self._at_user_ids])
                result["text"] = at_text + " " + result["text"]
            
            # 处理按钮
            if self._buttons is not None:
                result["buttons"] = self._buttons
            
            return result
        
        def _get_parent_id(self, param_parent_id: str = "") -> str:
            """
            获取parent_id，优先使用链式修饰，兼容参数方式
            
            :param param_parent_id: 方法参数中的parent_id
            :return: 实际使用的parent_id
            """
            return self._reply_message_id if self._reply_message_id is not None else param_parent_id
        
        def _get_buttons(self, param_buttons: List = None):
            """
            获取buttons，优先使用链式修饰，兼容参数方式
            
            :param param_buttons: 方法参数中的buttons
            :return: 实际使用的buttons
            """
            return self._buttons if self._buttons is not None else param_buttons
        
        def Raw_ob12(self, message, **kwargs):
            """
            发送原始 OneBot12 格式消息
            
            将 OneBot12 格式转换为云湖格式发送
            注意：云湖不支持组合消息，会将不同类型的消息段分别发送
            
            :param message: OneBot12 消息段或消息段数组
            :param kwargs: 额外参数
            :return: asyncio.Task
            """
            # 处理单条消息段的情况
            if isinstance(message, dict):
                message = [message]
            
            # 分组消息段，云湖不支持组合消息
            grouped_messages = self._group_ob12_messages(message)
            
            # 定义异步发送函数
            async def _send_grouped_messages():
                results = []
                for msg_group in grouped_messages:
                    # 调用对应的发送方法
                    result = await self._send_ob12_group(msg_group)
                    results.append(result)
                
                # 返回最后一个结果作为主结果
                return results[-1] if results else None
            
            return asyncio.create_task(_send_grouped_messages())
        
        def _group_ob12_messages(self, message: List[Dict]) -> List[List[Dict]]:
            """
            将 OneBot12 消息段数组分组，每组包含一个主要消息类型
            
            :param message: OneBot12 消息段数组
            :return: 分组后的消息段数组列表
            """
            groups = []
            current_group = []
            
            # 定义可以合并到文本组的消息类型
            text_mergeable_types = ["text", "mention"]
            
            for segment in message:
                seg_type = segment.get("type", "")
                
                # 回复消息可以附加到任何组
                if seg_type == "reply":
                    # 如果当前没有组，创建一个
                    if not current_group:
                        current_group.append(segment)
                    # 否则追加到当前组
                    else:
                        current_group.append(segment)
                    continue
                
                # 文本消息、@可以合并
                if seg_type in text_mergeable_types:
                    # 如果当前组是文本组或空组，添加进去
                    if not current_group or all(s.get("type") in text_mergeable_types or s.get("type") == "reply" for s in current_group):
                        current_group.append(segment)
                    else:
                        # 当前组不是文本组，先保存，再创建新组
                        if current_group:
                            groups.append(current_group)
                        current_group = [segment]
                
                # 其他消息类型（图片、视频、文件、markdown、html等）单独成组
                else:
                    # 先保存当前组
                    if current_group:
                        groups.append(current_group)
                    # 新建组
                    groups.append([segment])
                    current_group = []
            
            # 保存最后一组
            if current_group:
                groups.append(current_group)
            
            return groups
        
        async def _send_ob12_group(self, msg_group: List[Dict]) -> Dict:
            """
            发送一组消息段，调用对应的发送方法
            
            :param msg_group: 一组消息段
            :return: 发送结果
            """
            if not msg_group:
                return None
            
            # 获取第一个段来确定类型
            first_segment = msg_group[0]
            seg_type = first_segment.get("type", "")
            
            # 合并链式修饰到这组消息
            parent_id = self._reply_message_id
            buttons = self._buttons
            at_user_ids = self._at_user_ids.copy() if self._at_user_ids else []
            
            # 处理文本组（可能包含多个文本和@）
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
                
                # 添加链式修饰的@用户
                if at_user_ids:
                    at_text = " ".join([f"@{uid}" for uid in at_user_ids])
                    text_parts.insert(0, at_text)
                
                text = " ".join(text_parts) or " "
                
                # 调用 Text 方法
                return await self.Text(text, buttons=buttons, parent_id=parent_id)
            
            # 处理其他类型的消息
            seg_data = first_segment.get("data", {})
            
            # 图片
            if seg_type == "image":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self.Image(file_url, buttons=buttons, parent_id=parent_id)
            
            # 音频（云湖使用video类型）
            elif seg_type == "audio":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self.Video(file_url, buttons=buttons, parent_id=parent_id)
            
            # 视频
            elif seg_type == "video":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self.Video(file_url, buttons=buttons, parent_id=parent_id)
            
            # 文件
            elif seg_type == "file":
                file_url = seg_data.get("file") or seg_data.get("url", "")
                return await self.File(file_url, buttons=buttons, parent_id=parent_id)
            
            # Markdown
            elif seg_type == "markdown":
                markdown_text = seg_data.get("markdown", "")
                if buttons is None and "buttons" in seg_data:
                    buttons = seg_data["buttons"]
                return await self.Markdown(markdown_text, buttons=buttons, parent_id=parent_id)
            
            # HTML
            elif seg_type == "html":
                html_text = seg_data.get("html", "")
                return await self.Html(html_text, buttons=buttons, parent_id=parent_id)
            
            # 回复（单独一个reply的情况）
            elif seg_type == "reply":
                parent_id = seg_data.get("message_id", "")
                # 回复需要伴随消息内容，如果只有回复，发送空文本
                return await self.Text("", buttons=buttons, parent_id=parent_id)
            
            # 云湖特有消息段
            elif seg_type.startswith("yunhu_"):
                # 暂不支持，作为文本处理
                return await self.Text(str(seg_data), buttons=buttons, parent_id=parent_id)
            
            # 其他未知类型，作为文本处理
            else:
                return await self.Text(str(seg_data), buttons=buttons, parent_id=parent_id)
        
        def Text(self, text: str, buttons: List = None, parent_id: str = ""):
            """发送文本消息，支持链式修饰"""
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
                    content=self._build_content_with_modifiers(text, "text"),
                    parentId=self._get_parent_id(parent_id)
                )
            )

        def Html(self, html: str, buttons: List = None, parent_id: str = ""):
            """发送HTML消息，支持链式修饰"""
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
                    content=self._build_content_with_modifiers(html, "html"),
                    parentId=self._get_parent_id(parent_id)
                )
            )

        def Markdown(self, markdown: str, buttons: List = None, parent_id: str = ""):
            """发送Markdown消息，支持链式修饰"""
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
                    content=self._build_content_with_modifiers(markdown, "markdown"),
                    parentId=self._get_parent_id(parent_id)
                )
            )

        def Image(self, file, buttons: List = None, parent_id: str = "", stream: bool = False, filename: str = None):
            """发送图片消息，支持链式修饰"""
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/image/upload",
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type="image",
                    buttons=self._get_buttons(buttons),
                    parent_id=self._get_parent_id(parent_id),
                    stream=stream
                )
            )

        def Video(self, file, buttons: List = None, parent_id: str = "", stream: bool = False, filename: str = None):
            """发送视频消息，支持链式修饰"""
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/video/upload",
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type="video",
                    buttons=self._get_buttons(buttons),
                    parent_id=self._get_parent_id(parent_id),
                    stream=stream
                )
            )

        def File(self, file, buttons: List = None, parent_id: str = "", stream: bool = False, filename: str = None):
            """发送文件消息，支持链式修饰"""
            return asyncio.create_task(
                self._upload_file_and_call_api(
                    "/file/upload",
                    file_name=filename,
                    file=file,
                    endpoint="/bot/send",
                    content_type="file",
                    buttons=self._get_buttons(buttons),
                    parent_id=self._get_parent_id(parent_id),
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
            """
            撤回消息
            
            注意：云湖Recall必须使用To(target_type, target_id)指定目标
            
            :param msg_id: 要撤回的消息ID
            :return: asyncio.Task
            """
            # 验证To参数是否已设置
            if not self._target_id or not self._target_type:
                raise ValueError("Recall必须使用To(target_type, target_id)指定目标。例如: Send.To('group', '123').Recall('msg_id')")
            
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

        async def _download_file_from_url(self, url: str, max_size: int = 100 * 1024 * 1024) -> tuple[Optional[bytes], Optional[str]]:
            """
            从 URL 下载文件
            
            :param url: 文件URL
            :param max_size: 最大文件大小（字节），默认100MB
            :return: (文件内容, 文件名) 或 (None, None)
            """
            if not url:
                return None, None
            
            try:
                # 从URL中提取文件名
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(url)
                filename = unquote(parsed_url.path.split('/')[-1]) or "downloaded_file"
                
                self._adapter.logger.debug(f"开始下载文件: {url}")
                
                if not self._adapter.session:
                    self._adapter.session = aiohttp.ClientSession()
                
                async with self._adapter.session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    # 检查Content-Length
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        size = int(content_length)
                        if size > max_size:
                            self._adapter.logger.warning(f"文件过大: {size / 1024 / 1024:.2f}MB (限制: {max_size / 1024 / 1024:.0f}MB)")
                            return None, None
                    
                    # 使用io.BytesIO流式下载，避免一次性加载大文件到内存
                    file_buffer = io.BytesIO()
                    downloaded_size = 0
                    
                    async for chunk in response.content.iter_chunked(8192):  # 8KB chunks
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            self._adapter.logger.warning(f"下载文件过大: {downloaded_size / 1024 / 1024:.2f}MB (限制: {max_size / 1024 / 1024:.0f}MB)")
                            return None, None
                        file_buffer.write(chunk)
                    
                    file_buffer.seek(0)
                    file_data = file_buffer.read()
                    
                    self._adapter.logger.debug(f"文件下载完成: {len(file_data)} bytes, 文件名: {filename}")
                    return file_data, filename
                    
            except Exception as e:
                self._adapter.logger.error(f"下载文件失败: {url}, 错误: {str(e)}")
                return None, None

        async def _upload_file_and_call_api(self, upload_endpoint, file_name, file, endpoint, content_type, **kwargs):
            # 确定使用的bot
            bot_name = self._account_id
            bot = None

            # 智能判断 _account_id 是账户名还是 bot_id
            if bot_name and bot_name in self._adapter.bots:
                # _account_id 是账户名，直接使用
                bot = self._adapter.bots[bot_name]
                if not bot.enabled:
                    raise ValueError(f"Bot {bot_name} 已禁用")
            elif bot_name:
                # _account_id 是 bot_id，查找对应的账户
                for name, bot_config in self._adapter.bots.items():
                    if bot_config.bot_id == bot_name:
                        bot = bot_config
                        bot_name = name
                        break
                if bot and not bot.enabled:
                    raise ValueError(f"Bot {bot_name} (bot_id: {bot.bot_id}) 已禁用")
                if not bot:
                    self.logger.warning(f"找不到bot_id为 {bot_name} 的机器人，将使用默认bot")

            if not bot:
                # 使用第一个启用的bot
                enabled_bots = [b for b in self._adapter.bots.values() if b.enabled]
                if not enabled_bots:
                    raise ValueError("没有配置任何启用的机器人")
                bot = enabled_bots[0]
                bot_name = next((name for name, b in self._adapter.bots.items() if b == bot), "")
            
            # 处理URL类型文件
            if isinstance(file, str) and (file.startswith('http://') or file.startswith('https://')):
                self._adapter.logger.info(f"检测到URL，开始下载: {file}")
                file_data, downloaded_filename = await self._download_file_from_url(file)
                
                if file_data is None:
                    # 下载失败或文件过大，发送文本提示
                    error_msg = f"[文件发送失败] 无法发送文件: {file}\n原因: 文件过大(超过100MB)或下载失败"
                    return await self._adapter.call_api(
                        endpoint="/bot/send",
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": error_msg},
                        parentId=kwargs.get("parent_id", "")
                    )
                
                # 使用下载的文件名（如果未指定）
                if file_name is None and downloaded_filename:
                    file_name = downloaded_filename
                
                file = file_data
            
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

            self._adapter.logger.debug(f"Bot {bot_name} (bot_id: {bot.bot_id}) 上传文件: {upload_filename}")
            data.add_field(
                name=content_type,
                value=file_data,
                filename=upload_filename,
            )

            # 上传文件，增加超时时间
            timeout = aiohttp.ClientTimeout(total=600, connect=30)  # 10分钟总超时，30秒连接超时
            async with self._adapter.session.post(url, data=data, timeout=timeout) as response:
                # 检查响应状态
                if response.status == 413:
                    # 文件过大
                    error_msg = f"[文件发送失败] 文件过大: {upload_filename}\n原因: 超过云湖服务器限制"
                    return await self._adapter.call_api(
                        endpoint="/bot/send",
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": error_msg},
                        parentId=kwargs.get("parent_id", "")
                    )
                
                # 尝试解析JSON
                try:
                    upload_res = await response.json()
                except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                    # 响应不是JSON格式，可能是错误页面
                    error_text = await response.text()[:500]
                    self._adapter.logger.error(f"上传响应非JSON格式: {error_text}")
                    error_msg = f"[文件发送失败] 上传失败: {upload_filename}\n原因: 服务器返回错误 (状态码: {response.status})"
                    return await self._adapter.call_api(
                        endpoint="/bot/send",
                        recvId=self._target_id,
                        recvType=self._target_type,
                        contentType="text",
                        content={"text": error_msg},
                        parentId=kwargs.get("parent_id", "")
                    )
                
                self._adapter.logger.debug(f"上传响应: {upload_res}")

                if upload_res.get("code") !=1:
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
        bot = None

        # 智能判断 _account_id 是账户名还是 bot_id
        if bot_name and bot_name in self.bots:
            # _account_id 是账户名，直接使用
            bot = self.bots[bot_name]
            if not bot.enabled:
                raise ValueError(f"Bot {bot_name} 已禁用")
            bot_token = bot.token
        elif bot_name:
            # _account_id 是 bot_id，查找对应的账户
            for name, bot_config in self.bots.items():
                if bot_config.bot_id == bot_name:
                    bot = bot_config
                    bot_name = name
                    break
            if bot and not bot.enabled:
                raise ValueError(f"Bot {bot_name} (bot_id: {bot.bot_id}) 已禁用")
            if not bot:
                self.logger.warning(f"找不到bot_id为 {bot_name} 的机器人，将使用默认bot")

        if not bot:
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
        self.logger.debug(f"Bot {bot_name} (bot_id: {bot.bot_id}) 准备发送流式消息到 {target_id}，会话类型: {conversation_type}, 内容类型: {content_type}")
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
        :param _account_id: 账户名或bot_id
        :param params: 其他API参数
        :return: 标准化的响应
        """
        # 确定使用的bot
        bot = None

        # 智能判断 _account_id 是账户名还是 bot_id
        if _account_id and _account_id in self.bots:
            # _account_id 是账户名，直接使用
            bot = self.bots[_account_id]
            if not bot.enabled:
                raise ValueError(f"Bot {_account_id} 已禁用")
        elif _account_id:
            # _account_id 是 bot_id，查找对应的账户
            for name, bot_config in self.bots.items():
                if bot_config.bot_id == _account_id:
                    bot = bot_config
                    _account_id = name
                    break
            if bot and not bot.enabled:
                raise ValueError(f"Bot {_account_id} (bot_id: {bot.bot_id}) 已禁用")
            if not bot:
                self.logger.warning(f"找不到bot_id为 {_account_id} 的机器人，将使用默认bot")

        if not bot:
            # 使用第一个启用的bot
            enabled_bots = [b for b in self.bots.values() if b.enabled]
            if not enabled_bots:
                raise ValueError("没有配置任何启用的机器人")
            bot = enabled_bots[0]
            _account_id = next((name for name, b in self.bots.items() if b == bot), "")

        self.logger.error(f"Bot {_account_id} (bot_id: {bot.bot_id}) 调用API:{endpoint} 参数:{params}")

        raw_response = await self._net_request("POST", endpoint, params, bot_token=bot.token)

        is_batch = "batch" in endpoint or isinstance(params.get('recvIds'), list)

        standardized = {
            "status": "ok" if raw_response.get("code") == 1 else "failed",
            "retcode": 0 if raw_response.get("code") == 1 else 34000 + (raw_response.get("code") or 0),
            "data": {},
            "message": "",
            "yunhu_raw": raw_response,
            "self": {"user_id": bot.bot_id}  # 使用bot_id标识机器人账号
        }

        if raw_response.get("code") == 1:
            if is_batch:
                message_ids = [
                    msg.get("msgId", "")
                    for msg in raw_response.get("data", {}).get("successList", [])
                    if isinstance(msg, dict) and msg.get("msgId")
                ] if "successList" in raw_response.get("data", {}) else []
                standardized["message_id"] = message_ids
                standardized["data"]["message_ids"] = message_ids
            else:
                data = raw_response.get("data", {})
                message_id = (
                    data.get("messageInfo", {}).get("msgId", "")
                    if "messageInfo" in data
                    else data.get("msgId", "")
                )
                standardized["message_id"] = message_id
                standardized["data"]["message_id"] = message_id
                # 添加时间戳
                import time
                standardized["data"]["time"] = time.time()
        else:
            standardized["data"] = None
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
