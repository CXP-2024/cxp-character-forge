# CXP Character Forge

**从一张角色立绘开始，由 AI agent 一步步做出能跳 MMD 舞的 3D 角色。**

这是一个给 AI 编程 agent（Claude Code、Codex）用的 skill，覆盖从零开始做 MMD 角色的整条流程：设定图 → Tripo 生成模型 → 拆件 → 绑定与骨架校验 → 分组件重贴图 → 眼睛、嘴部和表情 → 衣服和头发物理 → 套 MMD 动作 → 渲染。每一步都写了做法、验收标准，以及实际项目里踩过的坑和解决办法。

它不是一键生成器。流程来自一个真实项目的整套制作：DeepSeek 鲸娘，从立绘做到双人跳完整首《愛包ダンスホール》。skill 里写明了哪些步骤做到了什么程度、哪些还需要人来把关。

## 流程总览

| 阶段 | 做什么 | 文档 |
| --- | --- | --- |
| 0. 准备 | 安装 [Charakuru](https://github.com/nanocle/Charakuru) 源码，作为方法库（三视图、重贴图分组、权重迁移、表情、摇摆物理） | [character-workflow](references/character-workflow.md) 第 0 步、[charakuru-methods](references/charakuru-methods.md) |
| 1. 设定图 | 整理出 T 型正背设定图，两张图的基线、头顶、臂展像素对齐 | [character-workflow](references/character-workflow.md) |
| 2. 生成 | 用 Tripo 一次生成整个人物。**每次只提交一个任务，不抽卡；头和身体不要分开生成** | 同上，以及 [proxy-api](references/proxy-api.md) |
| 3. 拆件 | 先看灰模，当场试拆头、头发和刘海、饰品、裙子；拆不开就重新生成 | [component-texturing](references/component-texturing.md) |
| 4. 绑定 | 快速绑定，套一段简单 MMD 舞蹈校验骨架，让 AI 修骨骼节点和权重 | [rigging-physics](references/rigging-physics.md) |
| 5. 重贴图 | 按组件选方法：Tripo 重贴图、Codex 多视角重画后投影、从几何生成、平涂 | [component-texturing](references/component-texturing.md)、[texture-transfer](references/texture-transfer.md)、[texture-refinement-qa](references/texture-refinement-qa.md) |
| 6. 表情 | 三样缺一不做：Charakuru 方法、原脸型不变、参考角色的表情网络和贴图 | [facial-expressions](references/facial-expressions.md)、[eye-brow-expression-workflow](references/eye-brow-expression-workflow.md)、[mouth-transfer-vmd-repair](references/mouth-transfer-vmd-repair.md)、[eye-refinement](references/eye-refinement.md) |
| 7. 物理 | 真实多层裙的 Houdini Vellum 解算（层间缝合、裙撑），整首分段并行解算，远端 Linux 机器的安装与授权 | [houdini-cloth-hair](references/houdini-cloth-hair.md)、[houdini-fullsong-remote](references/houdini-fullsong-remote.md) |
| 8. 渲染 | 原神风格的三渲二：面部 UV、眼睛分层、服装 ramp、原生 MMD 描边 | 姊妹 skill [genshin-blender-render](https://github.com/CXP-2024/genshin-blender-render) |

制作期间二次元角色默认用原神式快速三渲二材质（EEVEE 下几秒一帧，方便反复迭代），最后一步才用渲染 skill 做精细渲染。每个阶段都要求用灰模加这套材质验收，在同一相机下与参考对比，原始资产只读、修改另存新版本。

## 推荐安装

把本仓库放进 agent 的 skills 目录，agent 就会在做角色时自动加载它。

**Claude Code**

```sh
git clone https://github.com/CXP-2024/cxp-character-forge.git ~/.claude/skills/cxp-character-forge
cd ~/.claude/skills/cxp-character-forge
python scripts/bootstrap.py
```

**Codex**

```sh
git clone https://github.com/CXP-2024/cxp-character-forge.git ~/.codex/skills/cxp-character-forge
cd ~/.codex/skills/cxp-character-forge
python scripts/bootstrap.py
```

装好后直接对 agent 说要做什么角色即可，例如“按这张立绘做一个能跳 MMD 的模型”。Codex 也可以用 `$cxp-character-forge` 显式调用。

### 建议一起安装

| 名称 | 用途 |
| --- | --- |
| [Charakuru](https://github.com/nanocle/Charakuru) | 从 Releases 下载解压。本 skill 用它的方法和脚本做三视图、权重迁移、表情和摇摆物理 |
| [genshin-blender-render](https://github.com/CXP-2024/genshin-blender-render) | 原神风格渲染 |
| [codex-image-gen-skill](https://github.com/CXP-2024/codex-image-gen-skill) | 本地动漫生图：设定图、参考图和局部重画 |
| [gcp-blender-render](https://github.com/CXP-2024/gcp-blender-render) / [paratera-blender-render](https://github.com/CXP-2024/paratera-blender-render) | 在云 GPU 上渲染长片 |

## 运行环境

| 需要 | 用在哪里 |
| --- | --- |
| Python 3.10+、Git | 全部 |
| Tripo 兼容代理和自己的密钥 | 生成模型、重贴图 |
| Blender 5.2 + [mmd_tools](https://github.com/MMD-Blender/blender_mmd_tools) | 拆件、绑定、表情、套 MMD 动作、渲染 |
| Node.js 22+、VRM Add-on | 运行 Charakuru |
| Houdini（Indie 即可） | 衣服和头发的 Vellum 解算。授权按机器计算：一份授权同一时间只能在一台机器上用，但这台机器上可以开多个进程 |

## 配置 Tripo 代理

复制 `proxy-config.example.json` 为 `proxy-config.json`，填写兼容代理地址和本地密钥文件路径。密钥存放在仓库外，文件内容只是服务提供的 token。也可以用 `TRIPO_PROXY_BASE_URL` 和 `TRIPO_PROXY_KEY_FILE` 环境变量。

该适配器面向 `/v1`、返回 `{code: "ok", data: ...}` 的兼容代理，密钥格式为 `tp_live_...` / `tp_test_...`。它不能直接接入官方 `/v3`，也不保证兼容任意代理。

```sh
python scripts/tripo_proxy.py doctor            # 离线检查配置
python scripts/tripo_proxy.py doctor --online   # 只读联网检查，不提交任务
python scripts/tripo_proxy.py models
python scripts/test_proxy.py
```

只读检查不会提交生成任务。实际生成会消耗服务额度，费用由服务决定。

## 仓库结构

```
SKILL.md                      agent 入口：路线、按任务查资料的索引
references/                   各阶段的方法、验收标准和踩坑记录
scripts/tripo_proxy.py        Tripo 代理客户端：提交、等待、恢复、下载
scripts/component_tex/        分组件重贴图：Tripo 前后 UV 写回、多视角投影烘焙、局部重画、金边纽扣几何、手部平涂、无光照材质
scripts/eye_refine/           眼睛精细化：眼白上睑阴影、分层虹膜、发光闪点
scripts/houdini_song/         Houdini 裙子解算：真实多层裙、整首分段排队、拼接、饰品重挂、灰模检查
```

脚本里的项目路径都改成了参数或环境变量；各脚本的用法写在文件开头的注释里。

## 来源与边界

在 Tripo 公开人物工作流和 Charakuru 方法的基础上，我们加了代理客户端、离线回归、分阶段验收流程和一整套制作经验。依赖与来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；固定版本下载有 SHA-256 校验。

本项目不是 Tripo 或 Charakuru 的官方产品，不包含模型资产、密钥、商业服务额度，也不附带 Charakuru 的人体和表情素材，使用这些素材请遵守它们各自的许可。skill 不承诺全自动产出合格的表情或物理：每一步都需要按文档验收，结果因角色而异。
