#!/usr/bin/env python3
"""Lightweight tests for douyin_video_breakdown.py."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "douyin_video_breakdown.py"


def load_module():
    spec = importlib.util.spec_from_file_location("douyin_video_breakdown", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_sections():
    mod = load_module()
    transcript = """# Demo

## 1. 开头钩子 [00:00 - 00:12]
第一段内容。

## 2. 核心观点 [00:12 - 01:05]
第二段内容。
"""
    sections = mod.parse_sections(transcript)
    assert len(sections) == 2
    assert sections[0]["title"] == "1. 开头钩子"
    assert sections[0]["start"] == 0
    assert sections[1]["end"] == 65


def test_parse_simple_frontmatter_author_from_source():
    mod = load_module()
    metadata = mod.parse_simple_frontmatter(
        """---
title: "Kimi Code视频理解链路"
source: "抖音：小天fotos"
---

# Body
"""
    )
    assert metadata["title"] == "Kimi Code视频理解链路"
    assert metadata["source"] == "抖音：小天fotos"


def test_build_report_from_transcript():
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transcript = root / "transcript.md"
        out_dir = root / "out"
        transcript.write_text(
            """# 视频标题

> 时长 1:05 | 来源: https://v.douyin.com/demo/

## 1. 开头钩子 [00:00 - 00:12]
作者先抛出一个强问题。

## 2. 核心观点 [00:12 - 01:05]
作者解释为什么这个问题值得重视。
""",
            encoding="utf-8",
        )
        report, sop = mod.build_report(
            "https://v.douyin.com/demo/",
            transcript,
            out_dir,
            "测试标题",
            "测试作者",
            None,
        )
        content = report.read_text(encoding="utf-8")
        assert "作者昵称：测试作者" in content
        assert "自动候选：这条视频主要围绕 1. 开头钩子、2. 核心观点 展开" in content
        assert "- 1. 开头钩子：作者先抛出一个强问题。" in content
        assert "未提供本地视频文件，关键截图待补。" in content
        assert "## 拉片报告" in content
        assert "## 工具链推断" in content
        assert sop.exists()
        sop_content = sop.read_text(encoding="utf-8")
        assert "# 测试标题 复刻SOP" in sop_content
        assert "## 配帧逐段表" in sop_content


def test_infer_infographic_tool_list_type():
    mod = load_module()
    transcript = "Obsidian AI Skills 工具清单：这一期整理 10 个 AI 工具。"
    assert mod.infer_video_type(transcript, []) == "信息图口播_工具清单"


if __name__ == "__main__":
    test_parse_sections()
    test_parse_simple_frontmatter_author_from_source()
    test_build_report_from_transcript()
    test_infer_infographic_tool_list_type()
    print("ok")
