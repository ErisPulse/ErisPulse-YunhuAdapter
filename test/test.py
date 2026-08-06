import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from ErisPulse import sdk
from ErisPulse.Core.Event import notice

@dataclass
class TestConfig:
    """测试配置类"""
    # 适配器配置
    adapter_name: str = "yunhu"  # 要测试的适配器名称
    
    # 基础配置
    group_id: str = "272475188"  # 测试群号
    test_user_id: str = "5197892"  # 测试用户ID
    test_user_id_2: str = "5940358"  # 第二个测试用户ID
    
    # 文件路径配置
    test_files_dir: str = "test_files"
    video_file: str = "test.mp4"
    image_file: str = "test.jpg"
    doc_file  : str = "test.docx"
    voice_file: Optional[str] = "M5000017K7gL4WYnw2.mp3"
    
    # 消息发送间隔（秒）
    send_interval: float = 1.0
    
    # 启用/禁用特定测试
    enable_basic_tests: bool = True  # 基础测试（1-5）
    enable_media_tests: bool = True  # 媒体测试（6-11）
    enable_advanced_tests: bool = True  # 高级功能测试（12-16）
    enable_format_tests: bool = True  # 格式化消息测试（17-19）
    enable_chain_tests: bool = True  # 链式调用测试（20-24）
    enable_mention_tests: bool = True  # @功能测试（25-26）
    enable_recall_tests: bool = True  # 撤回测试（27）
    enable_button_tests: bool = True  # 按钮测试（28-29）
    enable_api_tests: bool = True  # ApiDSL 测试（30-42）
    enable_event_mixin_tests: bool = True  # EventMixin 单元测试（43）

    # 单独启用的测试（列表形式）
    # 例如：[1, 6, 7] 表示只运行测试1、6和7
    # 如果为空列表，则根据上面的 bool 配置运行
    # specific_tests: List[int] = field(default_factory=list)
    specific_tests = []

    # Api 测试配置
    test_tag: str = "ErisPulse"  # 用于头衔/标签测试的标签名（云湖限最长 9 个字符）
    test_ban_duration: int = 600  # 禁言时长（秒），云湖仅接受 0/600/3600/21600/43200/-1
    
    # URL 配置
    image_url: str = "https://http.cat/200"
    voice_url: str = "http://music.163.com/song/media/outer/url?id=1372315637.mp3"
    video_url: str = "https://www.w3school.com.cn/example/html5/mov_bbb.mp4"
    file_url: str = "https://www.w3school.com.cn/example/html5/mov_bbb.mp4"


@dataclass
class TestResult:
    """单个测试结果"""
    test_num: int
    test_name: str
    status: str  # "success", "failed", "error", "skipped"
    response: Optional[dict] = None
    error_message: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class TestCase:
    """测试用例类"""
    name: str
    enabled: bool = True
    async_func: Optional[callable] = None
    description: str = ""


class TestSkipped(Exception):
    """测试被跳过（如缺少机器人权限、配置项未就绪等环境原因）"""


class TestRunner:
    """测试运行器"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.adapter = None
        self.api_adapter = None
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
        self.reply_message_id = ""  # 用于存储回复测试的 message_id
        self.recall_message_id = ""  # 用于存储撤回测试的 message_id

    def setup(self):
        """初始化"""
        platform = getattr(sdk.adapter, self.config.adapter_name)
        self.adapter = platform.Send
        self.api_adapter = platform.Api
        self._register_test_cases()
        
    def _read_file(self, filename: str) -> Optional[bytes]:
        """读取文件内容"""
        file_path = Path(self.config.test_files_dir) / filename
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception:
            return None
    
    def _register_test_cases(self):
        """注册所有测试用例"""
        # 基础测试
        self._add_basic_tests()
        # 媒体测试
        self._add_media_tests()
        # 高级功能测试
        self._add_advanced_tests()
        # 格式化消息测试
        self._add_format_tests()
        # 链式调用测试
        self._add_chain_tests()
        # @功能测试
        self._add_mention_tests()
        # 按钮测试
        self._add_button_tests()
        # ApiDSL 测试
        self._add_api_tests()
        # EventMixin 单元测试
        self._add_event_mixin_tests()
    
    def _add_basic_tests(self):
        """添加基础测试用例"""
        self.test_cases.extend([
            TestCase("发送文本消息", self.config.enable_basic_tests, None),
            TestCase("发送@用户消息", self.config.enable_basic_tests, None),
            TestCase("发送表情（emoji）", self.config.enable_basic_tests, None),
            TestCase("发送Markdown消息", self.config.enable_basic_tests, None),
            TestCase("发送Html消息", self.config.enable_basic_tests, None),
        ])
    
    def _add_media_tests(self):
        """添加媒体测试用例"""
        self.test_cases.extend([
            TestCase("发送图片（本地文件）", self.config.enable_media_tests, None),
            TestCase("发送图片（URL）", self.config.enable_media_tests, None),
            TestCase("发送视频（本地文件）", self.config.enable_media_tests, None),
            TestCase("发送视频（URL）", self.config.enable_media_tests, None),
            TestCase("发送语音（本地文件）", self.config.enable_media_tests, None),
            TestCase("发送语音（URL）", self.config.enable_media_tests, None),
        ])
    
    def _add_advanced_tests(self):
        """添加高级功能测试用例"""
        self.test_cases.extend([
            TestCase("发送文件（本地）", self.config.enable_advanced_tests, None),
            TestCase("发送文件（URL）", self.config.enable_advanced_tests, None),
            TestCase("发送回复消息", self.config.enable_advanced_tests, None),
            TestCase("发送组合消息", self.config.enable_advanced_tests, None),
            TestCase("撤回消息", self.config.enable_advanced_tests, None),
        ])
    
    def _add_format_tests(self):
        """添加格式化消息测试用例"""
        self.test_cases.extend([
            TestCase("发送格式化消息（Raw_ob12）", self.config.enable_format_tests, None),
            TestCase("发送文本消息段", self.config.enable_format_tests, None),
            TestCase("发送组合消息段", self.config.enable_format_tests, None),
        ])
    
    def _add_chain_tests(self):
        """添加链式调用测试用例"""
        self.test_cases.extend([
            TestCase("多次@用户（链式调用）", self.config.enable_chain_tests, None),
            TestCase("链式调用 - 回复+@用户", self.config.enable_chain_tests, None),
            TestCase("链式调用 - 组合修饰符", self.config.enable_chain_tests, None),
            TestCase("格式化消息 + 链式@", self.config.enable_chain_tests, None),
            TestCase("复杂组合消息", self.config.enable_chain_tests, None),
        ])
    
    def _add_mention_tests(self):
        """添加@功能测试用例"""
        self.test_cases.extend([
            TestCase("@全体成员", self.config.enable_mention_tests, None),
            TestCase("@全体 + @用户组合", self.config.enable_mention_tests, None),
        ])

    def _add_button_tests(self):
        """添加按钮功能测试用例"""
        self.test_cases.extend([
            TestCase("发送带按钮的消息（群）", self.config.enable_button_tests, None),
            TestCase("发送带按钮的私聊消息", self.config.enable_button_tests, None),
        ])

    def _add_api_tests(self):
        """添加 ApiDSL 标准动作与平台扩展动作测试用例"""
        self.test_cases.extend([
            TestCase("Api.get_self_info（机器人自身信息）", self.config.enable_api_tests, None),
            TestCase("Api.get_user_info（用户信息）", self.config.enable_api_tests, None),
            TestCase("Api.get_group_info（群信息）", self.config.enable_api_tests, None),
            TestCase("Api.upload_file（上传文件，data方式）", self.config.enable_api_tests, None),
            TestCase("Api.get_file（获取文件URL）", self.config.enable_api_tests, None),
            TestCase("Api.delete_message（撤回消息）", self.config.enable_api_tests, None),
            TestCase("Api.call yunhu.bot_info（扩展）", self.config.enable_api_tests, None),
            TestCase("Api.call yunhu.user_homepage（扩展）", self.config.enable_api_tests, None),
            TestCase("Api.call yunhu.get_messages（历史消息）", self.config.enable_api_tests, None),
            TestCase("Api.call yunhu.tag.list（标签列表）", self.config.enable_api_tests, None),
            TestCase("Api.call yunhu.ban/unban（禁言/解禁）", self.config.enable_api_tests, None),
            TestCase("Api.call yunhu.set/unset_member_title（头衔）", self.config.enable_api_tests, None),
            TestCase("Api.Using 多账户选择", self.config.enable_api_tests, None),
            TestCase("Api 不支持的标准动作返回10002", self.config.enable_api_tests, None),
        ])

    def _add_event_mixin_tests(self):
        """添加 EventMixin 事件扩展方法单元测试用例"""
        self.test_cases.extend([
            TestCase("EventMixin 发送者角色/头像", self.config.enable_event_mixin_tests, None),
            TestCase("EventMixin 指令/按钮/A2UI/菜单/设置", self.config.enable_event_mixin_tests, None),
            TestCase("EventMixin 类型判断与原始事件", self.config.enable_event_mixin_tests, None),
        ])

    def _make_event_mixin_tester(self):
        """
        构造一个绑定 EventMixin 方法的测试对象

        EventMixin 的方法依赖 ``self.get(key, default)``，
        此处用内存字典模拟事件数据，实现纯离线单元测试（不依赖真实事件）。
        """
        from YunhuAdapter.Core import YunhuAdapter

        class _FakeEvent(dict):
            """同时支持 Event.get(key, default) 与 dict 访问"""

            def get(self, key, default=None):
                return super().get(key, default)

        def _bind(data: dict) -> _FakeEvent:
            obj = _FakeEvent(data)
            # 将 EventMixin 方法绑定到实例（绕过平台注册，直接单元测试）
            for name, fn in [
                (n, f)
                for n, f in YunhuAdapter.EventMixin.__dict__.items()
                if callable(f) and not n.startswith("_")
            ]:
                setattr(obj, name, fn.__get__(obj))
            return obj

        # 群文本消息（含角色/头像）
        group_msg = _bind({
            "platform": "yunhu",
            "detail_type": "group",
            "role": "admin",
            "user_avatar": "http://x/avatar.png",
            "yunhu_sender_level": "administrator",
            "yunhu_raw": {
                "header": {"eventType": "message.receive.normal"},
                "event": {
                    "sender": {
                        "senderId": "u1",
                        "senderNickname": "Alice",
                        "senderUserLevel": "administrator",
                        "senderAvatarUrl": "http://x/avatar.png",
                    }
                },
            },
        })
        # 指令消息
        instr_msg = _bind({
            "platform": "yunhu",
            "yunhu_command": {"name": "help", "id": "1", "args": ""},
        })
        # 按钮点击事件
        button_click = _bind({
            "platform": "yunhu",
            "detail_type": "yunhu_button_click",
            "yunhu_button": {"id": "b1", "value": "confirm"},
        })
        # A2UI 事件
        a2ui = _bind({
            "platform": "yunhu",
            "detail_type": "yunhu_a2ui_button",
            "yunhu_a2ui": {
                "recv_id": "r1",
                "recv_type": "group",
                "action_name": "submit",
                "source_component_id": "f1",
                "form_context": {"name": "张三"},
                "interaction_json": "{}",
            },
        })
        # 快捷菜单事件
        menu = _bind({
            "platform": "yunhu",
            "detail_type": "yunhu_shortcut_menu",
            "yunhu_menu": {"id": "m1", "type": 1, "action": 1},
        })
        # 机器人设置事件
        setting = _bind({
            "platform": "yunhu",
            "detail_type": "yunhu_bot_setting",
            "yunhu_setting": {"notifyLevel": 1},
        })

        return {
            "group_msg": group_msg,
            "instr_msg": instr_msg,
            "button_click": button_click,
            "a2ui": a2ui,
            "menu": menu,
            "setting": setting,
        }
    
    def _check_response(self, response: Any) -> tuple[bool, Optional[dict]]:
        """检查响应是否成功"""
        if response is None:
            return False, None
        
        # 如果是 Task 对象，获取结果
        if hasattr(response, '__await__'):
            # 这是一个协程，已经被 await 了
            if isinstance(response, dict):
                resp = response
            else:
                return False, None
        elif isinstance(response, dict):
            resp = response
        else:
            return False, None
        
        # 检查响应格式是否符合标准
        if isinstance(resp, dict):
            status = resp.get("status")
            retcode = resp.get("retcode", -1)
            
            if status == "ok" and retcode == 0:
                return True, resp
        
        return False, resp
    
    async def run_test(self, test_num: int):
        """运行单个测试"""
        if test_num > len(self.test_cases) or test_num < 1:
            return
        
        test_case = self.test_cases[test_num - 1]
        print(f"{test_num}. {test_case.name}")
        
        result = TestResult(
            test_num=test_num,
            test_name=test_case.name,
            status="skipped"
        )
        
        start_time = time.time()
        
        try:
            # 执行测试
            response = await self._execute_test(test_num)
            
            # 检查结果
            success, resp_dict = self._check_response(response)
            
            result.execution_time = time.time() - start_time
            result.response = resp_dict
            
            if success:
                result.status = "success"
                print(f"  成功 - {result.execution_time:.2f}s")
                if resp_dict and resp_dict.get("data") is not None:
                    data_str = json.dumps(resp_dict.get("data"), ensure_ascii=False)
                    if len(data_str) > 500:
                        data_str = data_str[:500] + "...(已截断)"
                    print(f"    data: {data_str}")
            else:
                result.status = "failed"
                if resp_dict:
                    retcode = resp_dict.get("retcode", -1)
                    message = resp_dict.get("message", "")
                    print(f"  失败 - retcode: {retcode}, message: {message}")
                    if resp_dict.get("data") is not None:
                        data_str = json.dumps(resp_dict.get("data"), ensure_ascii=False)
                        if len(data_str) > 500:
                            data_str = data_str[:500] + "...(已截断)"
                        print(f"    data: {data_str}")
                else:
                    print(f"  失败 - 无效响应")
                    
        except TestSkipped as e:
            result.execution_time = time.time() - start_time
            result.status = "skipped"
            result.error_message = str(e)
            print(f"  跳过 - {str(e)}")
        except Exception as e:
            result.execution_time = time.time() - start_time
            result.status = "error"
            result.error_message = str(e)
            print(f"  错误 - {type(e).__name__}: {str(e)}")
        
        self.results.append(result)
        await asyncio.sleep(self.config.send_interval)
    
    async def _execute_test(self, test_num: int) -> Optional[Any]:
        """执行具体的测试逻辑"""
        group_id = self.config.group_id
        test_user_id = self.config.test_user_id
        
        # 1. 发送文本消息
        if test_num == 1:
            return await self.adapter.To("group", group_id).Text("Hello, 这是一条测试消息！")
        
        # 2. 发送@用户消息
        elif test_num == 2:
            return await self.adapter.To("group", group_id).At(test_user_id).Text("@某位成员")

        # 3. 发送表情（emoji，云湖文本消息支持 emoji）
        elif test_num == 3:
            return await self.adapter.To("group", group_id).Text("发送表情测试 😀🎉🚀")
        
        # 4. 发送Markdown消息
        elif test_num == 4:
            markdown_text = "**粗体** 和 *斜体* 文本测试"
            return await self.adapter.To("group", group_id).Markdown(markdown_text)
        
        # 5. 发送Html消息
        elif test_num == 5:
            html_text = "<b>粗体</b> 和 <i>斜体</i> 文本测试"
            return await self.adapter.To("group", group_id).Html(html_text)
        
        # 6. 发送图片（本地文件）
        elif test_num == 6:
            image_data = self._read_file(self.config.image_file)
            if image_data:
                return await self.adapter.To("group", group_id).Image(image_data)
            # 回退到 URL 方式
            return await self.adapter.To("group", group_id).Image(self.config.image_url)
        
        # 7. 发送图片（URL）
        elif test_num == 7:
            return await self.adapter.To("group", group_id).Image(self.config.image_url)
        
        # 8. 发送视频（本地文件）
        elif test_num == 8:
            video_data = self._read_file(self.config.video_file)
            if video_data:
                return await self.adapter.To("group", group_id).Video(video_data)
            # 回退到 URL 方式
            return await self.adapter.To("group", group_id).Video(self.config.video_url)
        
        # 9. 发送视频（URL）
        elif test_num == 9:
            return await self.adapter.To("group", group_id).Video(self.config.video_url)
        
        # 10. 发送语音（本地文件）
        elif test_num == 10:
            if self.config.voice_file:
                voice_data = self._read_file(self.config.voice_file)
                if voice_data:
                    return await self.adapter.To("group", group_id).Voice(voice_data)
            # 回退到 URL 方式
            return await self.adapter.To("group", group_id).Voice(self.config.voice_url)
        
        # 11. 发送语音（URL）
        elif test_num == 11:
            return await self.adapter.To("group", group_id).Voice(self.config.voice_url)
        
        # 12. 发送文件（本地）
        elif test_num == 12:
            file_data = self._read_file(self.config.doc_file)
            if file_data:
                return await self.adapter.To("group", group_id).File(file_data)
            return await self.adapter.To("group", group_id).File(self.config.file_url)
        
        # 13. 发送文件（URL）
        elif test_num == 13:
            return await self.adapter.To("group", group_id).File(self.config.file_url)
        
        # 14. 发送回复消息
        elif test_num == 14:
            test_message = "这是一条测试消息，用于后续回复功能测试"
            result = await self.adapter.To("group", group_id).Text(test_message)
            
            # 尝试获取 message_id
            if isinstance(result, dict) and result.get("data", {}).get("message_id"):
                self.reply_message_id = result["data"]["message_id"]
            else:
                self.reply_message_id = "temp_msg_id_" + str(int(time.time()))
            
            return result
        
        # 15. 发送组合消息
        elif test_num == 15:
            ob12_message = [
                {"type": "text", "data": {"text": "组合消息测试："}},
                {"type": "mention", "data": {"user_id": test_user_id}}
            ]
            return await self.adapter.To("group", group_id).Raw_ob12(ob12_message)
        
        # 16. 撤回消息
        elif test_num == 16:
            # 先发送一条消息
            test_message = "这条消息将被撤回"
            result = await self.adapter.To("group", group_id).Text(test_message)
            
            print(f"发送消息：{result}")
            # 获取 message_id
            self.recall_message_id = result.get("data", {}).get("message_id")
            
            # 等待一下再撤回
            await asyncio.sleep(2)
            
            print(f"撤回消息：{self.recall_message_id}")

            # 撤回消息
            return await self.adapter.To("group", group_id).Recall(self.recall_message_id)
        
        # 17. 发送格式化消息（Raw_ob12）
        elif test_num == 17:
            ob12_message = [
                {"type": "text", "data": {"text": "这是格式化消息 "}},
                {"type": "text", "data": {"text": "使用 Raw_ob12 发送"}}
            ]
            return await self.adapter.To("group", group_id).Raw_ob12(ob12_message)
        
        # 18. 发送文本消息段
        elif test_num == 18:
            ob12_message = [
                {"type": "text", "data": {"text": "第一条文本消息段"}},
                {"type": "text", "data": {"text": "第二条文本消息段"}}
            ]
            return await self.adapter.To("group", group_id).Raw_ob12(ob12_message)
        
        # 19. 发送组合消息段
        elif test_num == 19:
            ob12_message = [
                {"type": "text", "data": {"text": "文本 + 图片："}},
                {"type": "image", "data": {"file": self.config.image_url}}
            ]
            return await self.adapter.To("group", group_id).Raw_ob12(ob12_message)
        
        # 20. 多次@用户（链式调用）
        elif test_num == 20:
            return await self.adapter.To("group", group_id).At(test_user_id).At(self.config.test_user_id_2).Text(" @多个用户")
        
        # 21. 链式调用 - 回复+@用户
        elif test_num == 21:
            return await self.adapter.To("group", group_id).Reply(self.reply_message_id).At(test_user_id).Text("回复并@用户")
        
        # 22. 链式调用 - 组合修饰符
        elif test_num == 22:
            return await self.adapter.To("group", group_id).At(test_user_id).Reply(self.reply_message_id).Text("@用户并回复")
        
        # 23. 格式化消息 + 链式@
        elif test_num == 23:
            ob12_message = [{"type": "text", "data": {"text": "格式化消息 + 链式@"}}]
            return await self.adapter.To("group", group_id).At(test_user_id).Raw_ob12(ob12_message)
        
        # 24. 复杂组合消息
        elif test_num == 24:
            ob12_message = [
                {"type": "text", "data": {"text": "复杂组合消息："}},
                {"type": "mention", "data": {"user_id": test_user_id}},
                {"type": "reply", "data": {"message_id": self.reply_message_id}}
            ]
            return await self.adapter.To("group", group_id).Raw_ob12(ob12_message)
        
        # 25. @全体成员
        elif test_num == 25:
            return await self.adapter.To("group", group_id).AtAll().Text("这是全体成员消息")
        
# 26. @全体 + @用户组合
        elif test_num == 26:
            return await self.adapter.To("group", group_id).AtAll().At(test_user_id).Text("全体 + 单个@")

        # 27. 发送带按钮的消息（测试yunhu按钮功能）
        elif test_num == 27:
            buttons = [
                [
                    {"text": "复制", "actionType": 2, "value": "test_copy_value"},
                    {"text": "跳转URL", "actionType": 1, "url": "http://www.baidu.com"},
                    {"text": "点击汇报", "actionType": 3, "value": "button_click_value"}
                ]
            ]
            return await self.adapter.To("group", group_id).Buttons(buttons).Text("带按钮的消息")

        # 28. 发送带按钮的私聊消息
        elif test_num == 28:
            buttons = [
                [
                    {"text": "按钮A", "actionType": 3, "value": "btn_a"},
                    {"text": "按钮B", "actionType": 3, "value": "btn_b"}
                ]
            ]
            return await self.adapter.To("user", test_user_id).Buttons(buttons).Text("点击下方按钮")

        # 29. Api.get_self_info
        elif test_num == 29:
            return await self.api_adapter.get_self_info()

        # 30. Api.get_user_info
        elif test_num == 30:
            return await self.api_adapter.get_user_info(test_user_id)

        # 31. Api.get_group_info
        elif test_num == 31:
            return await self.api_adapter.get_group_info(group_id)

        # 32. Api.upload_file（data 方式，自动判定类别）
        elif test_num == 32:
            image_data = self._read_file(self.config.image_file)
            if not image_data:
                # 回退：从 URL 下载
                image_data = b""
                try:
                    from ErisPulse.Core import client

                    resp = await client.get(self.config.image_url, timeout=60)
                    image_data = await resp.read()
                except Exception:
                    pass
            return await self.api_adapter.upload_file(
                type="data", name="test_upload.jpg", data=image_data
            )

        # 33. Api.get_file（云湖 file_id 即 URL）
        elif test_num == 33:
            return await self.api_adapter.get_file(self.config.image_url)

        # 34. Api.delete_message（需 chat_id + chat_type）
        elif test_num == 34:
            result = await self.adapter.To("group", group_id).Text("这条消息将被 Api.delete_message 撤回")
            msg_id = ""
            if isinstance(result, dict):
                msg_id = result.get("data", {}).get("message_id", "")
            if not msg_id:
                # 先查询最近一条消息作为测试目标
                history = await self.api_adapter.call(
                    "yunhu.get_messages", chat_id=group_id, chat_type="group", before=1
                )
                lst = (history.get("data") or {}).get("list", []) if isinstance(history, dict) else []
                if lst:
                    msg_id = lst[0].get("msgId", "")
            if not msg_id:
                return {"status": "failed", "retcode": 10003, "message": "未能获取可撤回的消息ID"}
            await asyncio.sleep(2)
            return await self.api_adapter.delete_message(
                msg_id, chat_id=group_id, chat_type="group"
            )

        # 35. Api.call yunhu.bot_info
        elif test_num == 35:
            # 用运行时探测到的机器人 ID 查询
            bot_id = ""
            platform = getattr(sdk.adapter, self.config.adapter_name)
            if hasattr(platform, "_bot_ids") and platform._bot_ids:
                bot_id = next(iter(platform._bot_ids.values()), "")
            if not bot_id:
                return {"status": "failed", "retcode": 35000, "message": "机器人ID尚未探测到"}
            return await self.api_adapter.call("yunhu.bot_info", bot_id=bot_id)

        # 36. Api.call yunhu.user_homepage
        elif test_num == 36:
            return await self.api_adapter.call("yunhu.user_homepage", user_id=test_user_id)

        # 37. Api.call yunhu.get_messages
        elif test_num == 37:
            return await self.api_adapter.call(
                "yunhu.get_messages", chat_id=group_id, chat_type="group", before=5
            )

        # 38. Api.call yunhu.tag.list
        elif test_num == 38:
            return await self.api_adapter.call("yunhu.tag.list", group_id=group_id)

        # 39. Api.call yunhu.ban + unban
        elif test_num == 39:
            ban_result = await self.api_adapter.call(
                "yunhu.ban",
                group_id=group_id,
                user_id=test_user_id,
                duration=self.config.test_ban_duration,
            )
            if not (isinstance(ban_result, dict) and ban_result.get("status") == "ok"):
                # 无权限/目标为群主等环境原因，跳过而非失败
                if isinstance(ban_result, dict) and ban_result.get("retcode") == 33999:
                    raise TestSkipped(f"禁言被拒（需机器人有禁言权限，且目标非群主）: {ban_result.get('message', '')}")
                return ban_result
            await asyncio.sleep(1)
            return await self.api_adapter.call(
                "yunhu.unban", group_id=group_id, user_id=test_user_id
            )

        # 40. Api.call yunhu.set_member_title + unset（标签≈头衔）
        elif test_num == 40:
            tag = self.config.test_tag
            # 确保标签存在（不存在则创建；已存在则复用）
            create_res = await self.api_adapter.call(
                "yunhu.tag.create", group_id=group_id, tag=tag
            )
            # 权限不足属于环境原因，跳过而非失败
            if isinstance(create_res, dict) and create_res.get("retcode") == 33999:
                raise TestSkipped(f"标签/头衔操作被拒（需机器人有标签管理权限）: {create_res.get('message', '')}")
            # 创建可能因已存在而失败，忽略
            await asyncio.sleep(0.5)
            set_res = await self.api_adapter.call(
                "yunhu.set_member_title", group_id=group_id, user_id=test_user_id, title=tag
            )
            if not (isinstance(set_res, dict) and set_res.get("status") == "ok"):
                if isinstance(set_res, dict) and set_res.get("retcode") == 33999:
                    raise TestSkipped(f"标签/头衔操作被拒（需机器人有标签管理权限）: {set_res.get('message', '')}")
                return set_res
            await asyncio.sleep(1)
            unset_res = await self.api_adapter.call(
                "yunhu.unset_member_title", group_id=group_id, user_id=test_user_id, title=tag
            )
            # 清理：删除测试标签（失败可忽略，如权限不足）
            await self.api_adapter.call("yunhu.tag.delete", group_id=group_id, tag=tag)
            return unset_res

        # 41. Api.Using 多账户选择
        elif test_num == 41:
            # Using 未指定时使用第一个启用账户，验证链式账户选择可用
            result = await self.api_adapter.Using("default").get_self_info()
            if isinstance(result, dict) and result.get("status") == "failed":
                # default 账户名可能不存在，回退到无 Using 调用
                return await self.api_adapter.get_self_info()
            return result

        # 42. Api 不支持的标准动作返回 retcode=10002
        elif test_num == 42:
            result = await self.api_adapter.get_friend_list()
            ok = (
                isinstance(result, dict)
                and result.get("status") == "failed"
                and result.get("retcode") == 10002
            )
            if not ok:
                raise AssertionError(f"get_friend_list 应返回 retcode=10002，实际: {result}")
            return {"status": "ok", "retcode": 0, "data": result}

        # 43. EventMixin 发送者角色/头像
        elif test_num == 43:
            objs = self._make_event_mixin_tester()
            gm = objs["group_msg"]
            assert gm.get_sender_role() == "admin", gm.get_sender_role()
            assert gm.get_sender_level() == "administrator", gm.get_sender_level()
            assert gm.get_sender_avatar() == "http://x/avatar.png", gm.get_sender_avatar()
            assert gm.get_raw_event()["header"]["eventType"] == "message.receive.normal"
            return {"status": "ok", "retcode": 0, "data": {"role": gm.get_sender_role()}}

        # 44. EventMixin 指令/按钮/A2UI/菜单/设置
        elif test_num == 44:
            objs = self._make_event_mixin_tester()
            assert objs["instr_msg"].get_command() == {"name": "help", "id": "1", "args": ""}
            assert objs["button_click"].get_button_value() == "confirm"
            assert objs["a2ui"].get_a2ui_action() == "submit"
            assert objs["a2ui"].get_a2ui_form_context() == {"name": "张三"}
            assert objs["menu"].get_menu_id() == "m1"
            assert objs["setting"].get_setting() == {"notifyLevel": 1}
            return {"status": "ok", "retcode": 0, "data": {"actions": "all"}}

        # 45. EventMixin 类型判断与原始事件
        elif test_num == 45:
            objs = self._make_event_mixin_tester()
            assert objs["button_click"].is_button_click() is True
            assert objs["button_click"].is_a2ui_button() is False
            assert objs["a2ui"].is_a2ui_button() is True
            assert objs["instr_msg"].is_command_message() is True
            assert objs["group_msg"].is_command_message() is False
            assert objs["group_msg"].get_sender_title() == ""
            return {"status": "ok", "retcode": 0, "data": {"types": "ok"}}

        return None
    
    def _print_summary(self):
        """打印测试结果汇总"""
        success_count = sum(1 for r in self.results if r.status == "success")
        failed_count = sum(1 for r in self.results if r.status == "failed")
        error_count = sum(1 for r in self.results if r.status == "error")
        skipped_count = sum(1 for r in self.results if r.status == "skipped")
        total_time = sum(r.execution_time for r in self.results)

        print("\n___")
        print("测试结果")
        print("    总结")
        print(f"         成功：{success_count}个")
        print(f"         失败：{failed_count}个")
        print(f"         错误：{error_count}个")
        print(f"         跳过：{skipped_count}个")

        if skipped_count > 0:
            print("\n    跳过详情")
            for r in self.results:
                if r.status == "skipped":
                    print(f"         [{r.test_num}] {r.test_name} - {r.error_message}")

        if failed_count > 0:
            print("\n    失败详情")
            for r in self.results:
                if r.status == "failed":
                    if r.response:
                        retcode = r.response.get("retcode", -1)
                        message = r.response.get("message", "")
                        print(f"         [{r.test_num}] {r.test_name} - retcode: {retcode}, message: {message}")
                    else:
                        print(f"         [{r.test_num}] {r.test_name} - 无响应")
        
        if error_count > 0:
            print("\n    错误详情")
            for r in self.results:
                if r.status == "error":
                    print(f"         [{r.test_num}] {r.test_name} - {r.error_message}")
        
        print(f"\n    执行时间：{total_time:.2f} 秒")
        print("___")
    
    async def run_all(self):
        """运行所有启用的测试"""
        enabled_tests = []
        
        # 如果指定了特定测试，只运行这些测试
        if self.config.specific_tests:
            for test_num in self.config.specific_tests:
                if 1 <= test_num <= len(self.test_cases):
                    enabled_tests.append(test_num)
                else:
                    print(f"[警告] 无效的测试编号: {test_num}")
        else:
            # 否则根据配置运行所有启用的测试
            for i, test_case in enumerate(self.test_cases, 1):
                if test_case.enabled:
                    enabled_tests.append(i)
        
        print(f"准备运行 {len(enabled_tests)} 个测试用例")
        print("=" * 50)
        
        for test_num in enabled_tests:
            await self.run_test(test_num)
        
        print("=" * 50)
        self._print_summary()


async def main():
    try:
        isInit = await sdk.init_task()
        
        if not isInit:
            sdk.logger.error("ErisPulse 初始化失败，请检查日志")
            return
        
        await sdk.adapter.startup()

        # 等待适配器完全启动
        await asyncio.sleep(3)
        
        # 创建测试配置
        config = TestConfig()
        
        # 配置示例：
        # 1. 指定适配器
        # config.adapter_name = "onebot12"
        # config.adapter_name = "red"

        # 2. 只运行特定测试
        # config.specific_tests = [6, 7, 8, 9, 10, 11]  # 只运行媒体测试
        # config.specific_tests = [29, 30, 31, 37]  # 只运行 Api 信息查询测试
        # config.specific_tests = [43, 44, 45]  # 只运行 EventMixin 单元测试

        # 3. 禁用某些测试类别
        # config.enable_media_tests = False  # 禁用媒体测试
        # config.enable_chain_tests = False   # 禁用链式调用测试
        # config.enable_api_tests = False  # 禁用 ApiDSL 测试
        
        # 4. 配置文件路径
        # config.video_file = "my_video.mp4"
        # config.voice_file = "my_voice.amr"
        # config.test_files_dir = "custom/files"
        
        # 配置发送间隔（秒）
        config.send_interval = 1.0
        
        print(f"测试适配器: {config.adapter_name}")
        print(f"测试目标: 群号 {config.group_id}")
        print("=" * 50)
        from ErisPulse.Core.Event import notice

        @notice.on_notice()
        async def handle_yunhu_notice(event):
            print(event)
            # 检查是否是按钮点击事件（使用 EventMixin 方法）
            if event.is_button_click():
                user_id = event.get_user_id()
                user_nickname = event.get_user_nickname()
                button_value = event.get_button_value()

                print(f"用户 {user_nickname}({user_id}) 点击了按钮: {button_value}")

                # 使用 event.reply() 自动回复（会根据平台自动选择正确的发送方式）
                if button_value == "confirm":
                    await event.reply("你点击了确认按钮！")
                elif button_value == "cancel":
                    await event.reply("操作已取消")
                else:
                    await event.reply(f"收到你的选择: {button_value}")

            # 处理快捷菜单事件
            elif event.get("detail_type") == "yunhu_shortcut_menu":
                menu_id = event.get_menu_id()
                await event.reply(f"触发了快捷菜单: {menu_id}")

            # 处理机器人设置变更
            elif event.get("detail_type") == "yunhu_bot_setting":
                settings = event.get_setting()
                await event.reply(f"设置已更新: {settings}")

            # 处理 A2UI 按钮事件（使用 EventMixin 方法）
            elif event.get("detail_type") == "yunhu_a2ui_button":
                action = event.get_a2ui_action()
                ctx = event.get_a2ui_form_context()
                await event.reply(f"A2UI操作: {action}, 表单数据: {ctx}")

            # 处理群消息（打印发送者角色，验证 EventMixin）
            elif event.get("detail_type") == "group":
                role = event.get_sender_role()
                print(f"收到群消息, 发送者角色: {role}")

        # 创建并运行测试
        runner = TestRunner(config)
        runner.setup()
        await runner.run_all()
        
        # 保持程序运行(不建议修改)
        await asyncio.Event().wait()
    except Exception as e:
        sdk.logger.error(f"发生错误: {e}", exc_info=True)
    except KeyboardInterrupt:
        sdk.logger.info("正在停止程序")
    finally:
        await sdk.adapter.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
