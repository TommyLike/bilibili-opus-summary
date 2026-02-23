#!/usr/bin/env python3
"""
Bilibili Summary Web Service — Flask 后端

路由：
  GET  /api/summaries          历史摘要列表
  GET  /api/summaries/<id>     摘要详情
  POST /api/tasks              提交新任务
  GET  /api/tasks/<task_id>    查询任务状态
  GET  /output/<path>          静态文件（图片）
  GET  /                       返回 Vue index.html
"""

import json
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

from bilibili_summary import extract_post_id, get_config, run_summary

# ---------------------------------------------------------------------------
# 应用初始化
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

OUTPUT_DIR = Path("output")

# 内存任务状态存储：task_id -> {status, error, result}
TASKS: dict = {}
TASKS_LOCK = threading.Lock()


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
# API 路由
# ---------------------------------------------------------------------------

@app.get("/api/summaries")
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
def get_summary(summary_id: str):
    """返回摘要详情：raw.json 元数据 + summary.md 内容"""
    # 安全校验：只允许字母数字下划线中文
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
def create_task():
    """提交新摘要任务，异步执行，返回 task_id"""
    body = request.get_json(silent=True) or {}

    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url 不能为空"}), 400

    if not extract_post_id(url):
        return jsonify({"error": f"无法从 URL 中提取动态 ID，请确认格式正确: {url}"}), 400

    # 构建配置（API 传参优先于 env）
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
    # 如果 static 目录存在 index.html，说明是生产模式
    if app.static_folder and (Path(app.static_folder) / "index.html").exists():
        return send_from_directory(app.static_folder, "index.html")
    # 开发模式下无 static/index.html，返回提示
    return jsonify({"message": "Bilibili Summary API 服务运行中，前端请访问 http://localhost:5173"}), 200


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "6000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
