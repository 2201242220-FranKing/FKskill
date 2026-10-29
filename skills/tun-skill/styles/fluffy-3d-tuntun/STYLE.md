---
title: 毛毡短绒 3D 豚豚视觉规则
created: 2026-10-25
updated: 2026-10-26
---

# 毛毡短绒 3D 豚豚视觉规则

## 视觉目标

以 `assets/references/` 的实际输入图为身份基准，呈现细腻毛毡 / 麂皮短绒、平滑柔和表面、轻微边缘绒毛、柔和体积光和充足留白。画面像一张有想法的内容插画，不像产品广告或 PPT。不要把“毛绒”理解成长毛蓬松玩具。

## 构图

- 豚豚承担一个关键动作，动作清楚且可被一眼读懂。
- 场景道具少而准确，为动作服务。
- 按 `references/scene-catalog.md` 的平台与发布位置选择画幅：小红书封面/轮播常用 3:4，抖音视频封面 9:16、图文 3:4，X 信息流 16:9、长文封面 5:2、主页 Header 3:1，公众号主封面约 2.35:1、正文图常用 16:9。
- 封面和横幅为标题与界面裁切预留安全区；同一主题跨平台发布时分别适配构图，不拉伸画面。
- 背景使用柔和渐变、浅色棚拍空间或干净留白。


## 字体与图中文字

- 统一使用：**得意黑风格标题 + 思源黑体风格说明文字**；封面与普通配图都按此执行。英文和数字可用 Inter 风格。
- 标题与说明直接写入生图提示词，并在同一次生成调用中随插画一起生成。不要先生成无字插画后再叠字，也不要要求另跑一次字体排版。
- 用户给出标题时，按原文生成；文字保持短而清楚，版面预留标题空间，避免密集小字。未提供标题时，不自行加标题。
- 若中文字形或文案不准确，针对整张图重新生成；不改成单独排字流程。
- 提示词描述的是字体视觉风格，不声称生图模型精确调用了本机字体文件。

## 提示词片段

`reference-image-driven 3D mascot, fine felt or suede short nap, smooth soft surface, subtle fuzzy edge, gentle studio light, clean negative space, slightly surreal physical metaphor, calm sky-blue and cream palette, three-layer circular badge visible, pure sky-blue body, no water droplet, no long fluffy fur, no flat vector, no childish commercial poster, no PPT layout`
