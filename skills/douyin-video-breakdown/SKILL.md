---
name: douyin-video-breakdown
description: Analyze a single Douyin/TikTok-style short video from a user-provided link or transcript. Use when the user asks to break down, transcribe, summarize, capture keyframes, extract valuable points, infer the production workflow, or create a replica SOP for a Douyin short video, Chinese short-form video, or already-transcribed short video.
---

# Douyin Video Breakdown

Use this skill to turn one user-provided short-video link or transcript into two Markdown artifacts:

1. a video breakdown report with metadata, overview, transcript, keyframes, segment table, value points, and tool-chain inference
2. a replica SOP that explains how to remake the same format for another topic

Process only one user-provided video at a time. Do not bulk scrape, bypass platform protections, save account cookies, or send private/sensitive videos to third-party transcription services.

## Quick Start

Run the local doctor first:

```bash
python3 scripts/douyin_video_breakdown.py --doctor
```

For a Douyin link, prefer the local `video-transcript` backend when installed:

```bash
python3 scripts/douyin_video_breakdown.py "https://v.douyin.com/xxxx/" --engine video-transcript
```

For an existing transcript:

```bash
python3 scripts/douyin_video_breakdown.py "https://v.douyin.com/xxxx/" \
  --transcript "/path/to/transcript.md" \
  --title "Video title" \
  --author "Author nickname"
```

If a local video file is available, add `--video /path/to/video.mp4` to extract keyframes with `ffmpeg`.

## Dependencies

The script is useful in transcript-only mode with only Python 3.

Optional dependencies:

- `ffmpeg` and `ffprobe`: keyframe extraction and media inspection
- `video-transcript`: preferred local downloader/transcriber backend, usually installed at `~/.claude/skills/video-transcript`
- `deyo`: optional cloud transcription fallback; use only for non-sensitive videos and after the user accepts cloud upload and minute costs

Set `VIDEO_TRANSCRIPT_SKILL_HOME` or `VT_HOME` when the `video-transcript` backend is installed somewhere non-standard.

## Workflow

1. Identify whether the user provided a link, a transcript, or both.
2. If only a link is available, run `--engine video-transcript`.
3. If transcription fails, explain the failure and ask for an exported transcript or a local video file.
4. Run `scripts/douyin_video_breakdown.py` to create the first-pass report and SOP.
5. Open the generated Markdown files and refine the sections that require judgment:
   - content overview
   - value points
   - segment table visual descriptions
   - tool-chain confidence
   - recommended reuse actions
6. Return file paths and a concise summary. Do not paste the full transcript unless the user asks.

## Outputs

By default, files are written to:

```text
./douyin-video-breakdowns/YYYY-MM-DD/
```

Override with `--out-dir`.

The generated files include:

- `YYYY-MM-DD_<title>_视频拆解.md`
- `YYYY-MM-DD_<title>_复刻SOP.md`
- optional `assets/<title>/keyframe_*.jpg`

## SOP Templates

The script selects a template from `references/replica_sop_templates/` by inferred video type:

- `口播教程_录屏露脸`
- `口播教程_纯露脸`
- `vlog_生活日常`
- `剧情类_短剧`
- `蓄势类_教学做菜`
- `信息图口播_工具清单`

When type inference is wrong, manually correct `video_type` in the generated SOP and refine the report.
