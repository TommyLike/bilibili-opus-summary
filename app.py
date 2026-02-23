#!/usr/bin/env python3
"""
Bilibili Summary Web Service — Flask 后端

路由：
  POST /api/auth/login         登录
  POST /api/auth/logout        登出
  GET  /api/auth/check         检查登录状态
  GET  /api/summaries          历史摘要列表
  GET  /api/summaries/<id>     摘要详情
  POST /api/tasks              提交新任务
  GET  /api/tasks/<task_id>    查询任务状态
  GET  /output/<path>          静态文件（图片）
  GET  /                       返回 Vue index.html
"""

import json
import os
import secrets
import threading
import time
import uuid
from datetime import timedelta
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

# 内存任务状态存储：task_id -> {status, error, result}
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

# {ip: {"count": int, "window_start": float, "locked_until": float}}
_RATE_LIMIT: dict = {}
_RATE_LOCK = threading.Lock()

_MAX_ATTEMPTS = 5       # 窗口内最大失败次数
_WINDOW_SECONDS = 300   # 计数窗口：5 分钟
_LOCKOUT_SECONDS = 900  # 锁定时长：15 分钟


def _get_client_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limit(ip: str):
    """
    检查 IP 是否被限流。

    Returns:
        (allowed: bool, retry_after_seconds: int)
    """
    now = time.time()
    with _RATE_LOCK:
        record = _RATE_LIMIT.get(ip)
        if record is None:
            return True, 0

        locked_until = record.get("locked_until", 0)
        if locked_until > now:
            return False, int(locked_until - now)

        # 计数窗口已过期，视为干净
        if now - record.get("window_start", 0) > _WINDOW_SECONDS:
            del _RATE_LIMIT[ip]
            return True, 0

        return True, 0


def _record_failure(ip: str):
    """记录一次登录失败，必要时触发锁定。"""
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
    """登录成功后清除该 IP 的限流记录。"""
    with _RATE_LOCK:
        _RATE_LIMIT.pop(ip, None)


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
# 鉴权路由（公开，不需要 require_auth）
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
def auth_login():
    """验证密码，写入 session。"""
    ip = _get_client_ip()

    # 速率限制检查
    allowed, retry_after = _check_rate_limit(ip)
    if not allowed:
        minutes = (retry_after + 59) // 60
        return jsonify({"error": f"尝试次数过多，请 {minutes} 分钟后再试"}), 429

    if not AUTH_PASSWORD:
        return jsonify({"error": "服务未配置 AUTH_PASSWORD，请联系管理员"}), 500

    body = request.get_json(silent=True) or {}
    password = body.get("password", "")

    # 使用常数时间比较，防止时序攻击
    if not secrets.compare_digest(password, AUTH_PASSWORD):
        _record_failure(ip)
        # 失败后再次检查是否触发了锁定
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
    """清除 session。"""
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/check")
def auth_check():
    """检查当前 session 是否有效。"""
    if session.get("logged_in"):
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False}), 401


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
    """返回历史摘要列表，扫描 output/*/raw.json"""
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
    """返回摘要详情：raw.json 元数据 + summary.md 内容"""
    import re
    if not re.match(r'^[\w\u4e00-\u9fff\-]+$', summary_id):
        abort(400, "无效的 summary_id")

    raw = _load_raw(summary_id)
    if raw is None:
        abort(404, f"摘要不存在: {summary_id}")

    summary_md = _load_summary_md(summary_id)

    return jsonify({
        "id": summary_id,
        "author": raw.get("author", ""),
        "time": raw.get("time", ""),
        "fetched_at": raw.get("fetched_at", ""),
        "source_url": raw.get("source_url", ""),
        "cover_image_local": raw.get("cover_image_local", ""),
        "summary_md": summary_md or "",
    })


@app.post("/api/tasks")
@require_auth
def create_task():
    """提交新摘要任务，异步执行，返回 task_id"""
    body = request.get_json(silent=True) or {}

    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url 不能为空"}), 400

    if not extract_post_id(url):
        return jsonify({"error": f"无法从 URL 中提取动态 ID，请确认格式正确: {url}"}), 400

    try:
        config = get_config(overrides={
            "sessdata": body.get("sessdata"),
            "bili_jct": body.get("bili_jct"),
            "buvid3": body.get("buvid3"),
            "gemini_api_key": body.get("gemini_api_key"),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    task_id = str(uuid.uuid4())
    with TASKS_LOCK:
        TASKS[task_id] = {"status": "pending", "error": None, "result": None}

    def _worker():
        with TASKS_LOCK:
            TASKS[task_id]["status"] = "running"
        try:
            result = run_summary(url, config, force=body.get("force", False))
            with TASKS_LOCK:
                TASKS[task_id]["status"] = "done"
                TASKS[task_id]["result"] = result
        except Exception as e:
            with TASKS_LOCK:
                TASKS[task_id]["status"] = "error"
                TASKS[task_id]["error"] = str(e)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    return jsonify({"task_id": task_id, "status": "pending"}), 202


@app.get("/api/tasks/<task_id>")
@require_auth
def get_task(task_id: str):
    """查询任务状态"""
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
    """提供 output/ 目录下的静态文件（图片等）"""
    return send_from_directory(OUTPUT_DIR, filename)


# ---------------------------------------------------------------------------
# Vue SPA 回退（生产模式）
# ---------------------------------------------------------------------------

@app.get("/")
@app.get("/<path:path>")
def serve_spa(path: str = ""):
    """非 API 路由均返回 Vue 的 index.html"""
    if app.static_folder and (Path(app.static_folder) / "index.html").exists():
        return send_from_directory(app.static_folder, "index.html")
    return jsonify({"message": "Bilibili Summary API 服务运行中，前端请访问 http://localhost:5173"}), 200


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "6000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
