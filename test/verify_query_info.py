"""验证查询类 API"code=1 空壳数据"误判修复

覆盖：get_user_info / get_group_info / get_self_info / call("yunhu.user_homepage")
- 离线用例：monkeypatch _web_request 返回空壳 fixture（不依赖真实服务器行为）
- 在线用例：真实用户 5197892（YingXinche）/ 不存在用户 999999999999999999

运行（仓库根目录）：python test/verify_query_info.py
退出码：0 全部通过，1 存在失败
"""

import asyncio
import sys

from ErisPulse import sdk

REAL_USER_ID = "5197892"  # 真实存在，nickname 应为 YingXinche
GHOST_USER_ID = "999999999999999999"  # 不存在
REAL_GROUP_ID = "272475188"
GHOST_GROUP_ID = "1"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}\n      {detail}")


def is_not_found(resp, keyword):
    return (
        resp.get("status") == "failed"
        and resp.get("retcode") == 34001
        and keyword in (resp.get("message") or "")
    )


async def main():
    if not await sdk.init_task():
        print("ErisPulse 初始化失败，请检查配置")
        return 2
    try:
        await sdk.adapter.startup()
    except Exception as e:
        print(f"适配器启动异常（继续测试，公开 Web API 查询无需鉴权）: {e}")
    await asyncio.sleep(3)

    platform = getattr(sdk.adapter, "yunhu")
    api = platform.Api

    # ---- 离线用例：模拟服务端对不存在 userId 的空壳响应 ----
    async def fake_web_request(path, payload=None, method="POST"):
        return {
            "code": 1,
            "msg": "success",
            "data": {
                "user": {
                    "userId": "",
                    "nickname": "",
                    "registerTimeText": "1970-01-01 08:00:00",
                    "medals": [],
                }
            },
        }

    orig_web_request = api._web_request
    api._web_request = fake_web_request
    try:
        resp = await api.get_user_info(GHOST_USER_ID)
    finally:
        api._web_request = orig_web_request
    check(
        "离线: 空壳响应不再误判为成功（failed/34001/用户不存在）",
        is_not_found(resp, "用户不存在"),
        f"status={resp.get('status')}, retcode={resp.get('retcode')}, "
        f"message={resp.get('message')}",
    )

    # ---- 在线用例：真实存在的用户 ----
    resp = await api.get_user_info(REAL_USER_ID)
    d = resp.get("data") or {}
    check(
        "在线: get_user_info(5197892) status=ok 且 nickname=YingXinche",
        resp.get("status") == "ok" and d.get("user_name") == "YingXinche",
        f"status={resp.get('status')}, user_name={d.get('user_name')}, "
        f"user_id={d.get('user_id')}",
    )
    check(
        "在线: 返回新增字段 register_time_text/on_line_day/continuous_on_line_day/medals",
        "register_time_text" in d
        and "on_line_day" in d
        and "continuous_on_line_day" in d
        and "medals" in d,
        f"register_time_text={d.get('register_time_text')}, "
        f"on_line_day={d.get('on_line_day')}, "
        f"continuous_on_line_day={d.get('continuous_on_line_day')}, "
        f"medals={d.get('medals')}",
    )

    # ---- 在线用例：不存在的用户 ----
    resp = await api.get_user_info(GHOST_USER_ID)
    check(
        "在线: get_user_info(999999999999999999) failed/34001 且 message 含'用户不存在'",
        is_not_found(resp, "用户不存在"),
        f"status={resp.get('status')}, retcode={resp.get('retcode')}, "
        f"message={resp.get('message')}",
    )

    # ---- 群信息（同类空壳校验）----
    resp = await api.get_group_info(REAL_GROUP_ID)
    check(
        "在线: get_group_info(272475188) status=ok",
        resp.get("status") == "ok",
        f"status={resp.get('status')}, "
        f"group_name={(resp.get('data') or {}).get('group_name')}",
    )
    resp = await api.get_group_info(GHOST_GROUP_ID)
    # 群接口对不存在的群服务端直接返回 code!=1（msg=群聊不存在），空壳校验为兜底；
    # 行为要求：failed/34001，不限定具体文案
    check(
        "在线: get_group_info(1) failed/34001",
        resp.get("status") == "failed" and resp.get("retcode") == 34001,
        f"status={resp.get('status')}, retcode={resp.get('retcode')}, "
        f"message={resp.get('message')}",
    )

    # ---- 扩展动作（同一公开 API 的另一入口）----
    resp = await api.call("yunhu.user_homepage", user_id=GHOST_USER_ID)
    check(
        "在线: call('yunhu.user_homepage') 不存在用户 failed/34001",
        is_not_found(resp, "用户不存在"),
        f"status={resp.get('status')}, retcode={resp.get('retcode')}, "
        f"message={resp.get('message')}",
    )

    # ---- 机器人自身信息（依赖启动时探测到的 bot_id）----
    resp = await api.get_self_info()
    if resp.get("status") == "failed" and resp.get("retcode") == 35000:
        print(f"SKIP  get_self_info（机器人 ID 尚未探测到）: {resp.get('message')}")
    else:
        check(
            "在线: get_self_info status=ok",
            resp.get("status") == "ok",
            f"status={resp.get('status')}, "
            f"user_name={(resp.get('data') or {}).get('user_name')}",
        )

    failed = [name for name, ok in results if not ok]
    print("=" * 50)
    print(
        f"结果: {len(results) - len(failed)}/{len(results)} 通过"
        + (f"，失败: {failed}" if failed else "，全部通过")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    finally:
        try:
            asyncio.run(sdk.adapter.shutdown())
        except Exception:
            pass
    sys.exit(exit_code)
