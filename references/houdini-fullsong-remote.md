# Houdini 裙子整首解算、分段拼接与远端（远端 Linux 容器）安装授权

接续 [houdini-cloth-hair.md](houdini-cloth-hair.md)。本篇来自 2026-10-29 爱包双人整首（DeepSeek 鲸娘 ×2，Hime/Hina 官方 VMD，6580 帧）的实际交付，用户认可前 60 秒后再延长到整首。路径为本机示例。

## 流程总览（每个舞者一套，两人可并行）

```
src.blend（该舞者完整动作）
 → export.py / export_acc.py / export_hair.py  F0 F1      # 腿、裙蒙皮、髋、饰品、头发碰撞，世界坐标
 → patterns.py DIR 96 34                                  # 低分辨率锥形模拟裙
 → hython solve.py DIR 45 '{cloth/solver 参数}'           # Vellum，45 帧预热保持首帧姿势
 → transfer → refine → transfer2(挤压) → refine → defold → refine(8mm) → defold → contact
 → bows.py / ribbon_prep / chain_prep / spring_tails / acc_cache   # 蝴蝶结、飘带
 → write_f0rest / splice_song.py                          # 第 0 帧写静止形，接到已认可段
```

脚本在 `<project>/skirt_vellum/`：`stageA.sh`（导出+解算）、`remote_post.py`（远端分块整理）、`stitch_extra.py`、`splice_song.py`；Blender 侧 `<project>/scripts/`：`ds_extend.py`（动作延长）、`ds_attach_song.py`（挂缓存）。

参数（已认可）：`bendstiffness 0.015, thickness 0.003, density 0.18, benddampingratio 0.08, substeps 5, niter 80`；整理链 `chain_v79.sh DIR 0.006 0.004`。

## 已认可段不重算：只解后段再拼接

- 用户问“难道要重新跑？”——不要。前 60 秒（0–1800）原样保留，从 **1740** 帧开始新解（带 45 帧预热），在 **1740–1800** 用 smoothstep 混合到新段（`splice_song.py OUT OLD_SKIRT_MDD OLD_ACC_DIR SEGDIR`）。
- 验收：接缝窗口每帧最大位移要落在整首正常运动的 p95–p99 以内（本次 68–72 mm vs p95 62–97 mm），并抽一帧与旧版逐像素对比（第 1000 帧差 0）。
- 动作延长同理：0–1800 关键帧不动，只追加 1801 起；检查 1795–1807 每帧骨骼最大位移连续。
- 开头只有某几帧坏（例如第二人第 0 帧瞬移 38 cm 把裙子甩开）：用 `solve_seg.py DIR 45 0 120` 只重算 0–120（约 2 分钟），90–120 平滑接回原 cloth，后面完全不变。**不要整段重跑**（用户明确指出“只需要处理开头片段”）。
- T-pose 第 0 帧站位修了以后，所有 `*_f0rest.mdd` 的第 0 帧（静止形）也要平移到同一位置，否则 reset 帧裙子离体、看起来大一圈。

## 只有 60 秒长的缓存会在 1800 帧后冻住

延长时间轴前列出全部 `MESH_CACHE`（帧数），逐个处理：裙子/饰品重新解算；只是蒙皮烘焙出来的（如头发 `hair_skinned.mdd`）直接换回 Armature 修改器，先在 1/300/900/1500/1800 帧与旧缓存逐点比对（本次 0 mm）再删缓存。

## 远端整理（远端 Linux 容器）：按帧分块并行

- 整理链按帧独立（只做小范围时间平滑），可按 150 帧一块、前后各 24 帧填充切块，40 个进程并行，拼接时丢掉填充（`remote_post.py DIR 150 24 40`）。本次 4841 帧/人约 11 分钟（本机串行约 75 分钟）；60 秒测试 3 分 42 秒 vs 本机 20 分钟。
- 先用一段已有本机结果做一致性测试：本次 99.93% 顶点完全一致、分块边界无跳变；剩余零星差异来自不同 numpy/BLAS 版本。
- 远端 Python：系统 3.8 无 pip → 用随附 Miniforge 装独立环境（`/root/mf3`），国内镜像 `a nearby PyPI mirror`；需要 `numpy scipy trimesh rtree`。子进程设 `OMP_NUM_THREADS=1`。
- **坑**：下游 `bows.py` 还要 `push_grid.npy`（refine 的中间产物），分块后只拼了 `skirt_refined.npy` → 缺文件报错。用 `stitch_extra.py DIR 150 24 push_grid.npy` 在远端同样拼好再拉回。
- 传输走直连：`ssh/scp -o ProxyCommand=none -o ProxyJump=none -o ClearAllForwardings=yes -P PORT`，内容用 `tar | ssh tar` 管道；百 MB 级数秒。

## Houdini 在远端 Linux 容器上的安装与授权（Indie）

1. **安装器**：用户从 SideFX 下载 `install_houdini_launcher.sh`（约 100 MB），传上去后 `bash install_houdini_launcher.sh --no-desktop-menus /opt/sidefx/launcher`。提示 “Cannot install service hserver using init” 是容器无 init，可忽略。
2. **命令行安装不会交互问账号**，必须 `--settings-file`（key=value，无分节）：`username/password` 或 `client_id/client_secret`，外加 `accept_eula=SideFX-2021-10-13`（是否接受由用户决定）。文件由用户自己在终端写（`umask 077; cat > file`，Ctrl+D 结束；按 Ctrl+C 则输入作废、文件为空），装完立刻删除。
3. **第三方登录账号**（Google/Apple 等）报 “Your password is not stored by sidefx.com” → 只能用 API Key：sidefx.com/oauth2/applications 新建应用，Client type `Confidential`，Grant type **Client credentials**，并且 **Redirect uris 必须填一个**（如 `http://localhost:8080/`）。留空时安装器用的 `oauth2/application_token` 接口返回 “Missing redirect URI.”，即使授权类型已正确；表单下拉框刷新后也可能没真正选上，保存后到详情页核对。诊断法：`curl -u ID:SECRET -d grant_type=client_credentials https://www.sidefx.com/oauth2/token/` 返回 `invalid_scope` 说明凭证有效，问题在应用配置。
4. **平台识别失败**（Ubuntu 20.04 容器）：“Could not determine the platform string automatically” → 加 `--platform linux_x86_64_gcc14.2`。完整命令：
   `LANG=C.UTF-8 houdini_installer install --product Houdini --version 22.0.466 --platform linux_x86_64_gcc14.2 --installdir /opt/hfs22.0.466 --settings-file FILE`（约 5 GB，远端机 上几分钟）。
5. **授权**：`hserver -S https://www.sidefx.com/license/sesinetd --clientid/--clientsecret` 不会登录（日志 “422 You must be logged in”）。正确做法：`mkdir -p /usr/lib/sesi/hserver`（否则 sqlite/cookie 存储报错），然后 `source houdini_setup_bash; sesictrl login --client-id ID --client-secret SECRET`。`sesictrl print-license` 查看实际授权；登录在 hserver 重启后仍保留，容器重启后先运行 `hserver`。
6. **Indie 授权数量**：示例账号有 Houdini Engine Indie ×1、Renderer ×1、Karma ×1 → 远端同时只能跑 **1 个** hython；与本机 Houdini 授权互不占用。hython 报 “No licenses could be found” 时先查是否已登录、是否已有一个 hython 占用。
7. **验证**：同一段 `solve_seg.py` 远端与本机结果最大差 0.04 mm，远端 1m45 vs 本机 2m07。安装日志里只有含 password 字样的文件名，仍一并删除；用户截图泄露过的 secret 提醒其重新生成。

## 速度与调度

- Vellum 逐帧依赖，单个解算即使在 180 核上也只用约 4 核；加速靠**分段并行**（每段带预热、段间 60 帧混合），段数受 Houdini 授权数限制（本机 + 远端各 1）。
- 本次整首两人 4886 帧/人：本机两路并行约 58 分钟；远端整理约 11 分钟；蝴蝶结与拼接约 15 分钟。用户的重任务上限是同时 4 个。
- 解算日志经 `grep` 过滤会缓冲到结束才出现进度；要看进度用 `--line-buffered` 或直接写日志文件。
