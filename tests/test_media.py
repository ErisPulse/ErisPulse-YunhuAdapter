"""媒体消息与标准 Web 动作路由的回归测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from YunhuAdapter.Converter import YunhuConverter


def _image_message():
    return {
        "version": "1.0",
        "header": {"eventId": "e1", "eventType": "message.receive.normal", "eventTime": 1700000000000},
        "event": {
            "sender": {"senderId": "u1", "senderType": "user", "senderNickname": "tester"},
            "chat": {"chatId": "g1", "chatType": "group"},
            "message": {
                "msgId": "m1",
                "parentId": "",
                "sendTime": 1700000000000,
                "chatId": "g1",
                "chatType": "group",
                "contentType": "image",
                "content": {
                    "imageUrl": "https://chat-img.jwznb.com/abc.tmp",
                    "imageName": "abc.tmp",
                    "imageWidth": 10,
                    "imageHeight": 20,
                },
            },
        },
    }


def test_media_data_carries_referer_hint():
    c = YunhuConverter()
    ev = c.convert(_image_message())
    seg = ev["message"][0]
    assert seg["type"] == "image"
    assert seg["data"]["headers"]["Referer"] == "https://im.jwzhd.com/"
    assert seg["data"]["url"] == "https://chat-img.jwznb.com/abc.tmp"


@pytest.mark.asyncio
async def test_get_group_info_routed_to_web_api(monkeypatch):
    """call_api("get_group_info") 必须走 Api 的公开 Web API 实现，而不是 POST 兜底"""
    from YunhuAdapter.Core import YunhuAdapter

    a = YunhuAdapter.__new__(YunhuAdapter)
    a._accounts_data = None  # 单账户解析路径
    a.Api = YunhuAdapter.Api(a)
    a.logger = type("L", (), {"info": staticmethod(lambda *a, **k: None)})()
    calls = {}

    async def fake_web_request(path, payload=None, method="POST"):
        calls["path"] = path
        calls["payload"] = payload
        return {"code": 1, "data": {"group": {"groupId": "g1", "name": "测试群", "headcount": 3}}, "msg": "success"}

    monkeypatch.setattr(a.Api, "_web_request", fake_web_request)
    resp = await a.call_api("get_group_info", group_id="g1")
    assert calls["path"] == "/v1/group/group-info"
    assert calls["payload"] == {"groupId": "g1"}
    assert resp["status"] == "ok"
    assert resp["data"]["group_id"] == "g1"


@pytest.mark.asyncio
async def test_get_file_downloads_with_referer(monkeypatch):
    from YunhuAdapter.Core import YunhuAdapter

    a = YunhuAdapter.__new__(YunhuAdapter)
    a._accounts_data = None
    a.Api = YunhuAdapter.Api(a)
    seen = {}

    class FakeResp:
        async def read(self):
            return b"\x89PNG-data"

        def headers(self):  # noqa: U100（占位，实际用属性）
            return {}

    fake_headers = {"Content-Type": "image/png"}

    async def fake_get(url, headers=None, params=None):
        seen["url"] = url
        seen["headers"] = headers

        class _R:
            async def read(self_inner):
                return b"\x89PNG-data"

            content_type = "image/png"
            headers = fake_headers

        return _R()

    import YunhuAdapter.Core as core_mod
    monkeypatch.setattr(core_mod, "client", type("C", (), {"get": staticmethod(fake_get)}))
    resp = await a.call_api("get_file", file_id="https://chat-img.jwznb.com/abc.tmp")
    assert seen["url"] == "https://chat-img.jwznb.com/abc.tmp"
    assert seen["headers"]["Referer"] == "https://im.jwzhd.com/"
    assert resp["status"] == "ok"
    import base64
    assert base64.b64decode(resp["data"]["base64"]) == b"\x89PNG-data"


@pytest.mark.asyncio
async def test_get_file_missing_id():
    from YunhuAdapter.Core import YunhuAdapter

    a = YunhuAdapter.__new__(YunhuAdapter)
    a._accounts_data = None
    resp = await a.call_api("get_file")
    assert resp["status"] == "failed"
    assert resp["retcode"] == 10003
