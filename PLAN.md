# Bilibili 动态内容抓取与图片识别摘要脚本

## 项目概述

输入一条 Bilibili 动态 URL，脚本将：
1. 通过 Cookie 认证调用 Bilibili API 获取该动态内容
2. 提取正文文字和图片
3. 对图片调用 Claude API 进行图像识别，生成文字描述
4. 将所有内容汇总，生成一份中文摘要
5. 保存为 Markdown 文件，文件名基于作者名和发布日期

---

## 文件结构

```
/Users/husheng/codes/bilibili_summary/
├── bilibili_summary.py     # 主脚本（单文件实现）
├── .env                    # 环境变量（Cookie、API Key，不提交 git）
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── PLAN.md                 # 本文件
└── output/                 # 输出目录（自动创建）
    └── {作者名}_{YYYYMMDD}/
        ├── raw.json        # 原始抓取数据 + 图片描述（缓存）
        ├── images/         # 下载的原始图片（便于人工核查）
        │   ├── 1.jpg
        │   └── ...
        └── summary.md      # 最终摘要
```

---

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入真实的 Cookie 和 API Key
```

**如何获取 Bilibili Cookie：**
1. 浏览器登录 [bilibili.com](https://www.bilibili.com)
2. 打开开发者工具（F12）→ Application → Cookies → `www.bilibili.com`
3. 复制 `SESSDATA`、`bili_jct`、`buvid3` 的值

### 3. 运行

```bash
# 基本用法（输出到 output/{作者}_{日期}.md）
python bilibili_summary.py https://www.bilibili.com/opus/1171504724323598370

# 指定输出文件
python bilibili_summary.py https://www.bilibili.com/opus/1171504724323598370 --output my_note.md
```

---

## 实现流程

### Step 1: 配置管理

从 `.env` 或系统环境变量读取：

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `BILIBILI_SESSDATA` | B站登录 Cookie | 是 |
| `BILIBILI_BILI_JCT` | B站 CSRF Token | 否 |
| `BILIBILI_BUVID3` | 浏览器唯一标识 | 否 |
| `GEMINI_API_KEY` | Google Gemini API Key（图片识别 + 摘要） | 是 |

命令行参数：
- `url`（位置参数）— Bilibili 动态 URL
- `--force` — 忽略缓存，强制重新抓取并识别

### Step 2: 提取动态 ID 并请求 API

支持的 URL 格式：
- `https://www.bilibili.com/opus/{id}`
- `https://t.bilibili.com/{id}`

**API Endpoint**: `GET https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?id={id}`

解析字段：
- 文本: `data.item.modules.module_dynamic.desc.text`
- 图片: `data.item.modules.module_dynamic.major.draw.items[].src`
- 作者: `data.item.modules.module_author.name`
- 时间: `data.item.modules.module_author.pub_time`

### Step 3: 图片下载与识别（Google Gemini API）

- 模型：`gemini-2.0-flash`（图片识别 + 摘要生成统一使用）
- 流程：下载图片 → 保存到 `images/` → 用 Pillow 解析 → 调用 Gemini 多模态接口
- 提示词：识别图片中的文字、图表、场景等关键信息
- 每张图片识别后等待 0.5 秒防止限流
- 单张图片失败不中断整体流程

### Step 3.5: 保存原始数据（缓存）

识别完成后立即写入 `raw.json`，包含：
- 动态文本、图片 URL 列表、图片描述列表
- 数据来源 URL、抓取时间戳

**缓存逻辑**：再次处理同一 URL 时，扫描 `output/*/raw.json` 找到匹配缓存，直接跳过 Bilibili 请求和图片识别步骤，只重新生成摘要。使用 `--force` 可强制刷新。

### Step 4: 生成摘要（Google Gemini API）

将正文 + 图片描述合并后，调用 Gemini API 生成摘要：
- 概括核心内容和主要观点
- 提炼关键信息
- 整合图片与文字内容

### Step 5: 输出 Markdown

文件名规则：`output/{作者名}_{YYYYMMDD}.md`
- 作者名去除特殊字符，截断至 40 字符
- 日期从 `pub_time` 中提取，无法提取时使用当天日期

输出格式：
```markdown
# {作者名} - Bilibili 动态摘要

> 来源：{url}
> 发布时间：...
> 生成时间：...

---

## 摘要

...

---

## 原始内容

**正文**：...

**图片内容**：
- 图片1：...
```

---

## 技术依赖

```
requests>=2.31
google-generativeai>=0.8  # 图片识别 + 摘要生成
Pillow>=10.0              # 图片解析
python-dotenv>=1.0
```

---

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **单文件脚本** | 简洁，无需复杂项目结构 |
| **URL 作为输入** | 明确指向单条动态，避免批量抓取的封号风险 |
| **统一使用 Gemini** | 图片识别和摘要生成均用 Gemini，只需配置一个 API Key |
| **图片保存到本地** | 下载原图至 `images/`，便于人工核查图片识别结果 |
| **raw.json 缓存** | 避免重复调用 API，同时保留原始数据供人工修正 |
| **错误容错** | 单张图片识别失败不中断流程 |
| **目录语义化** | 基于作者名 + 日期，便于后续检索 |

---

## Web 服务部署

项目已升级为 Vue 3 前端 + Flask 后端的 Web 服务，支持 Docker 部署。

### 项目结构

```
bilibili_summary/
├── app.py                     # Flask 后端
├── bilibili_summary.py        # 核心逻辑（含 run_summary()）
├── frontend/                  # Vue 3 + Vite 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/index.js
│       ├── api/index.js
│       └── views/
│           ├── HomeView.vue    # 历史列表
│           ├── NewView.vue     # 新建表单
│           └── DetailView.vue  # 摘要详情
├── output/                    # 生成文件
├── requirements.txt           # Python 依赖（含 flask、flask-cors）
├── Dockerfile                 # 多阶段构建
└── docker-compose.yml
```

### 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `BILIBILI_SESSDATA` | B站登录 Cookie | 是 |
| `BILIBILI_BILI_JCT` | B站 CSRF Token | 否 |
| `BILIBILI_BUVID3` | 浏览器唯一标识 | 否 |
| `GEMINI_API_KEY` | Google Gemini API Key | 是 |

Web 界面也支持在表单中直接填写这些值，优先级高于 .env 配置。

### 开发模式启动

```bash
# 1. 启动 Flask 后端（端口 5000）
pip install -r requirements.txt
python app.py

# 2. 启动 Vue 前端（端口 5173，代理 /api 到 :5000）
cd frontend
npm install
npm run dev
```

前端访问 http://localhost:5173，API 请求自动代理到后端。

### Docker 构建与运行

```bash
# 一键构建并启动
docker compose up --build

# 访问 http://localhost:5000
```

Docker 模式下，前端构建产物由 Flask 直接服务，无需单独运行前端。

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/summaries` | 历史摘要列表 |
| GET | `/api/summaries/<id>` | 摘要详情 |
| POST | `/api/tasks` | 提交新任务 |
| GET | `/api/tasks/<task_id>` | 查询任务状态 |
| GET | `/output/<path>` | 静态文件（图片）|

---

## 后续扩展方向

- [ ] 支持批量处理多个 URL（从文件或命令行传入列表）
- [ ] 支持转发动态（`DYNAMIC_TYPE_FORWARD`）的原文提取
- [ ] 支持视频动态（`DYNAMIC_TYPE_AV`）的标题/简介提取
- [ ] 支持将摘要推送到通知渠道（微信、邮件、Telegram 等）
- [ ] 增量记录已处理的 URL，避免重复处理
- [ ] 任务持久化（SQLite），避免重启后丢失任务状态
