# 更新日志

所有版本更新遵循 [语义化版本控制](https://semver.org/lang/zh-CN/) 规范。

> **如何阅读本日志**
> 每个版本分为 "新增"/"变更"/"修复"/"移除"/"废弃" 等部分。建议开发者在升级前先阅读对应版本的 Breaking Change 和修复内容。

> **贡献日志**
> 如需为新版本添加日志，请在对应版本号下补充内容，并注明日期和主要贡献者。

---

## 规则

### 必须包含的信息
1. **贡献者信息**：每项变更必须标明贡献者，格式为 `@Github用户名`
2. **变更类型**：明确标识变更类型（新增/变更/修复/移除/废弃等）
3. **日期信息**：版本发布日期采用 `YYYY/MM/DD` 格式

### 示例格式

```markdown
## [version] - 2025/08/20
> 开发版本

### 新增

- By [贡献者](https://github.com/贡献者)
  - `模块名` 模块新增功能描述：
    - 具体功能点1
    - 具体功能点2
```

---

## [4.3.0] - 2026/08/06

### 新增
- **标准 Api 动作（ApiDSL）**：新增 `Api` 内部类，提供跨平台标准动作
  - `get_self_info()` / `get_user_info(user_id)` / `get_group_info(group_id)`：通过公开 Web API（chat-web-go.jwzhd.com，非官方）实现信息查询，返回数据含昵称/头像/人数/VIP 等扩展字段，并输出信息日志
  - `upload_file(*, type, name, ...)`：自动判定 image/video/file 类别上传到对应端点
  - `get_file(file_id)`：云湖 file_id 即下载 URL，直接返回
  - `delete_message(message_id, *, chat_id, chat_type)`：撤回消息（云湖要求 chat_id+chat_type）
  - 不支持的标准动作（get_friend_list / get_group_list / 群成员 / set_group_name / leave_group）返回 retcode=10002
- **平台扩展动作**：通过 `Api.call("yunhu.xxx", ...)` 调用云湖特有动作
  - `yunhu.recall` / `yunhu.kick` / `yunhu.ban` / `yunhu.unban`
  - `yunhu.tag.create/edit/delete/list/relate/relate_cancel`
  - `yunhu.set_member_title` / `yunhu.unset_member_title`（标签≈头衔的原生语义别名，内部映射到 tag.relate）
  - `yunhu.msg_type_limit` / `yunhu.get_messages` / `yunhu.bot_info` / `yunhu.user_homepage`
- **EventMixin 事件扩展方法**：事件对象可直接调用 `get_sender_role()` / `get_sender_title()` / `get_button_value()` / `get_a2ui_action()` / `get_command()` / `get_menu_id()` / `get_setting()` 等
- **声明式翻译键（I18nClass）**：配置字段的 zh-CN/en 翻译集中声明，框架自动注册
- **全局配置类（ConfigClass）**：`base_url` / `web_api_base_url` / `ws_base_url` 可配置（带默认值）

### 变更
- Converter 继承 `BaseConverter` 基类，复用公共字段构建与消息段辅助方法
- 配置字段 metadata 迁移到 `ui` 新格式（兼容 `webui` 旧格式）
- 事件新增标准 `role` 字段（由 senderUserLevel 映射）与 `user_avatar` 字段
- 新增 `on_config_update` 热更新回调，API 地址变更时自动同步
- 网络层统一使用 `ErisPulse.Core.client`，不再顶层依赖 aiohttp（仅 multipart 上传处函数内局部导入 FormData）
- **上传逻辑重构**：下载改用 `resp.read()`（修复 `resp.raw.content.iter_chunked` 流式读取因 client eager-read 导致的 "Connection closed" 失败）；类型检测 / multipart 上传 / 失败回退文案统一为适配器级共享辅助方法（`_detect_extension` / `_build_upload_filename` / `_perform_upload` / `_extract_upload_key`）
- **Api 扩展参数映射修复**：`tag.*` / `msg_type_limit` 等扩展动作补全 OB12→云湖参数键名翻译（group_id→groupId 等）
- **call_api 参数清理**：剔除 `ApiDSL._merge_context` 泄漏的 `account_id` 参数，避免其进入请求体/查询串导致 "Invalid variable type"
- **call_api 响应数据保留**：非批量成功响应不再用 `{"message_id", "time"}` 覆盖平台返回的真实 `data`（如标签列表 / 历史消息 / 看板），发送类响应仍注入 `message_id`/`time` 保持向后兼容
- `yunhu.bot_info` / `yunhu.user_homepage` 扩展动作返回标准化 OB12 响应（含 `self` 字段），并记录查询日志

### 移除
- 移除 `aiohttp` 直接依赖（ErisPulse 已内置，无需重复声明）

---

## [3.6.0] - 2026/02/12  

### 新增
- 链式修饰支持：新增 `.Reply(message_id)` 等链式修饰方法，支持消息回复等操作
- OneBot12消息格式支持：新增 `.Raw_ob12()` 方法，支持发送OneBot12格式消息
- 多机器人配置及管理：支持通过 bot_id 识别机器人账户，同时配置多个云湖机器人
- 日志信息优化：增强日志中的bot_id识别信息，便于调试和追踪

## [3.4.0] - 2025/08/21

### 变更
- 向 `convert` 模块添加 `yunhu_raw_type` 字段
- 删除提交原始数据的接口（交由ErisPulse处理原生事件分发）

---

## [3.3.2] - 2025/08/20

### 修复
- 修复config调用问题

---

## [3.2.1] - 2025/08/20

### 修复
- 修复流式发送时返回信息为非OneBot12格式的错误

---

## [3.2.0] - 2025/08/20

### 新增
- 平台原生事件映射关系添加原始事件提交

### 变更
- 修改注册路由的方法为最新实现，移除原兼容性模式

### 移除
- 移除 `CheckExist` 发送接口

---

## [2.8.0]

### 新增
- 添加 ErisPulse 2.0.0 对于OneBot12协议对转的兼容

---

## [2.7.0]

### 新增
- 编辑消息支持传入按钮
- 上传文件时可以传入文件名（包括流式）

---

## [2.6.0]

### 新增
- File/Image/Video 支持流式上传模式