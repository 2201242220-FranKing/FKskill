# 豚豚插画 Skill

基于豚说 IP 的参考图驱动 3D 毛毡短绒认知插画 Skill。它把文章、方法论、知识库和活动主题转成可执行的插画提示词，让豚豚作为陪跑型吉祥物承担一个关键动作。

## 核心约束

- `assets/references/` 中的图片必须作为生图请求的实际输入，不能只读不传。
- 外貌严格参考图片：纯天蓝身体、奶白脸、两个宽间距圆点黑点、左上单个圆钝突起。
- 胸口中央三层圆形徽章必须完整保留：奶白大圆盘 → 天蓝内圆 → 白色粗笔手写 `φ`。
- 动作、表情和配饰可以按主题变化；水滴默认去掉。
- 质感是细腻毛毡 / 麂皮短绒，不是蓬松长毛。
- 风格偏好：3D、柔和、怪诞、清爽、留白。
- 避免：白色腹部、蓝白斜切、猫耳、尖鳍、长条黑点、扁平、幼稚、商业海报感、PPT 感。

## 使用

让 Agent 先读取 `SKILL.md`、`references/character-bible.md` 和 `references/reference-image-protocol.md`，再根据用途读取其他 `references/`、`styles/` 和 `assets/references/`。

生成前必须确认当前模型支持图生图，并在实际调用参数或附件中核验参考图已经发送。WorkBuddy 的 Agnes 图改图使用 `agnes-image-2.0-flash`，参考图通过工具规定的 `extra_body.image` URL 数组传入；只有上传流程确实提供可访问 URL 时才执行。纯文生图、无法确认图片是否随请求发送，或只在提示词里写文件路径时，只交付提示词草稿，不把结果标为合格出图。

适用：正文配图、公众号封面、小红书封面、X 封面、活动海报、Banner、个人知识库和 AI 工具主题插画。

## 目录

- `SKILL.md`：主工作流
- `references/character-bible.md`：角色圣经
- `references/reference-image-protocol.md`：参考图实际输入协议
- `references/prompt-blueprint.md`：两段式提示词蓝图
- `references/tuntun-qa-checklist.md`：生成验收
- `styles/fluffy-3d-tuntun/`：毛毡短绒 3D 风格原子
- `assets/references/`：三视图、多表情和动作参考图
