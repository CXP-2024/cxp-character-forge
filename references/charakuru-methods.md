# Charakuru：源码方法与适用边界

核对日期：2026-10-24。来源为 [nanocle/Charakuru](https://github.com/nanocle/Charakuru)，本地检查版本为 `1.1.0`，发行目录 `charakuru-1.1.0-2026-10-23T00-56-38-465Z`。这不是对上游最新版本的声明。

源码根目录为 Release 解压出的 kit 目录（安装见 [character-workflow.md](character-workflow.md) 第 0 步）。执行前检查存在性和当前版本，按以下相对路径查找。本文提炼方法，不捆绑其第三方人体、表情素材或源码。需要复制发布时核对仓库与素材各自许可证。

## 四种分组各司其职

| 分组 | 该版本的做法 | 本地应用 |
| --- | --- | --- |
| 候选生成 | 含全部头发的头部、T 姿身体，分别用一致多视图生成 | 不将它误写成无发头/头发分别生成；已认可资产可直接续作 |
| 贴图 | hair / head / upper_body / lower_body / accessories | 每组对应实际网格范围与前后参考；下半身包括腰部衣装、裙子、腿、鞋 |
| 摆动物理 | 髪束、裙片、蝴蝶结等有共同运动规律的部件 | 与贴图分组独立，不能把腿和裙子共同绑进裙摆物理 |
| 表情 | 眼周皮肤、睫毛/眼睑线追随部件、上下口缘、左右眉 | 与 UV 岛或连通块不等价，需实际三维选区 |

上游五组是其 `.charakit`/脚本契约。直接跑原程序就遵守契约；本地已有 Blender 项目可采用合适的分组，但必须称作适配路线，不声称完整复刻上游流程。上游特定批次数、面数、人工采用候选节点和 UI 浏览器流程不自动套用到当前代理。

## 按用途找源码

| 任务 | 优先阅读的上游相对路径 |
| --- | --- |
| 分类、参考、重贴图、装配、骨配置 | `skills/tripo-agent-workflow/SKILL.md`、`references/retexture-images.md`（位于该 skill 内） |
| 精细参考的材质语言 | `skills/character-material-brushup/references/painting.md` |
| 对应面恢复 UV / 材质 | `scripts/production.py` 的 `restore_uv`、`assemble` |
| 表情拟合与迁移 | `skills/avatar-expression-authoring/SKILL.md` 及 `references/{commands,transfer,anatomy,diagnostics,visual-quality}.md` |
| 可编辑表情工具与渲染 | `scripts/expression-studio.py`、`scripts/expression-mask.py`、`scripts/expression-transfer.py` |
| 骨架导入与流程调度 | `scripts/import-bones.mjs`、`scripts/run-local-job.mjs` |
| 素体拟合与蒙皮 | `skills/avatar-weight-transfer/SKILL.md`、`references/manual-transfer.md` 及该 skill 的 `scripts/transfer.py` |
| 摆动物理及运行时检查 | `skills/avatar-spring-setup/SKILL.md`、`scripts/spring-setup.py`、`scripts/verify-springs.mjs` |
| MToon 与导出 | `scripts/mtoon-export.py` |

不要仅凭函数名称调用：先读版本对应的参数与前置状态。尤其 `restore_uv` 会清除目标材质槽和 UV 层，在当前项目需用副本/封装保留原 UV 和原材质；不能直接对唯一原本执行。

## 已验证与尚未验证

本地 DeepSeek 案例项目只作为案例定位，不把顶点编号、模型名字或坐标写死进通用工具。

- `charakuru_expressions_v1`：实际采用眼周面罩、口缘和眉部迁移。眼部已有连续演示；嘴型仍有口缘/口内外观问题，未合格。
- `charakuru_expressions_v2_cleanup`：清除重复眉眼纹理并补眼睑线追随；闭眼睫毛局部折角仍在。
- `body_retexture_v1`：身体重贴图、UV 重叠修复、颈部局部统一颜色已做实际渲染与保真检查。不是上游五组全流程。4K 原生图转移到 8K 画布不等于生成 8K 细节；领口与宝石仍有模糊/脏色。
- Charakuru 素体权重转移、SpringBone 运行时检查是已读源码的方法，不据此声称当前 DeepSeek 已按该方案完成绑定或物理。

沿用方法而非上游应用的组织约束：授权范围内持续完成任务，不每一步重复询问；也不因更新 skill 启动生成、购买插件、下载付费素材、推送仓库或重做当前模型。
