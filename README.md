# 豚豚插画 Skill

基于豚说 IP 的毛绒 3D 认知插画 Skill。它把文章、方法论、知识库和活动主题转成可执行的插画提示词，让豚豚作为陪跑型吉祥物承担一个关键动作。

## 核心约束

- 外貌严格参考 `assets/references/`，不能改变角色身份特征。
- 胸口中央椭圆徽章和白色手写 `φ` 必须保留。
- 动作、表情和配饰可以按主题变化。
- 水滴默认去掉。
- 风格偏好：毛绒、3D、柔和、怪诞、清爽、留白。
- 避免：扁平、幼稚、商业海报感、PPT 感。

## 使用

让 Agent 先读取 `SKILL.md`，再根据用途读取 `references/`、`styles/` 和 `assets/references/`。

适用：正文配图、公众号封面、小红书封面、X 封面、活动海报、Banner、个人知识库和 AI 工具主题插画。

## 目录

- `SKILL.md`：主工作流
- `references/character-bible.md`：角色圣经
- `references/prompt-blueprint.md`：提示词蓝图
- `references/tuntun-qa-checklist.md`：生成验收
- `styles/fluffy-3d-tuntun/`：毛绒 3D 风格原子
- `assets/references/`：三视图、多表情和动作参考图
