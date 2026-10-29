---
title: FKskill
created: 2026-10-29
updated: 2026-10-29
---

# FKskill

个人技能工具箱：主 Skill 负责路由，子 Skill 独立执行。参考 dbs 的组织方式，不复制其商业诊断内容。

## 技能结构

```text
FKskill/
├── README.md
└── skills/
    ├── fkskill/
    │   └── SKILL.md          # 主入口
    └── tun-skill/           # Tun skill：插画与视觉设计
        ├── SKILL.md
        ├── README.md
        ├── assets/references/
        ├── references/
        └── styles/
```

| 技能 | 定位 | 入口 |
|---|---|---|
| FKskill / `fkskill` | 识别需求，路由到子技能 | [主入口](skills/fkskill/SKILL.md) |
| Tun skill / `tun-skill` | 豚豚 IP 插画、正文配图、封面、活动海报、Banner 与流程图 | [使用说明](skills/tun-skill/README.md) |

## 安装

克隆仓库：

```sh
git clone https://github.com/2201242220-FranKing/FKskill.git
```

将 `skills/fkskill/` 与 `skills/tun-skill/` 两个完整目录复制到客户端的技能目录，例如 Codex 的 `~/.codex/skills/` 或 WorkBuddy 的 `~/.workbuddy/skills/`。不要只复制 SKILL.md，Tun skill 的参考图与支持文档必须一并保留。刷新或重启客户端以重新发现技能。

只需要插画设计，也可以单独安装 `tun-skill/`。升级时使用同名目录更新，避免同时保留旧版 `tuntun-illustrations` 而重复加载。安装 FKskill 时不需要把仓库根目录当作单个技能。

## 使用示例

- “用 FKskill 做一张 Obsidian 个人知识库 Banner。”
- “用 Tun skill 生成小红书封面，标题是……”
- “用 Tun skill 做 X 长文封面。”

Tun skill 保留参考图实际输入、固定角色外貌、平台尺寸判断、X 长文封面 5:2，以及得意黑风格标题＋思源黑体风格说明一次直接生成的规则。主入口本身不提供生图模型或 API 密钥。

## 扩展

新增一个真正可用的技能时，在 `skills/<技能名>/` 中独立维护 SKILL.md 和资源，再更新 FKskill 路由表及本页技能表。目前仅收录 Tun skill。
