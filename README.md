---
title: FKskill
created: 2026-10-29
updated: 2026-11-11
---

# FKskill

个人技能工具箱，采用“主入口路由 + 独立子技能”结构。FKskill 主入口识别用户意图，具体工作由子技能处理。每个 `skills/<name>/` 都是完整独立的技能，可以整套安装，也可以只装其中一个，彼此不依赖。

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
| [豚说论坛查询与微信成文](skills/tuntun-forum/SKILL.md) | 匿名只读查 4 校校友圈最新帖、热帖、关键词、详情、对比、日报与 CSV 导出，并把帖子写成微信 / 公众号稿 |

`skills/fkskill/` 是总览路由入口（需求 → 子技能），本身不实现具体能力。需要自动分发时一并安装；只装单个子技能也能独立触发。新增技能时同步维护 `fkskill/SKILL.md` 的路由表与本清单。

## 安装

### 用安装器（推荐，WorkBuddy 用户级）

    git clone https://github.com/2201242220-FranKing/FKskill.git
    cd FKskill
    ./install.sh --list                  # 查看全部技能与本机安装状态
    ./install.sh --all                   # 整套安装（含 fkskill 总览）
    ./install.sh --only tuntun-forum     # 只装论坛技能
    ./install.sh --all --link            # 软链安装，改仓库即时生效

默认装到 `~/.workbuddy/skills/`，可用 `WORKBUDDY_SKILLS_DIR` 指定别的目录；目标已存在时默认跳过，加 `--force` 会先备份到 `.backup/` 再覆盖。安装器只复制或软链文件，不删除已有技能。

### 不 clone 仓库，只下载一个技能

GitHub 网页不支持只下载子目录，安装器提供 `--fetch`：通过 GitHub 文件树 API 与 raw 文件拉取指定技能目录，适合只要一个技能的场景。

    curl -fsSL https://raw.githubusercontent.com/2201242220-FranKing/FKskill/main/install.sh -o install.sh
    bash install.sh --fetch tuntun-forum

也可以用 Git 稀疏检出：

    git clone --filter=blob:none --sparse https://github.com/2201242220-FranKing/FKskill.git
    cd FKskill
    git sparse-checkout set skills/tuntun-forum

`--fetch` 需要 `curl` 与 `python3`，并读取远程 `main` 分支；可用 `FKSKILL_OWNER` / `FKSKILL_REPO` / `FKSKILL_BRANCH` 覆盖仓库与分支。

### 手动复制（Codex 等）

    git clone https://github.com/2201242220-FranKing/FKskill.git
    cp -R FKskill/skills/fkskill ~/.codex/skills/
    cp -R FKskill/skills/tuntun-forum ~/.codex/skills/

按需把其他 `skills/<skill-name>/` 目录复制到同一位置。WorkBuddy 等支持 SKILL.md 的 Agent 也可安装对应完整目录。刷新或重启客户端以重新发现技能。**不要把仓库根目录当作单个技能安装。**

## 目录结构

    .gitignore                         排除本地配置、缓存与凭据
    install.sh                         整套 / 单装 / 远程单下载
    skills/
    ├── fkskill/                       # 路由入口
    ├── tun-skill/                     # 豚豚插画与视觉设计
    ├── xiaohaitun-ip-generator/        # 校园宠物海豚 IP 生成
    ├── infographic-onepager/          # 方法论信息图
    ├── xiaojin-content-repurposer/    # 多平台内容改写
    ├── xiaohongshu-launch-coach/      # 小红书账号策略
    ├── douyin-video-breakdown/        # 短视频拆解
    ├── knowledge-base-evolver/        # Markdown / Obsidian 知识库整理
    └── tuntun-forum/                  # 豚说论坛只读查询与微信成文
        ├── SKILL.md
        ├── LICENSE                    # MIT
        ├── config.example.json        # 公开只读参数（域名与 4 校 circleId）
        ├── references/api.md          # 字段映射与待确认问题
        └── scripts/forum_query.py     # 自包含，仅 Python 标准库

## 配置与隐私

`tuntun-forum` 的默认公开参数写在 `skills/tuntun-forum/config.example.json`：论坛域名与 4 校 `circleId`，均为匿名只读 GET 的公开参数，不含账号或令牌。换学校时把它复制为同目录 `config.json` 后修改（该文件已被 `.gitignore` 排除），也可用命令行或环境变量覆盖。脚本只发只读 GET，不保存凭据、不发帖、不回复、不点赞。

## 许可说明

各子技能的许可和来源分别管理。已有许可文件的技能按其文件执行；没有许可文件的技能未授予额外的复制或再分发许可。多平台内容改写目录保留所参考上游项目的 MIT 许可文件。`tuntun-forum` 采用 MIT 许可，见 `skills/tuntun-forum/LICENSE`；新增技能请在自身目录内附许可文件。使用豚说 IP 相关素材时，应确认相应品牌与素材授权。
