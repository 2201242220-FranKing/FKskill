---
title: FKskill
created: 2026-10-29
updated: 2026-10-29
---

# FKskill

个人技能工具箱，采用“主入口路由 + 独立子技能”结构。FKskill 主入口识别用户意图，具体工作由子技能处理。

## 技能列表

| 技能 | 用途 |
|---|---|
| [Tun skill](skills/tun-skill/README.md) | 豚豚 IP 插画、封面、海报、Banner 与视觉设计 |
| [小海豚 IP 生成](skills/xiaohaitun-ip-generator/SKILL.md) | 个性化校园宠物海豚角色、头像、立绘与贴纸 |
| [方法论一图流生成器](skills/infographic-onepager/SKILL.md) | 方法论、SOP、培训内容的信息图与一图流 |
| [多平台内容改写](skills/xiaojin-content-repurposer/SKILL.md) | 将母稿改写为 X、小红书、抖音、公众号和飞书内容 |
| [小红书起号教练](skills/xiaohongshu-launch-coach/SKILL.md) | 账号定位、起号、选题、诊断与内容打磨 |
| [短视频拆解复刻教练](skills/douyin-video-breakdown/SKILL.md) | 拆解单条短视频并整理分析报告与复刻 SOP |
| [知识库自进化管家](skills/knowledge-base-evolver/SKILL.md) | 整理 Markdown / Obsidian 知识库及索引结构 |

## 安装

将仓库中需要的完整技能目录复制到目标 Agent 的 skills 目录。需要主入口自动分发时，同时安装 skills/fkskill/ 和要使用的子技能目录。

Codex 示例：

    git clone https://github.com/2201242220-FranKing/FKskill.git
    cp -R FKskill/skills/fkskill ~/.codex/skills/
    cp -R FKskill/skills/tun-skill ~/.codex/skills/

按需把其他 skills/<skill-name>/ 目录复制到同一位置。WorkBuddy 等支持 SKILL.md 的 Agent 也可安装对应完整目录。刷新或重启客户端以重新发现技能。不要把仓库根目录当作单个技能安装。

## 目录结构

    skills/
    ├── fkskill/                       # 路由入口
    ├── tun-skill/                     # 豚豚插画与视觉设计
    ├── xiaohaitun-ip-generator/        # 校园宠物海豚 IP 生成
    ├── infographic-onepager/          # 方法论信息图
    ├── xiaojin-content-repurposer/    # 多平台内容改写
    ├── xiaohongshu-launch-coach/      # 小红书账号策略
    ├── douyin-video-breakdown/        # 短视频拆解
    └── knowledge-base-evolver/        # Markdown / Obsidian 知识库整理

## 许可说明

各子技能的许可和来源分别管理。已有许可文件的技能按其文件执行；没有许可文件的技能未授予额外的复制或再分发许可。多平台内容改写目录保留所参考上游项目的 MIT 许可文件。使用豚说 IP 相关素材时，应确认相应品牌与素材授权。
