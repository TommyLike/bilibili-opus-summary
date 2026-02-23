#!/usr/bin/env python3
"""
Bilibili Summary Web Service — Flask 后端

路由：
  POST /api/auth/login                    登录
  POST /api/auth/logout                   登出
  GET  /api/auth/check                    检查登录状态
  GET  /api/config                        服务端能力标志（公开）
  GET  /api/summaries                     历史摘要列表
  GET  /api/summaries/<id>                摘要详情
  POST /api/summaries/<id>/send-email     详情页补发邮件
  POST /api/tasks                         提交新任务
  GET  /api/tasks/<task_id>               查询任务状态
  GET  /output/<path>                     静态文件（图片）
  GET  /                                  返回 Vue index.html
"""

import html as _html
import json
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
import uuid
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, abort, session
from flask_cors import CORS

from bilibili_summary import extract_post_id, get_config, run_summary

# ---------------------------------------------------------------------------
# 应用初始化
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app, supports_credentials=True)

OUTPUT_DIR = Path("output")

TASKS: dict = {}
TASKS_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# 鉴权配置
# ---------------------------------------------------------------------------

AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")
_raw_secret = os.getenv("SESSION_SECRET_KEY", "")

if not _raw_secret:
    _raw_secret = secrets.token_hex(32)
    print("[WARNING] SESSION_SECRET_KEY 未设置，已随机生成。服务重启后所有会话将失效，"
          "建议在 .env 中固定设置。")

if not AUTH_PASSWORD:
    print("[WARNING] AUTH_PASSWORD 未设置，所有登录请求将被拒绝。请在 .env 中配置。")

app.secret_key = _raw_secret
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

if os.getenv("HTTPS", "").lower() == "true":
    app.config["SESSION_COOKIE_SECURE"] = True

# ---------------------------------------------------------------------------
# 速率限制器（内存，IP 维度）
# ---------------------------------------------------------------------------

_RATE_LIMIT: dict = {}
_RATE_LOCK = threading.Lock()
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_LOCKOUT_SECONDS = 900


def _get_client_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limit(ip: str):
    now = time.time()
    with _RATE_LOCK:
        record = _RATE_LIMIT.get(ip)
        if record is None:
            return True, 0
        locked_until = record.get("locked_until", 0)
        if locked_until > now:
            return False, int(locked_until - now)
        if now - record.get("window_start", 0) > _WINDOW_SECONDS:
            del _RATE_LIMIT[ip]
            return True, 0
        return True, 0


def _record_failure(ip: str):
    now = time.time()
    with _RATE_LOCK:
        record = _RATE_LIMIT.get(ip)
        if record is None or now - record.get("window_start", 0) > _WINDOW_SECONDS:
            _RATE_LIMIT[ip] = {"count": 1, "window_start": now, "locked_until": 0}
        else:
            record["count"] += 1
            if record["count"] >= _MAX_ATTEMPTS:
                record["locked_until"] = now + _LOCKOUT_SECONDS


def _clear_rate_limit(ip: str):
    with _RATE_LOCK:
        _RATE_LIMIT.pop(ip, None)

# ---------------------------------------------------------------------------
# 邮件配置
# ---------------------------------------------------------------------------

SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM", "") or SMTP_USER
APP_BASE_URL  = os.getenv("APP_BASE_URL", "http://localhost:5000").rstrip("/")

EMAIL_ENABLED = all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD])

if not EMAIL_ENABLED:
    print("[INFO] 邮件功能未启用（SMTP_HOST / SMTP_USER / SMTP_PASSWORD 未全部配置）。")


def _extract_summary_section(summary_id: str) -> str:
    """从 summary.md 中提取 ## 摘要 小节的纯文字。"""
    md_path = OUTPUT_DIR / summary_id / "summary.md"
    if not md_path.exists():
        return ""
    lines = md_path.read_text(encoding="utf-8").split("\n")
    in_section, result = False, []
    for line in lines:
        if re.match(r"^##\s+摘要", line):
            in_section = True
            continue
        if in_section and (line.startswith("## ") or line.strip() == "---"):
            break
        if in_section:
            result.append(line)
    return "\n".join(result).strip()


def _sender_addr() -> str:
    """从 'Display Name <addr>' 格式中提取实际邮件地址。"""
    m = re.search(r"<([^>]+)>", SMTP_FROM)
    return m.group(1) if m else SMTP_FROM.strip() or SMTP_USER


def send_summary_email(to_addr: str, summary_id: str) -> None:
    """
    发送摘要邮件到指定地址。失败时抛出异常。
    在任务线程中和详情页补发接口中共用。
    """
    raw_path = OUTPUT_DIR / summary_id / "raw.json"
    if not raw_path.exists():
        raise FileNotFoundError(f"raw.json 不存在: {summary_id}")

    raw          = json.loads(raw_path.read_text(encoding="utf-8"))
    author       = raw.get("author", "未知作者")
    pub_time     = raw.get("time", "")
    source_url   = raw.get("source_url", "")
    generated_at = raw.get("fetched_at", "")[:10]
    detail_url   = f"{APP_BASE_URL}/summary/{summary_id}"
    summary_text = _extract_summary_section(summary_id)

    subject = f"[Bilibili摘要] {author} · {pub_time}"

    # ---- 纯文本版本 ----
    plain = (
        f"{author} 的 Bilibili 动态摘要\n\n"
        f"查看详情页：{detail_url}\n\n"
        f"{'─' * 40}\n"
        f"{summary_text}\n"
        f"{'─' * 40}\n\n"
        f"发布时间：{pub_time}\n"
        f"原文链接：{source_url}\n"
        f"生成时间：{generated_at}\n"
    )

    # ---- HTML 版本 ----
    summary_html = "".join(
        f"<p style='margin:8px 0;line-height:1.7'>{_html.escape(line)}</p>"
        for line in summary_text.split("\n") if line.strip()
    )
    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f5f5f5;padding:24px;color:#333;">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
              padding:28px;box-shadow:0 1px 4px rgba(0,0,0,.08);">
    <h2 style="color:#00a1d6;margin:0 0 16px;font-size:20px;
               border-bottom:2px solid #00a1d6;padding-bottom:10px;">
      {_html.escape(author)} 的 Bilibili 动态摘要
    </h2>
    <p style="margin:0 0 20px;">
      <a href="{detail_url}"
         style="display:inline-block;background:#00a1d6;color:#fff;
                padding:10px 22px;border-radius:8px;text-decoration:none;font-weight:600;">
        查看详情页 →
      </a>
    </p>
    <div style="background:#f0f9ff;border-left:4px solid #00a1d6;
                padding:16px 20px;border-radius:0 8px 8px 0;margin-bottom:20px;">
      {summary_html}
    </div>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <div style="font-size:13px;color:#999;line-height:2;">
      <div>发布时间：{_html.escape(pub_time)}</div>
      <div>原文链接：
        <a href="{source_url}" style="color:#00a1d6;">{_html.escape(source_url)}</a>
      </div>
      <div>生成时间：{_html.escape(generated_at)}</div>
    </div>
  </div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = to_addr
    msg.attach(MIMEText(plain,     "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    ctx = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as smtp:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.sendmail(_sender_addr(), [to_addr], msg.as_bytes())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.sendmail(_sender_addr(), [to_addr], msg.as_bytes())


# ---------------------------------------------------------------------------
# 鉴权装饰器
# ---------------------------------------------------------------------------

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "未登录"}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# 鉴权路由（公开）
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
def auth_login():
    ip = _get_client_ip()
    allowed, retry_after = _check_rate_limit(ip)
    if not allowed:
        minutes = (retry_after + 59) // 60
        return jsonify({"error": f"尝试次数过多，请 {minutes} 分钟后再试"}), 429

    if not AUTH_PASSWORD:
        return jsonify({"error": "服务未配置 AUTH_PASSWORD，请联系管理员"}), 500

    body = request.get_json(silent=True) or {}
    password = body.get("password", "")

    if not secrets.compare_digest(password, AUTH_PASSWORD):
        _record_failure(ip)
        allowed, retry_after = _check_rate_limit(ip)
        if not allowed:
            minutes = (retry_after + 59) // 60
            return jsonify({"error": f"尝试次数过多，请 {minutes} 分钟后再试"}), 429
        return jsonify({"error": "密码错误"}), 401

    _clear_rate_limit(ip)
    session.permanent = True
    session["logged_in"] = True
    return jsonify({"ok": True})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/check")
def auth_check():
    if session.get("logged_in"):
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False}), 401


# ---------------------------------------------------------------------------
# 服务端能力配置（公开）
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_server_config():
    """返回前端所需的服务端能力标志，无需登录。"""
    return jsonify({"email_enabled": EMAIL_ENABLED})


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _load_raw(summary_id: str):
    raw_path = OUTPUT_DIR / summary_id / "raw.json"
    if not raw_path.exists():
        return None
    try:
        return json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_summary_md(summary_id: str):
    md_path = OUTPUT_DIR / summary_id / "summary.md"
    if not md_path.exists():
        return None
    try:
        return md_path.read_text(encoding="utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API 路由（均需登录）
# ---------------------------------------------------------------------------

@app.get("/api/summaries")
@require_auth
def list_summaries():
    summaries = []
    if OUTPUT_DIR.exists():
        for raw_path in sorted(OUTPUT_DIR.glob("*/raw.json"), reverse=True):
            summary_id = raw_path.parent.name
            try:
                data = json.loads(raw_path.read_text(encoding="utf-8"))
                summaries.append({
                    "id": summary_id,
                    "author": data.get("author", ""),
                    "time": data.get("time", ""),
                    "fetched_at": data.get("fetched_at", ""),
                    "source_url": data.get("source_url", ""),
                    "cover_image_local": data.get("cover_image_local", ""),
                })
            except Exception:
                continue
    return jsonify(summaries)


@app.get("/api/summaries/<summary_id>")
@require_auth
def get_summary(summary_id: str):
    if not re.match(r'^[\w\u4e00-\u9fff\-]+$', summary_id):
        abort(400, "无效的 summary_id")

    raw = _load_raw(summary_id)
    if raw is None:
        abort(404, f"摘要不存在: {summary_id}")

    return jsonify({
        "id": summary_id,
        "author": raw.get("author", ""),
        "time": raw.get("time", ""),
        "fetched_at": raw.get("fetched_at", ""),
        "source_url": raw.get("source_url", ""),
        "cover_image_local": raw.get("cover_image_local", ""),
        "summary_md": _load_summary_md(summary_id) or "",
    })


@app.post("/api/summaries/<summary_id>/send-email")
@require_auth
def send_summary_email_api(summary_id: str):
    """详情页补发邮件：对已生成摘要立即发送邮件。"""
    if not re.match(r'^[\w\u4e00-\u9fff\-]+$', summary_id):
        abort(400, "无效的 summary_id")

    if not EMAIL_ENABLED:
        return jsonify({"error": "邮件功能未配置，请在服务端设置 SMTP 环境变量"}), 503

    body  = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()

    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({"error": "邮件地址格式不正确"}), 400

    if _load_raw(summary_id) is None:
        abort(404, f"摘要不存在: {summary_id}")

    try:
        send_summary_email(email, summary_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/tasks")
@require_auth
def create_task():
    body = request.get_json(silent=True) or {}

    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url 不能为空"}), 400

    if not extract_post_id(url):
        return jsonify({"error": f"无法从 URL 中提取动态 ID，请确认格式正确: {url}"}), 400

    try:
        config = get_config(overrides={
            "sessdata":       body.get("sessdata"),
            "bili_jct":       body.get("bili_jct"),
            "buvid3":         body.get("buvid3"),
            "gemini_api_key": body.get("gemini_api_key"),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    notify_email = (body.get("notify_email") or "").strip()

    task_id = str(uuid.uuid4())
    with TASKS_LOCK:
        TASKS[task_id] = {"status": "pending", "error": None, "result": None}

    def _worker():
        with TASKS_LOCK:
            TASKS[task_id]["status"] = "running"
        try:
            result = run_summary(url, config, force=body.get("force", False))

            # 在标记 done 前发送邮件，确保前端轮询到 done 时 email_sent 已就绪
            if notify_email and EMAIL_ENABLED:
                sid = result.get("summary_id", "")
                try:
                    send_summary_email(notify_email, sid)
                    email_sent, email_err = True, None
                except Exception as e_mail:
                    email_sent, email_err = False, str(e_mail)
            else:
                email_sent, email_err = None, None

            with TASKS_LOCK:
                TASKS[task_id]["status"] = "done"
                TASKS[task_id]["result"] = result
                if email_sent is not None:
                    TASKS[task_id]["email_sent"]  = email_sent
                    TASKS[task_id]["email_error"] = email_err

        except Exception as e:
            with TASKS_LOCK:
                TASKS[task_id]["status"] = "error"
                TASKS[task_id]["error"]  = str(e)

    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"task_id": task_id, "status": "pending"}), 202


@app.get("/api/tasks/<task_id>")
@require_auth
def get_task(task_id: str):
    with TASKS_LOCK:
        task = TASKS.get(task_id)
    if task is None:
        abort(404, f"任务不存在: {task_id}")
    return jsonify({"task_id": task_id, **task})


# ---------------------------------------------------------------------------
# 静态文件
# ---------------------------------------------------------------------------

@app.get("/output/<path:filename>")
@require_auth
def serve_output(filename: str):
    return send_from_directory(OUTPUT_DIR, filename)


# ---------------------------------------------------------------------------
# Vue SPA 回退（生产模式）
# ---------------------------------------------------------------------------

@app.get("/")
@app.get("/<path:path>")
def serve_spa(path: str = ""):
    if app.static_folder and (Path(app.static_folder) / "index.html").exists():
        return send_from_directory(app.static_folder, "index.html")
    return jsonify({"message": "Bilibili Summary API 服务运行中，前端请访问 http://localhost:5173"}), 200


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port  = int(os.getenv("PORT", "6000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
