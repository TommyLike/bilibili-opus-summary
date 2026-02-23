# 邮件通知方案

## 功能描述

两个入口，共用同一套发送逻辑：

1. **新建时通知**：提交摘要任务时勾选「完成后发送邮件」，任务线程在生成结束后自动触发。
2. **详情页补发**：进入已生成摘要的详情页，填写收件地址后点击「发送邮件」，立即将该摘要发送到指定邮箱。

---

## 整体设计

| 维度 | 选择 | 理由 |
|---|---|---|
| 发送库 | Python 标准库 `smtplib` + `email` | 零新依赖，支持所有标准 SMTP |
| 邮件格式 | HTML + 纯文本 Multipart | 兼容性最好 |
| 发送时机 | 任务线程内同步发送（任务完成后） | 简单，不引入消息队列 |
| 失败处理 | 记录到任务状态，不影响主任务 | 邮件失败不应让用户以为摘要也失败 |
| 收件地址 | 每次提交时在前端填写 | 灵活，无需固定 |
| 发件地址 | .env 统一配置 | 安全，不暴露给前端 |

---

## 环境变量（新增）

```
# SMTP 发件配置（四项全填才启用邮件功能）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_sender@gmail.com
SMTP_PASSWORD=your_app_password     # Gmail 建议使用「应用专用密码」
SMTP_FROM=Bilibili摘要助手 <your_sender@gmail.com>   # 可选，默认等于 SMTP_USER

# 摘要详情页链接前缀（用于拼接邮件中的跳转链接）
APP_BASE_URL=http://localhost:5000
```

> SMTP 四项（HOST / PORT / USER / PASSWORD）任意一项未配置时，邮件功能在后端静默禁用，前端也不显示相关选项。

---

## 后端变更（app.py）

### 1. 邮件配置读取与检测

启动时读取 SMTP 相关 env，赋值给模块级常量：

```python
SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM", "") or SMTP_USER
APP_BASE_URL  = os.getenv("APP_BASE_URL", "http://localhost:5000").rstrip("/")

EMAIL_ENABLED = all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD])
```

### 2. 新增 GET /api/config（公开接口）

返回前端所需的服务端能力标志：

```
GET /api/config
Response: { "email_enabled": true/false }
```

前端用此决定是否展示邮件选项，无需登录即可访问（避免登录页也要额外处理）。

### 3. POST /api/tasks 新增字段

请求体新增可选字段：

```json
{
  "url": "...",
  "notify_email": "user@example.com"   // 为空/缺失时跳过邮件发送
}
```

### 4. 任务线程新增邮件发送步骤

`_worker` 函数在 `status = done` 之前插入邮件发送逻辑：

```
if notify_email and EMAIL_ENABLED:
    try:
        send_summary_email(notify_email, summary_id, result)
        TASKS[task_id]["email_sent"] = True
    except Exception as e:
        TASKS[task_id]["email_sent"] = False
        TASKS[task_id]["email_error"] = str(e)
```

邮件发送失败不影响任务最终状态（仍为 `done`）。

### 5. 新增 send_summary_email() 函数

```
参数：to_addr, summary_id, run_result_dict
流程：
  1. 读取 output/{summary_id}/summary.md 获取摘要内容
  2. 读取 output/{summary_id}/raw.json 获取作者和时间
  3. 拼接详情页 URL：{APP_BASE_URL}/summary/{summary_id}
  4. 构建 MIMEMultipart("alternative") 邮件：
     - text/plain：纯文本版本
     - text/html：HTML 版本（标题、链接、摘要正文）
  5. 通过 SMTP_HOST:SMTP_PORT 以 STARTTLS 方式发送
```

### 6. GET /api/tasks/<task_id> 响应新增字段

```json
{
  "task_id": "...",
  "status": "done",
  "result": {...},
  "email_sent": true,        // 可选，仅当请求了邮件通知时存在
  "email_error": null        // 发送失败时填充错误信息
}
```

### 7. 新增 POST /api/summaries/<summary_id>/send-email（需登录）

详情页「补发」入口调用此接口：

```
POST /api/summaries/<summary_id>/send-email
需要：require_auth
请求体：{ "email": "user@example.com" }
```

处理流程：
1. 校验 `EMAIL_ENABLED`，未启用返回 `503 {"error": "邮件功能未配置"}`
2. 校验 `email` 字段非空且格式合法（简单正则），否则 `400`
3. 调用复用的 `send_summary_email()` 函数
4. 成功返回 `200 {"ok": true}`；失败返回 `500 {"error": "..."}`

> 此接口同步执行（摘要文件已存在，发送很快），无需异步任务机制。

---

## 前端变更（HomeView.vue）

### 1. 启动时获取服务端配置

`onMounted` 时调用 `GET /api/config`，将 `email_enabled` 保存到响应式变量。

### 2. 表单新增邮件选项

邮件选项放在高级选项区域下方（始终可见，不折叠），仅当 `email_enabled = true` 时渲染：

```
☑ 生成后发送邮件通知
   收件邮箱：[___________________]
```

- 勾选时邮箱输入框出现，且为 required
- 不勾选时 `notify_email` 不包含在提交 payload 中

### 3. 提交 payload 新增字段

```js
if (form.notify_email_enabled && form.notify_email) {
  payload.notify_email = form.notify_email
}
```

### 4. 任务状态展示增加邮件结果

在 `status = done` 的状态提示中，补充邮件结果：

```
✅ 处理完成，即将跳转...
📧 邮件已发送至 user@example.com        ← email_sent = true
⚠️ 邮件发送失败：[错误信息]              ← email_sent = false
```

---

## 邮件内容设计

**主题：** `[Bilibili摘要] {author} · {pub_time}`

**HTML 正文结构：**

```
标题：{author} 的 Bilibili 动态摘要

[查看详情页]  →  {APP_BASE_URL}/summary/{summary_id}

─────────────────────────────
{summary.md 的摘要部分（## 摘要 之后到下一个 ## 之前的内容）}
─────────────────────────────

发布时间：{pub_time}
原文链接：{source_url}
生成时间：{generated_at}
```

---

## 前端变更（DetailView.vue）

### 5. 补发邮件区域

在详情页 Markdown 内容下方增加一个独立卡片区域，仅当 `email_enabled = true` 时渲染：

```
─── 发送摘要到邮箱 ───────────────────────────────
收件地址  [________________________]  [发送]
```

交互细节：
- 输入框 `type="email"`，HTML5 格式校验
- 点击「发送」后按钮变为禁用并显示「发送中...」
- 成功：展示绿色提示「📧 已发送至 xxx@xxx.com」，5 秒后提示淡出，输入框清空
- 失败：展示红色提示「发送失败：[错误信息]」，输入框内容保留便于重试
- 每次点击重置上一次的结果提示

### 6. 服务端配置获取

`DetailView.vue` 的 `onMounted` 中调用 `GET /api/config`，与 `HomeView.vue` 共享同一个 `getConfig()` API 函数。
（可选优化：将 `email_enabled` 提升到全局状态 `auth.js` 中，仅在应用启动时获取一次，避免重复请求。）

---

## 文件改动清单

| 文件 | 改动 |
|---|---|
| `app.py` | 新增 SMTP 配置常量、`EMAIL_ENABLED` 标志、`GET /api/config`、`send_summary_email()`、`POST /api/summaries/<id>/send-email`、`_worker` 中触发邮件、任务响应新增邮件字段 |
| `frontend/src/api/index.js` | 新增 `getConfig()`、`sendEmail(summaryId, email)` 函数 |
| `frontend/src/views/HomeView.vue` | 获取服务端配置、表单新增邮件选项、提交时附带 `notify_email`、状态展示增加邮件结果 |
| `frontend/src/views/DetailView.vue` | 获取服务端配置、底部新增补发邮件卡片 |
| `.env.example` | 新增 SMTP 相关变量和 `APP_BASE_URL` 说明 |
| `requirements.txt` | 无新依赖（smtplib 为标准库） |

---

## 不在范围内

- 邮件模板自定义（固定模板）
- 多收件人
- 附件（不附带图片）
- 失败重试（单次发送，失败记录到任务状态）
- 发件历史记录
