#!/usr/bin/env python3
"""Create Markdown video breakdown reports from Douyin transcripts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = Path.cwd() / "douyin-video-breakdowns"
TEMPLATE_PATH = PROJECT_DIR / "references" / "video_analysis_template.md"
SOP_TEMPLATE_DIR = PROJECT_DIR / "references" / "replica_sop_templates"


def now_local() -> dt.datetime:
    return dt.datetime.now()


def safe_name(text: str, fallback: str = "douyin-video") -> str:
    text = text.strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|#\[\]\n\r\t]+", "-", text)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return text[:80] or fallback


def rel_for_markdown(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def find_video_transcript_home() -> Optional[Path]:
    candidates = [
        os.environ.get("VIDEO_TRANSCRIPT_SKILL_HOME"),
        os.environ.get("VT_HOME"),
        str(Path.home() / ".claude" / "skills" / "video-transcript"),
        str(Path.home() / ".codex" / "skills" / "video-transcript"),
        str(Path.home() / ".workbuddy" / "skills" / "video-transcript"),
        str(Path.cwd() / ".claude" / "skills" / "video-transcript"),
        str(Path.cwd() / "skills" / "video-transcript"),
    ]
    for item in candidates:
        if not item:
            continue
        path = Path(item).expanduser()
        if (path / "scripts" / "transcript.py").exists():
            return path
    return None


def find_video_transcript_python(vt_home: Optional[Path]) -> str:
    """优先用底座自己的 venv python(funasr/torch 在那里),找不到再 fallback 系统 python3。"""
    if vt_home is not None:
        for candidate in (
            vt_home / ".venv" / "bin" / "python",
            vt_home / ".venv" / "bin" / "python3",
        ):
            if candidate.exists():
                return str(candidate)
    return "python3"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(cmd: List[str], env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def run_doctor() -> int:
    print("douyin-video-breakdown doctor")
    print("=" * 48)
    checks = [
        ("python3", command_exists("python3"), sys.executable),
        ("ffmpeg", command_exists("ffmpeg"), shutil.which("ffmpeg") or "not found"),
        ("ffprobe", command_exists("ffprobe"), shutil.which("ffprobe") or "not found"),
    ]
    for name, ok, detail in checks:
        mark = "✓" if ok else "✗"
        print(f"{mark} {name}: {detail}")

    deyo = shutil.which("deyo")
    if deyo:
        print(f"✓ deyo: {deyo}")
    else:
        print("⚠ deyo: not found (云转写备选,可忽略,默认走本地 SenseVoice)")

    vt_home = find_video_transcript_home()
    vt_python = find_video_transcript_python(vt_home)
    if vt_home:
        print(f"✓ video-transcript: {vt_home}")
        print(f"  using python: {vt_python}")
    else:
        print("✗ video-transcript: not found")
        print("  Install: bash <(curl -fsSL https://raw.githubusercontent.com/voyagerwang/douyin-transcript-skill/main/bootstrap.sh)")

    if vt_home:
        print("\nExternal video-transcript doctor:")
        result = run_command([vt_python, str(vt_home / "scripts" / "transcript.py"), "--doctor"])
        output = (result.stdout + "\n" + result.stderr).strip()
        if output:
            print(output)
        return result.returncode
    return 1


def call_video_transcript(url: str, output_dir: Path, images_dir: Path, extra_args: Iterable[str]) -> Dict[str, Any]:
    vt_home = find_video_transcript_home()
    if not vt_home:
        raise RuntimeError("video-transcript skill not found. Run --doctor for install guidance.")
    env = os.environ.copy()
    env["VIDEO_TRANSCRIPT_OUTPUT_DIR"] = str(output_dir)
    env["VIDEO_TRANSCRIPT_IMAGES_DIR"] = str(images_dir)
    vt_python = find_video_transcript_python(vt_home)
    cmd = [vt_python, str(vt_home / "scripts" / "transcript.py"), url, *extra_args]
    result = run_command(cmd, env=env)
    if result.stderr.strip():
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"video-transcript failed with exit code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"video-transcript stdout is not JSON: {result.stdout[:500]}") from exc


def call_deyo(url: str, output_dir: Path, extra_args: Iterable[str]) -> Dict[str, Any]:
    deyo = shutil.which("deyo")
    if not deyo:
        raise RuntimeError("deyo CLI not found. Install and login to Deyo first, or use --engine video-transcript.")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_local().strftime("%Y%m%d_%H%M%S")
    transcript_path = output_dir / f"deyo_transcript_{stamp}.md"
    cmd = [
        deyo,
        "--language",
        "zh",
        "--progress-format",
        "jsonl",
        "-O",
        str(transcript_path),
        *extra_args,
        url,
    ]
    result = run_command(cmd)
    if result.stderr.strip():
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"deyo failed with exit code {result.returncode}: {result.stdout[-500:]}")
    if not transcript_path.exists():
        raise RuntimeError(f"deyo completed but transcript not found: {transcript_path}")
    return {
        "engine": "deyo",
        "transcript_path": str(transcript_path),
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_simple_frontmatter(markdown: str) -> Dict[str, str]:
    if not markdown.startswith("---"):
        return {}
    match = re.match(r"^---\s*\n(?P<body>.*?)\n---\s*\n", markdown, re.DOTALL)
    if not match:
        return {}
    data: Dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line or line.lstrip().startswith("-"):
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip().strip('"').strip("'")
        if value:
            data[key.strip()] = value
    return data


def parse_time_to_seconds(value: str) -> Optional[float]:
    value = value.strip()
    parts = value.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None
    return None


def fmt_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_sections(transcript: str) -> List[Dict[str, Any]]:
    pattern = re.compile(
        r"^##\s+(?P<title>.+?)\s+\[(?P<start>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?)\]\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(transcript))
    sections: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(transcript)
        start = parse_time_to_seconds(match.group("start"))
        end = parse_time_to_seconds(match.group("end"))
        sections.append(
            {
                "title": match.group("title").strip(),
                "start": start,
                "end": end,
                "body": transcript[body_start:body_end].strip(),
            }
        )
    return sections


def make_value_candidates(sections: List[Dict[str, Any]]) -> str:
    if not sections:
        return "待 Agent 基于逐字稿补充。"
    lines = []
    for section in sections[:6]:
        title = section["title"]
        body = re.sub(r"\s+", " ", section["body"]).strip()
        snippet = body[:90] + ("..." if len(body) > 90 else "")
        lines.append(f"- {title}：{snippet or '待补充'}")
    return "\n".join(lines)


def make_overview_candidate(sections: List[Dict[str, Any]]) -> str:
    if not sections:
        return "待 Agent 基于逐字稿补充。"
    titles = "、".join(section["title"] for section in sections[:5])
    return f"自动候选：这条视频主要围绕 {titles} 展开。请 Agent 继续阅读逐字稿后改写成 1-3 句自然概述。"


def extract_screenshots(video: Optional[Path], assets_dir: Path, sections: List[Dict[str, Any]]) -> List[Tuple[Path, str]]:
    if not video or not video.exists() or not command_exists("ffmpeg"):
        return []
    assets_dir.mkdir(parents=True, exist_ok=True)
    points: List[Tuple[float, str]] = [(1.0, "封面/开头画面")]
    for section in sections[:4]:
        start = section.get("start")
        end = section.get("end")
        if start is None or end is None or end <= start:
            continue
        points.append(((start + end) / 2, section["title"]))

    captures: List[Tuple[Path, str]] = []
    for idx, (seconds, label) in enumerate(points, start=1):
        output = assets_dir / f"keyframe_{idx:02d}_{fmt_seconds(seconds).replace(':', '-')}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            fmt_seconds(seconds),
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output),
        ]
        result = run_command(cmd)
        if result.returncode == 0 and output.exists():
            captures.append((output, label))
    return captures


def screenshot_markdown(captures: List[Tuple[Path, str]], video: Optional[Path]) -> str:
    if captures:
        lines = []
        for path, label in captures:
            lines.append(f"![{label}]({rel_for_markdown(path)})")
            lines.append(f"说明：{label}")
            lines.append("")
        return "\n".join(lines).strip()
    if video:
        return "未能自动抽取截图。请确认 `ffmpeg` 可用，或手动补充关键帧。"
    return "未提供本地视频文件，关键截图待补。"


def infer_video_type(transcript: str, captures: List[Tuple[Path, str]]) -> str:
    text = transcript.lower()
    if any(word in text for word in ("剧情", "反转", "短剧", "角色", "台词")):
        return "剧情类_短剧"
    if any(
        word in text
        for word in (
            "信息图",
            "工具清单",
            "工具合集",
            "skill",
            "skills",
            "obsidian",
            "notion",
            "ai工具",
            "开源项目",
        )
    ):
        return "信息图口播_工具清单"
    if any(word in text for word in ("录屏", "屏幕", "codex", "飞书", "代码", "工作流", "软件", "网页", "工具")):
        return "口播教程_录屏露脸"
    if any(word in text for word in ("vlog", "日常", "生活", "宿舍", "一天", "探店")):
        return "vlog_生活日常"
    if any(word in text for word in ("做菜", "手工", "材料", "步骤", "成品", "教程")) and not any(
        word in text for word in ("codex", "飞书", "代码", "工作流", "工具", "软件", "网页")
    ):
        return "蓄势类_教学做菜"
    return "口播教程_纯露脸"


def time_range_for_section(section: Dict[str, Any]) -> str:
    start = section.get("start")
    end = section.get("end")
    if start is None or end is None:
        return "待补"
    return f"{fmt_seconds(start)} - {fmt_seconds(end)}"


def summarize_line(text: str, limit: int = 42) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "待 Agent 复核"
    return text[:limit] + ("..." if len(text) > limit else "")


def build_segment_table(sections: List[Dict[str, Any]], captures: List[Tuple[Path, str]]) -> str:
    if not sections:
        return "待 Agent 基于逐字稿和关键帧补充配帧逐段表。"
    capture_by_label = {label: path for path, label in captures}
    rows = [
        "| 时间区间 | 画面/镜头 | 台词/内容 | 图形特效 | 作用 | 代表帧 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for section in sections:
        title = section["title"]
        body = section["body"]
        frame = capture_by_label.get(title)
        frame_md = f"![{title}]({rel_for_markdown(frame)})" if frame else "待补"
        visual = "待 Agent 结合关键帧判断"
        effect = "待 Agent 结合画面判断"
        role = "承接主题 / 推进信息"
        if any(word in title for word in ("开头", "引入", "钩子")):
            role = "建立钩子"
        elif any(word in title for word in ("结尾", "总结", "行动")):
            role = "收束观点 / CTA"
        rows.append(
            f"| {time_range_for_section(section)} | {visual} | {summarize_line(body)} | {effect} | {role} | {frame_md} |"
        )
    return "\n".join(rows)


def build_key_findings(sections: List[Dict[str, Any]], video_type: str) -> str:
    findings = [f"- 视频类型初判：{video_type}。"]
    if sections:
        findings.append(f"- 结构：共 {len(sections)} 个语义段落，适合按时间轴逐段复盘。")
        first = sections[0]["title"]
        findings.append(f"- 开头：第一段为「{first}」，需要重点检查前 5 秒是否有结果前置或强钩子。")
    else:
        findings.append("- 结构：暂未解析到带时间戳的语义段落，需要 Agent 手动补表。")
    findings.append("- 节奏：需结合关键帧检查跳切、字幕、动效和 CTA。")
    return "\n".join(findings)


def build_one_sentence_conclusion(sections: List[Dict[str, Any]], video_type: str) -> str:
    if sections:
        return f"这是一条{video_type}视频，主要靠「{sections[0]['title']}」进入主题，再按段落递进完成表达。"
    return f"这是一条{video_type}视频，需补充关键帧后判断具体拍法。"


def build_replicability_score(video_type: str, sections: List[Dict[str, Any]]) -> str:
    score = 4
    reason = "结构清晰，主要难点在脚本密度、剪辑节奏和画面细节复刻。"
    if video_type == "剧情类_短剧":
        score = 3
        reason = "剧情类需要演员、场景和反应镜头，复刻难度中等。"
    elif video_type == "信息图口播_工具清单":
        score = 4
        reason = "信息结构容易复刻，难点在视觉统一、专有名词准确性和高密度口播节奏。"
    elif video_type == "vlog_生活日常":
        score = 4
        reason = "素材可自拍，难点在真实感和节奏。"
    elif not sections:
        score = 2
        reason = "缺少时间轴段落和关键帧，当前只能低置信评估。"
    return f"{score}/5 — {reason}"


def infer_tool_chain(transcript: str, video_type: str) -> str:
    text = transcript.lower()
    rows = [
        "| 工具/环节 | 推断 | 置信度 | 依据 |",
        "| --- | --- | --- | --- |",
    ]
    if video_type == "信息图口播_工具清单":
        rows.append("| 脚本 | AI 辅助清单式口播稿 | 高 | 内容通常按“总观点 -> 条目清单 -> 入门建议”组织。 |")
        rows.append("| 视觉 | Figma / Canva / Keynote / AI 信息图模板 | 中 | 信息图口播依赖统一卡片、图标和关键词强调。 |")
    if any(word in text for word in ("codex", "代码", "网页", "飞书", "工作流", "软件")):
        rows.append("| 录屏 | OBS / QuickTime / 系统录屏 | 中 | 出现工具或软件操作讲解，需要屏幕录制。 |")
        rows.append("| 动效 | Remotion / After Effects / 剪映关键帧 | 低 | 需要结合关键帧确认是否有 motion graphics。 |")
    if "剪映" in text or "capcut" in text:
        rows.append("| 剪辑 | 剪映 / CapCut | 高 | 逐字稿直接提到剪映或 CapCut。 |")
    else:
        rows.append("| 剪辑 | 剪映 / CapCut / Premiere | 中 | 短视频常规剪辑链路，需看关键帧确认。 |")
    if video_type.startswith("口播") or video_type == "信息图口播_工具清单":
        rows.append("| 拍摄 | 手机/摄像头 + 补光 + 领夹麦 | 中 | 口播教程类通常需要人声和稳定画面。 |")
    rows.append("| 字幕 | 自动字幕 + 人工强调字卡 | 中 | 短视频教程通常需要字幕承载信息密度。 |")
    return "\n".join(rows)


def load_sop_template(video_type: str) -> Tuple[Path, str]:
    candidates = list(SOP_TEMPLATE_DIR.glob(f"*_{video_type}.md"))
    if not candidates:
        candidates = list(SOP_TEMPLATE_DIR.glob("*_口播教程_纯露脸.md"))
    if not candidates:
        raise RuntimeError(f"No SOP template found for video_type={video_type}")
    path = candidates[0]
    return path, read_text(path)


def generate_replica_sop(
    url: str,
    output_dir: Path,
    title: str,
    author: str,
    video_type: str,
    sections: List[Dict[str, Any]],
    segment_table: str,
    tool_chain: str,
) -> Path:
    template_path, template = load_sop_template(video_type)
    today = now_local().strftime("%Y-%m-%d")
    slug = safe_name(title)
    output_dir.mkdir(parents=True, exist_ok=True)
    sop_path = output_dir / f"{today}_{slug}_复刻SOP.md"
    section_titles = "\n".join(f"- {time_range_for_section(section)}：{section['title']}" for section in sections) or "- 待补时间轴"
    content = f"""---
title: "{title} 复刻SOP"
type: replica-sop
status: inbox
created: {today}
updated: {today}
source: douyin
author: "{author}"
url: "{url}"
video_type: "{video_type}"
template: "{template_path.name}"
tags:
  - 视频拆解
  - 复刻SOP
  - 抖音
---

# {title} 复刻SOP

## 基础信息

- 作者昵称：{author}
- 视频链接：{url}
- 视频类型：{video_type}
- SOP 模板：{rel_for_markdown(template_path)}

## 时间轴骨架

{section_titles}

## 工具链推断

{tool_chain}

## 原始模板

{template.strip()}

## 针对此视频的复刻建议

1. 先复刻结构，不急着复刻视觉细节。
2. 按上方时间轴写同结构脚本，每段只替换成自己的主题。
3. 对照配帧逐段表补拍/补录关键画面。
4. 剪辑完成后检查前 5 秒钩子、段落节奏和结尾 CTA。

## 配帧逐段表

{segment_table}
"""
    sop_path.write_text(content, encoding="utf-8")
    return sop_path


def load_template() -> str:
    return read_text(TEMPLATE_PATH)


def build_report(
    url: str,
    transcript_path: Path,
    output_dir: Path,
    title: str,
    author: str,
    video: Optional[Path],
) -> Tuple[Path, Path]:
    transcript = read_text(transcript_path)
    sections = parse_sections(transcript)
    today = now_local().strftime("%Y-%m-%d")
    timestamp = now_local().strftime("%Y-%m-%d %H:%M")
    slug = safe_name(title)
    assets_dir = output_dir / "assets" / slug
    captures = extract_screenshots(video, assets_dir, sections)
    video_type = infer_video_type(transcript, captures)
    segment_table = build_segment_table(sections, captures)
    tool_chain = infer_tool_chain(transcript, video_type)
    sop_path = generate_replica_sop(url, output_dir, title, author, video_type, sections, segment_table, tool_chain)
    report_path = output_dir / f"{today}_{slug}_视频拆解.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    template = load_template()
    transcript_ref = rel_for_markdown(transcript_path)
    transcript_content = transcript.strip()
    replacements = {
        "{{title}}": title,
        "{{author}}": author or "待补",
        "{{url}}": url,
        "{{date}}": today,
        "{{datetime}}": timestamp,
        "{{transcript_ref}}": transcript_ref,
        "{{screenshots}}": screenshot_markdown(captures, video),
        "{{transcript_content}}": transcript_content,
        "{{overview}}": make_overview_candidate(sections),
        "{{value_points}}": make_value_candidates(sections),
        "{{cover}}": screenshot_markdown(captures[:1], video),
        "{{one_sentence_conclusion}}": build_one_sentence_conclusion(sections, video_type),
        "{{replicability_score}}": build_replicability_score(video_type, sections),
        "{{key_findings}}": build_key_findings(sections, video_type),
        "{{segment_table}}": segment_table,
        "{{tool_chain}}": tool_chain,
        "{{sop_ref}}": rel_for_markdown(sop_path),
    }
    content = template
    for key, value in replacements.items():
        content = content.replace(key, value)
    report_path.write_text(content, encoding="utf-8")
    return report_path, sop_path


def infer_title(summary: Dict[str, Any], fallback: str) -> str:
    for key in ("title", "video_title"):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def infer_metadata_from_transcript(transcript_path: Path) -> Dict[str, str]:
    try:
        text = read_text(transcript_path)
    except OSError:
        return {}
    metadata = parse_simple_frontmatter(text)
    if "author" not in metadata:
        source = metadata.get("source", "")
        if "：" in source:
            metadata["author"] = source.split("：", 1)[1].strip()
        elif ":" in source:
            metadata["author"] = source.split(":", 1)[1].strip()
    return metadata


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Douyin video breakdown reports.")
    parser.add_argument("url", nargs="?", help="Douyin URL or original video URL.")
    parser.add_argument("--doctor", action="store_true", help="Check local dependencies.")
    parser.add_argument("--engine", choices=["none", "video-transcript", "deyo"], default="none")
    parser.add_argument("--transcript", help="Existing transcript Markdown path.")
    parser.add_argument("--video", help="Optional local video path for keyframe screenshots.")
    parser.add_argument("--title", default="", help="Video title.")
    parser.add_argument("--author", default="", help="Author nickname.")
    parser.add_argument("--out-dir", default="", help="Output directory. Defaults to ./douyin-video-breakdowns/YYYY-MM-DD.")
    parser.add_argument("--vt-arg", action="append", default=[], help="Extra arg passed to video-transcript.")
    parser.add_argument("--deyo-arg", action="append", default=[], help="Extra arg passed to deyo CLI.")
    args = parser.parse_args(argv)

    if args.doctor:
        return run_doctor()

    if not args.url:
        parser.error("url is required unless --doctor is used")

    today = now_local().strftime("%Y-%m-%d")
    output_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_OUTPUT_ROOT / today
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "assets"

    summary: Dict[str, Any] = {}
    transcript_path: Optional[Path] = Path(args.transcript).expanduser() if args.transcript else None

    if args.engine == "video-transcript":
        summary = call_video_transcript(args.url, output_dir, images_dir, args.vt_arg)
        raw_path = summary.get("transcript_path")
        if raw_path:
            transcript_path = Path(str(raw_path)).expanduser()
    elif args.engine == "deyo":
        summary = call_deyo(args.url, output_dir, args.deyo_arg)
        raw_path = summary.get("transcript_path")
        if raw_path:
            transcript_path = Path(str(raw_path)).expanduser()

    if not transcript_path:
        raise RuntimeError("No transcript path. Use --transcript or --engine video-transcript.")
    if not transcript_path.exists():
        raise RuntimeError(f"Transcript not found: {transcript_path}")

    transcript_metadata = infer_metadata_from_transcript(transcript_path)
    title = args.title.strip() or infer_title(summary, transcript_metadata.get("title", safe_name(transcript_path.stem, "抖音视频")))
    author = args.author.strip() or str(summary.get("author") or summary.get("nickname") or transcript_metadata.get("author") or "待补")
    video = Path(args.video).expanduser() if args.video else None
    report, sop = build_report(args.url, transcript_path, output_dir, title, author, video)

    result = {
        "status": "ok",
        "report_path": str(report),
        "sop_path": str(sop),
        "transcript_path": str(transcript_path),
        "output_dir": str(output_dir),
        "title": title,
        "author": author,
        "needs_agent_review": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
