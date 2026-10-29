---
name: cxp-character-forge
description: 从参考立绘通过 Tripo 兼容代理生成带贴图的 3D 人物，接续 Blender 外形检查、组件修整、按需绑骨动作与资产交付。用于人物建模和已有生成任务续作。
---

# CXP Character Forge

使用本 skill 目录下的 `scripts/tripo_proxy.py`。首次安装执行 `python scripts/bootstrap.py` 获取固定版本依赖；读取 README 的配置方式。只向用户配置的代理地址发送密钥，不调用上游官方 CLI 的 configure。

## 任务与参考

尊重用户确认的设计、比例、定稿版本与静态/动画用途。先查已有资产和任务记录，避免重复生成。造新人物先确认本机装有 [Charakuru](https://github.com/nanocle/Charakuru) 源码（Releases 下载解压；Node 22+、Blender 5.2、VRM Add-on），作为三视图、重贴图分组、UV 恢复、权重迁移、表情与摇摆物理的方法库，见 [Charakuru 方法](references/charakuru-methods.md)。推荐路线：T 型正背设定图 → **整体一次生成** → 在同一网格上拆分结构 → Tripo 重贴图并转回 UV → 表情 → 骨架与权重 → 物理；眼睛、嘴部和表情三样缺一不做：Charakuru 方法论、目标原脸型不变、参考角色的完整表情网络与贴图（含口腔结构），见 [表情前提](references/facial-expressions.md)、[眼眉流程](references/eye-brow-expression-workflow.md)；**不要把头和身体分开生成**（颈部接缝、比例、肤色难以接上，这点与 Charakuru 原版不同）。步骤、经验与 MMD 细节见 [人物流程](references/character-workflow.md)。与 MMD / 原神 PMX 角色同框时的眼睛精细化（眼白上睑阴影、分层瞳孔、发光闪点）见 [眼睛精细化](references/eye-refinement.md)，脚本在 `scripts/eye_refine/`。Houdini 无界面裙发解算见 [houdini-cloth-hair](references/houdini-cloth-hair.md)；整首分段解算、已认可段只解后段拼接、真实多层裙解算（层间缝合、裙撑、灰模验收）、远端 Linux 安装、授权按机器占用的规则与分块整理见 [houdini-fullsong-remote](references/houdini-fullsong-remote.md)，脚本在 `scripts/houdini_song/`。

先核对 A/T 姿态、头身比例、手指、前后轮廓与遮挡。多视图必须同角色同姿态；不可靠侧背图不应强行参与生成。隐藏面属于补全假设。

## 生成与恢复

- `doctor` 离线检查配置；`doctor --online` 只读验证；`models`、`balance` 查询模型与余额。配置服务兼容约定见 [代理 API](references/proxy-api.md)。
- 获取当前模型 value、支持参数和价格，不把历史型号或代理参数当作官方通用规格。已有制作授权内可执行生成；仅连接测试不要提交付费任务。
- 优先带原生纹理生成，尽早查看真正的贴图模型。灰模用于辅助诊断，不能代替带纹理检查。
- `upload --file reference.png --record uploads/front.json` 上传参考；将返回 token 与当前 model value 填入 examples/image-to-model.json 的副本。
- `submit --request request.json --job jobs/v1 --dry-run` 离线校验后，使用同命令 `--execute` 提交。
- `wait --job jobs/v1 --timeout 45`，退出码 3 表示继续等待；成功后 `download --job jobs/v1 --extract`。
- 同请求复用 job；改参数用新目录。POST 结果未知时先对账再 recover，不盲目重提。原生下载与收费格式转换要区分。

## Blender 验收

保留原始生成文件，在副本中修整。渲染真实模型正面、侧面、背面与旋转检查，不能把二维生成图当模型效果。检查手指、面部、贴图接缝、发根、头饰、尾巴体积与连接、翼根和手臂穿插。

保持用户认可的原生贴图与五官比例；三渲二无法修复错误几何或烘焙在贴图中的污染。局部替换需三维贴合与侧面验收，不能只看正面投影。尾巴/头发等组件需有连续根部和适当厚度。

静态交付无需强行绑骨。需要动画时执行 prereigcheck → rig → flags/animations → retarget，检查真实变形。MMD 表情、骨骼映射及衣发物理单独制作与验证；两个独立生成头不能直接视为连续眨眼形态键。

## 交付

按人物与版本组织定稿目录，Blender 贴图内嵌或完整相对路径，按需提供 GLB、真实渲染和旋转视频。报告完成阶段、已检查角度和剩余问题。用户只要模型包时，不夹带视频/过程文件；只报告实际验证过的动画能力。

离线回归：`python scripts/test_proxy.py`。脚本检查接口行为，不证明生成质量、蒙皮或物理通过。

原生嘴型迁移、VMD 表情轨道接入及嘴周碎片/肤色问题，见 [嘴型迁移与修复](references/mouth-transfer-vmd-repair.md)。
