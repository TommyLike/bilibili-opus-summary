# 登录鉴权方案

## 目标

- 所有页面和 API 均需登录后才能访问
- 防止密码爆破
- 实现简单，不引入额外数据库或第三方依赖

---

## 整体方案

**单密码 + Flask Session Cookie + 内存速率限制器**

| 维度 | 选择 | 理由 |
|---|---|---|
| 认证方式 | 单密码（无用户名） | 个人工具，无多用户需求 |
| 会话存储 | Flask Session（签名 Cookie） | 无需额外存储，天然支持 |
| 反爆破 | 内存速率限制（IP 维度） | 无需 Redis，重启清零可接受 |
| 前端状态 | App.vue 挂载时检查，覆盖所有路由 | 比路由守卫更简单 |

---

## 后端变更（app.py）

### 1. 新增环境变量

```
AUTH_PASSWORD=your_strong_password   # 必填，登录密码
SESSION_SECRET_KEY=random_hex_string # 必填，Cookie 签名密钥
```

启动时若两者缺失则打印警告并退出。

### 2. 速率限制器（内存）

```
结构：RATE_LIMIT = { ip: {count, locked_until, window_start} }
规则：
  - 5 分钟内连续失败 ≥ 5 次 → 锁定 IP 15 分钟
  - 锁定期间直接返回 429，不再检查密码
  - 登录成功 → 清除该 IP 的计数
```

### 3. 新增路由

| 路由 | 方法 | 说明 | 是否需要登录 |
|---|---|---|---|
| `/api/auth/login` | POST | 验证密码，写 session | 否 |
| `/api/auth/logout` | POST | 清除 session | 否 |
| `/api/auth/check` | GET | 返回登录状态 | 否 |

请求体（login）：`{ "password": "xxx" }`

响应（login 成功）：`200 { "ok": true }`
响应（密码错误）：`401 { "error": "密码错误" }`
响应（被限流）：`429 { "error": "尝试次数过多，请 X 分钟后再试" }`

### 4. 鉴权装饰器

新增 `require_auth` 装饰器，应用于所有现有 API 路由：

```
GET  /api/summaries          → require_auth
GET  /api/summaries/<id>     → require_auth
POST /api/tasks              → require_auth
GET  /api/tasks/<task_id>    → require_auth
GET  /output/<path>          → require_auth
```

未登录时统一返回 `401 { "error": "未登录" }`。

### 5. Session 配置

```python
app.secret_key = SESSION_SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 7天
```

HTTPS 环境下额外启用 `SESSION_COOKIE_SECURE = True`（通过 `HTTPS=true` env 控制）。

---

## 前端变更

### 1. App.vue — 挂载时检查登录状态

```
onMounted → GET /api/auth/check
  → 200: isLoggedIn = true，正常渲染 <RouterView>
  → 401: isLoggedIn = false，渲染 <LoginPanel>（内联组件，不走路由）
```

### 2. LoginPanel（内联于 App.vue 或独立组件）

- 单密码输入框 + 提交按钮
- 显示错误信息（密码错误 / 被限流 / 剩余等待时间）
- 登录成功后 `isLoggedIn = true`，`<RouterView>` 自动显示

### 3. axios 全局拦截器（api/index.js）

```
响应拦截：状态码 401 → isLoggedIn = false（触发重新显示登录界面）
```

无需重定向，直接切换 App.vue 的显示状态。

### 4. 登出

在 App.vue 顶部导航栏增加「登出」按钮：
`POST /api/auth/logout → isLoggedIn = false`

---

## 文件改动清单

| 文件 | 改动 |
|---|---|
| `app.py` | 添加 session 配置、速率限制器、3 个 auth 路由、`require_auth` 装饰器；现有路由加装饰器 |
| `frontend/src/App.vue` | 添加登录状态检查、LoginPanel 渲染逻辑、登出按钮 |
| `frontend/src/api/index.js` | 添加 `loginApi` / `logoutApi` / `checkAuthApi` 函数；添加 401 响应拦截 |
| `.env.example` | 新增 `AUTH_PASSWORD` 和 `SESSION_SECRET_KEY` 说明 |
| `requirements.txt` | 无新依赖（Flask session 内置） |

---

## 不在范围内

- 多用户 / 角色权限
- 密码修改界面（直接改 .env 重启）
- 持久化速率限制（服务重启后计数归零，可接受）
- JWT / OAuth（过于复杂，不适合此场景）
