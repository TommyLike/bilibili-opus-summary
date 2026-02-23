#!/usr/bin/env python3
"""
Bilibili 动态内容抓取与图片识别摘要脚本

用法：
    python bilibili_summary.py <bilibili_url>
    python bilibili_summary.py https://www.bilibili.com/opus/1171504724323598370

输出目录结构：
    output/{作者名}_{YYYYMMDD}/
    ├── raw.json        # 抓取的原始数据 + 图片描述（用于缓存）
    ├── images/         # 下载的原始图片（便于人工核查）
    │   ├── 1.jpg
    │   └── ...
    └── summary.md      # 最终摘要
"""

import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

# Bilibili API
BILIBILI_DETAIL_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def get_config(overrides: dict = None) -> dict:
    """从环境变量读取配置，overrides 中的非空值优先于 env"""
    overrides = overrides or {}

    config = {
        "sessdata": overrides.get("sessdata") or os.getenv("BILIBILI_SESSDATA", ""),
        "bili_jct": overrides.get("bili_jct") or os.getenv("BILIBILI_BILI_JCT", ""),
        "buvid3": overrides.get("buvid3") or os.getenv("BILIBILI_BUVID3", ""),
        "gemini_api_key": overrides.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", ""),
    }

    missing = []
    if not config["sessdata"]:
        missing.append("BILIBILI_SESSDATA")
    if not config["gemini_api_key"]:
        missing.append("GEMINI_API_KEY")

    if missing:
        raise ValueError(f"缺少必要的配置项: {', '.join(missing)}，请在 .env 文件或请求参数中提供")

    return config


def build_cookies(config):
    """构建 Cookie 字典"""
    cookies = {"SESSDATA": config["sessdata"]}
    if config["bili_jct"]:
        cookies["bili_jct"] = config["bili_jct"]
    if config["buvid3"]:
        cookies["buvid3"] = config["buvid3"]
    return cookies


# ---------------------------------------------------------------------------
# URL 解析
# ---------------------------------------------------------------------------

def extract_post_id(url):
    """
    从 Bilibili URL 中提取动态 ID

    支持格式：
      https://www.bilibili.com/opus/1171504724323598370
      https://t.bilibili.com/1171504724323598370
      1171504724323598370（纯 ID）
    """
    m = re.search(r"/opus/(\d+)", url)
    if m:
        return m.group(1)

    m = re.search(r"t\.bilibili\.com/(\d+)", url)
    if m:
        return m.group(1)

    if re.fullmatch(r"\d+", url.strip()):
        return url.strip()

    return None


# ---------------------------------------------------------------------------
# Bilibili 抓取
# ---------------------------------------------------------------------------

def fetch_post(post_id, cookies):
    """通过 API 获取单条动态详情，返回原始 item 或 None"""
    print(f"正在获取动态 ID: {post_id} ...")
    try:
        resp = requests.get(
            BILIBILI_DETAIL_API,
            params={"id": post_id, "timezone_offset": "-480"},
            headers=HEADERS,
            cookies=cookies,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

    if data.get("code") != 0:
        print(f"API 返回错误: {data.get('message', '未知错误')} (code={data.get('code')})")
        return None

    item = data.get("data", {}).get("item")
    if not item:
        print("未找到动态内容")
        return None

    return item


def parse_post(item):
    """解析动态 item，返回结构化数据"""
    modules = item.get("modules", {})
    module_author = modules.get("module_author", {})
    module_dynamic = modules.get("module_dynamic", {})

    author = module_author.get("name", "未知用户")
    pub_time = module_author.get("pub_time", "")

    desc = module_dynamic.get("desc") or {}
    text = desc.get("text", "").strip()

    images = []
    if item.get("type") == "DYNAMIC_TYPE_DRAW":
        major = module_dynamic.get("major") or {}
        draw = major.get("draw") or {}
        images = [img["src"] for img in draw.get("items", []) if img.get("src")]

    return {
        "author": author,
        "time": pub_time,
        "text": text,
        "images": images,
        "cover_image_local": "",      # 相对路径，如 "images/1.jpg"，空表示无封面图
        "image_descriptions": [],     # 与 images 等长；封面图对应位置为空字符串
        "combined_text": "",
    }


# ---------------------------------------------------------------------------
# 图片处理
# ---------------------------------------------------------------------------

def download_image(url, save_path):
    """
    下载图片并保存到本地

    Returns:
        PIL.Image 对象，失败返回 None
    """
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"Referer": "https://www.bilibili.com/"},
        )
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        # 保存原始文件
        save_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(save_path))
        return img
    except Exception as e:
        print(f"  图片下载失败 ({url}): {e}")
        return None


def _img_to_part(img):
    """将 PIL.Image 转为 Gemini Part"""
    buf = io.BytesIO()
    fmt = img.format or "JPEG"
    img.save(buf, format=fmt)
    mime = f"image/{fmt.lower()}"
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    return types.Part.from_bytes(data=buf.getvalue(), mime_type=mime)


def classify_first_image(client, model, img):
    """
    判断第一张图片是封面图还是文字图，一次调用完成分类 + 提取。

    Returns:
        ("COVER", "")          — 封面/配图，无需提取文字
        ("TEXT", extracted)    — 文字图，返回提取的文字内容
    """
    prompt = (
        "请判断这张图片的主要类型，并按以下规则回复：\n\n"
        "规则1：如果这是封面图/宣传海报/配图（主要是人物照片、艺术设计、场景插图，"
        "文字内容很少或仅作装饰性标题），请只回复一个词：COVER\n\n"
        "规则2：如果这张图片主要包含大段可读文字（如文章截图、聊天记录、文档截图），"
        "请直接提取并返回图片中所有文字内容，保持原段落格式。\n\n"
        "只回复 COVER 或提取的文字，不需要任何其他说明。"
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=[_img_to_part(img), prompt],
        )
        text = response.text.strip()
        if text.upper() == "COVER" or text.upper().startswith("COVER\n"):
            return "COVER", ""
        return "TEXT", text
    except Exception as e:
        print(f"  图片分类出错: {e}")
        return "TEXT", ""


def extract_text_from_image(client, model, img):
    """
    从图片中提取所有文字内容（OCR）。

    Returns:
        提取的文字字符串，失败返回空字符串
    """
    prompt = (
        "请提取这张图片中的所有文字内容，保持原有段落格式，"
        "只返回文字，不需要任何描述或解释。"
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=[_img_to_part(img), prompt],
        )
        return response.text.strip()
    except Exception as e:
        print(f"  文字提取出错: {e}")
        return ""


def process_images(post, gemini_client, gemini_model, images_dir):
    """
    下载图片、识别内容，结果写入 post 字典。

    - 第一张图：判断是封面还是文字图
      - 封面 → 保存到 images/，设置 cover_image_local，image_descriptions 追加 ""
      - 文字 → 提取文字，追加到 image_descriptions
    - 其余图：直接提取文字，追加到 image_descriptions
    """
    if not post["images"]:
        return

    print(f"\n共 {len(post['images'])} 张图片，开始下载并识别...")
    for i, img_url in enumerate(post["images"], 1):
        save_path = images_dir / f"{i}.jpg"
        print(f"  [{i}/{len(post['images'])}] 下载图片...")
        img = download_image(img_url, save_path)

        if img is None:
            post["image_descriptions"].append("")
            continue

        if i == 1:
            # 第一张图：分类判断
            print(f"  [{i}/{len(post['images'])}] 判断图片类型（封面/文字）...")
            kind, text = classify_first_image(gemini_client, gemini_model, img)
            if kind == "COVER":
                post["cover_image_local"] = f"images/{save_path.name}"
                post["image_descriptions"].append("")
                print(f"  → 封面图，已设置为摘要封面")
            else:
                post["image_descriptions"].append(text)
                print(f"  → 文字图，提取文字 {len(text)} 字")
        else:
            # 其余图：提取文字
            print(f"  [{i}/{len(post['images'])}] 提取文字...")
            text = extract_text_from_image(gemini_client, gemini_model, img)
            post["image_descriptions"].append(text)
            if text:
                print(f"  提取 {len(text)} 字: {text[:60]}{'...' if len(text) > 60 else ''}")

        if i < len(post["images"]):
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# 原始数据缓存
# ---------------------------------------------------------------------------

def save_raw(post, source_url, output_dir):
    """将抓取结果保存为 raw.json"""
    raw = {
        "source_url": source_url,
        "fetched_at": datetime.now().isoformat(),
        "author": post["author"],
        "time": post["time"],
        "text": post["text"],
        "images": post["images"],
        "cover_image_local": post.get("cover_image_local", ""),
        "image_descriptions": post["image_descriptions"],
        "combined_text": post["combined_text"],
    }
    raw_path = output_dir / "raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  原始数据已保存: {raw_path}")


def load_raw(output_dir):
    """
    从 raw.json 加载已缓存的数据

    Returns:
        dict 或 None（文件不存在时）
    """
    raw_path = output_dir / "raw.json"
    if not raw_path.exists():
        return None
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 摘要生成
# ---------------------------------------------------------------------------

def generate_summary(gemini_client, gemini_model, post):
    """调用 Gemini API 生成摘要（基于图片提取的文字内容）"""
    content = post["combined_text"]
    if not content.strip():
        return "该动态无有效文字内容。"

    if len(content) > 50000:
        content = content[:50000] + "\n...(内容已截断)"

    prompt = f"""以下是从 Bilibili 用户「{post['author']}」动态图片中提取的文字内容：

{content}

请用中文生成一份简洁的摘要，要求：
1. 概括文章的核心观点和主要内容
2. 提炼关键信息、重要数据或独到见解
3. 保留重要的专有名词、人名和术语
4. 语言简洁，结构清晰，300-500字以内
"""

    print("\n正在生成摘要...")
    try:
        response = gemini_client.models.generate_content(
            model=gemini_model,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return f"摘要生成失败: {e}"


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def sanitize_filename(name):
    """将字符串转为安全的文件名片段"""
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = name.strip().replace(" ", "_")
    return name[:40] if name else "unknown"


def build_output_dir(post):
    """生成输出目录名：output/{作者名}_{YYYYMMDD}"""
    author = sanitize_filename(post["author"])
    t = post["time"]

    # 格式1：2026-02-20
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        date_str = m.group(1) + m.group(2) + m.group(3)
    else:
        # 格式2：2026年02月20日
        m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", t)
        if m:
            date_str = m.group(1) + m.group(2) + m.group(3)
        else:
            date_str = datetime.now().strftime("%Y%m%d")

    return Path("output") / f"{author}_{date_str}"


def build_markdown(post, summary, source_url):
    """构建 Markdown 输出内容"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cover = post.get("cover_image_local", "")

    lines = [
        f"# {post['author']} - Bilibili 动态摘要",
        f"\n> 来源：{source_url}  \n> 发布时间：{post['time']}  \n> 生成时间：{now}",
        "",
    ]

    # 封面图（相对路径，summary.md 与 images/ 同级）
    if cover:
        lines += [f"![封面]({cover})", ""]

    lines += [
        "\n---\n",
        "## 摘要\n",
        summary,
        "\n---\n",
        "## 原始内容\n",
    ]

    if post["text"]:
        lines.append("**正文**：\n")
        lines.append(post["text"])
        lines.append("")

    # 图片提取的文字（跳过封面图对应的空描述）
    text_images = [
        (i + 1, desc)
        for i, desc in enumerate(post["image_descriptions"])
        if desc and not (i == 0 and cover)
    ]
    if text_images:
        lines.append("\n**图片提取文字**：\n")
        for img_num, desc in text_images:
            lines.append(f"#### 图片 {img_num}\n")
            lines.append(desc)
            lines.append("")

    if not post["text"] and not text_images:
        lines.append("*（无有效文字内容）*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 核心流程（供 CLI 和 Web API 共用）
# ---------------------------------------------------------------------------

def run_summary(url: str, config: dict, force: bool = False) -> dict:
    """
    执行完整的摘要生成流程。

    Args:
        url:    Bilibili 动态 URL
        config: 由 get_config() 返回的配置字典
        force:  True 时忽略缓存，强制重新抓取

    Returns:
        {"summary_id": str, "output_dir": str}

    Raises:
        ValueError: 参数校验失败
        RuntimeError: 抓取或处理失败
    """
    post_id = extract_post_id(url)
    if not post_id:
        raise ValueError(f"无法从 URL 中提取动态 ID: {url}，支持格式：https://www.bilibili.com/opus/<id>")

    gemini_client = genai.Client(api_key=config["gemini_api_key"])
    gemini_model = "gemini-2.5-flash"

    # -----------------------------------------------------------------------
    # 尝试从缓存加载，避免重复请求
    # -----------------------------------------------------------------------
    existing_cache = None
    output_base = Path("output")
    if output_base.exists():
        for d in output_base.glob("*/raw.json"):
            try:
                data = json.loads(d.read_text(encoding="utf-8"))
                if str(post_id) in data.get("source_url", ""):
                    existing_cache = (d.parent, data)
                    break
            except Exception:
                continue

    if existing_cache and not force:
        output_dir, raw_data = existing_cache
        print(f"\n发现缓存数据: {output_dir}")
        post = {k: raw_data[k] for k in ("author", "time", "text", "images", "image_descriptions", "combined_text")}
        post["cover_image_local"] = raw_data.get("cover_image_local", "")
        source_url = raw_data.get("source_url", url)
    else:
        # 从 Bilibili 抓取
        cookies = build_cookies(config)
        item = fetch_post(post_id, cookies)
        if not item:
            raise RuntimeError("获取动态失败，请检查 URL 和 Cookie。")

        post = parse_post(item)
        print(f"\n作者：{post['author']}")
        print(f"时间：{post['time']}")
        if post["text"]:
            preview = post["text"][:100]
            print(f"正文：{preview}{'...' if len(post['text']) > 100 else ''}")
        print(f"图片：{len(post['images'])} 张")

        # 确定输出目录并下载 + 识别图片
        output_dir = build_output_dir(post)
        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir = output_dir / "images"

        process_images(post, gemini_client, gemini_model, images_dir)

        # 合并文本：正文 + 各图片提取的文字（封面图描述为空，自动跳过）
        cover = post.get("cover_image_local", "")
        parts = []
        if post["text"]:
            parts.append(post["text"])
        for i, desc in enumerate(post["image_descriptions"]):
            if desc and not (i == 0 and cover):
                parts.append(desc)
        post["combined_text"] = "\n\n".join(parts)

        # 保存原始数据
        source_url = url
        print("\n保存原始数据...")
        save_raw(post, source_url, output_dir)

    # -----------------------------------------------------------------------
    # 生成摘要并写入 summary.md
    # -----------------------------------------------------------------------
    summary = generate_summary(gemini_client, gemini_model, post)

    md_content = build_markdown(post, summary, source_url)
    summary_path = output_dir / "summary.md"
    summary_path.write_text(md_content, encoding="utf-8")

    summary_id = output_dir.name
    print(f"\n完成！summary_id={summary_id}，输出目录：{output_dir}")

    return {"summary_id": summary_id, "output_dir": str(output_dir)}


# ---------------------------------------------------------------------------
# 主流程（CLI 入口）
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Bilibili 动态内容抓取与图片识别摘要工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n  python bilibili_summary.py https://www.bilibili.com/opus/1171504724323598370",
    )
    parser.add_argument("url", help="Bilibili 动态 URL（opus 格式或 t.bilibili.com 格式）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略缓存，强制重新抓取并识别",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Bilibili 动态摘要工具")
    print("=" * 60)

    try:
        config = get_config()
    except ValueError as e:
        print(f"错误：{e}")
        print("请在 .env 文件中配置这些变量（参考 .env.example）")
        sys.exit(1)

    try:
        result = run_summary(args.url, config, force=args.force)
        output_dir = Path(result["output_dir"])
        print(f"\n{'=' * 60}")
        print(f"完成！输出目录：{output_dir}")
        print(f"  摘要文件：{output_dir / 'summary.md'}")
        print(f"  原始数据：{output_dir / 'raw.json'}")
        if (output_dir / "images").exists():
            img_count = len(list((output_dir / "images").glob("*")))
            print(f"  图片文件：{output_dir / 'images'} ({img_count} 张)")
        print("=" * 60)
        summary_path = output_dir / "summary.md"
        if summary_path.exists():
            summary = summary_path.read_text(encoding="utf-8")
            # 提取摘要部分预览
            lines = summary.split("\n")
            preview_lines = []
            in_summary = False
            for line in lines:
                if line.startswith("## 摘要"):
                    in_summary = True
                    continue
                if in_summary and line.startswith("## "):
                    break
                if in_summary:
                    preview_lines.append(line)
            preview = "\n".join(preview_lines).strip()
            print("\n## 摘要预览\n")
            print(preview[:500] + ("..." if len(preview) > 500 else ""))
    except (ValueError, RuntimeError) as e:
        print(f"错误：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
