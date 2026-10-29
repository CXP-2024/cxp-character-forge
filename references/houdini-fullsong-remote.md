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
6. **Indie 授权按机器占用，不按进程**：一份 Houdini Engine Indie 只对应 **1 台机器**。被占用时 `sesictrl print-license` 显示 “in use by 用户@主机名”；**同一台机器上可以同时开任意多个 hython**，其他机器则报 “No licenses could be found”。本机 Windows 的 hython 用的也是同一个云端席位。所以 1 份授权时，本机和远端**不能同时**跑，要把全部段集中放到一台机器上。要两台同时跑，只能再加一份授权（可以是另一个账号：本机 `sesictrl login` 登录另一个账号，远端保留原账号，互不抢）。
7. **验证**：同一段 `solve_seg.py` 远端与本机结果最大差 0.04 mm，远端 1m45 vs 本机 2m07。安装日志里只有含 password 字样的文件名，仍一并删除；用户截图泄露过的 secret 提醒其重新生成。
8. **不要用 `hserver -q` 停本机（Windows）的授权服务**。HoudiniServer 是以 LocalSystem 运行的 Windows 服务，强停后再启动会丢失登录：日志 `C:\Windows\TEMP\houdini_temp\hserver.log` 报 `422 You must be logged in / Error L01`，License Administrator 卡在 “Connecting to license”，hython 报 `Timeout was reached [http://127.0.0.1:1714]`。修复步骤：
   - 结束卡死的 `hserver.exe` 和 `hkey.exe` 进程，再执行 `Start-Service HoudiniServer`；
   - 在用户自己的终端运行 `sesictrl login`，账号和密码由用户输入；
   - 如果 `sesictrl print-license` 里只有 `localhost:1715`，执行 `hserver -S https://www.sidefx.com/license/sesinetd` 把云端服务器加回去。
   
   要让出席位时，只需结束本机所有 hython，席位过几十秒就会释放。

## 真实多层裙解算（替代锥形模拟裙，推荐）

锥形模拟裙替代不了多层裙正面的层次，抬腿时会出现大腿穿模，后处理怎么推挤都盖不住（用户否决过“前裙片跟腿抬起”这种补丁）。根本解法：直接对真实裙网格做 Vellum 解算（本例共 3694 点，包括围裙、前后裙片、内裙、荷叶边），脚本为 `solve_real2.py DIR warm SEG0 SEG1 OUT.npy [json]`：

- **固定**：
  - 腰头（绑定 blend ≥ 1）和小于 200 点的独立小件硬固定到蒙皮裙上；
  - 腰下过渡区（0 < blend < 1）软固定，强度 40，跟随动画；
  - 小布条在输出时改为刚性跟随最近的 12 个布点（Kabsch），避免它们戳出新裙面。
- **预热从静止 T 姿势开始**：先用 smoothstep 过渡到 SEG0 的舞姿，再保持 15 帧。如果直接在舞姿里起步，腿已经插在裙子里，布料一开始就被卡住。
- **层间缝合**：先用 `glue_pairs.py DIR`（普通 Python；hython 没有 scipy）找出空间距离 < 3 cm、但沿网格表面距离 > max(3d, d+2 cm) 的点对，也就是上下叠着的两层。每点最多 2 条，按最短优先，本例共 2070 对。再用 distance 约束连上，刚度 50 就够（2000 看起来一样）。不加缝合的话，后侧内裙会脱离外层蓝裙、贴在大腿上。
- **腿部碰撞摩擦关掉**：solver 的 `friction` 是整数开关，设 0；层间自摩擦保留。不关的话，布料会被腿带着粘在大腿上。
- **裙撑**：抗弯刚度从 0.02 提到 **1.0**。太软时后摆失去蓬度，会塌在腿上。另一种做法是对全部自由点加 soft pin 拉向设计形状：强度 5 时布料被拉进穿模的蒙皮形，大腿露出来；强度 20 能撑住，但布料偏“定型”。用户最终选的是抗弯 1。
- **速度**：本机每帧约 3–3.5 s（3 个进程并行时），比锥形模拟裙慢，但原来那条整理链（refine/defold/contact）基本可以省掉。
- **饰品重挂**：用 `acc_follow.py OLD_DIR NEW_DIR A B`。蝴蝶结按最近 24 个裙点做刚性跟随；Acc_BB 的每个点跟随最近 6 个裙点的位移（新减旧）。
- **预览拼接**：
  - `patch_prev.py SRC OUT NPY A [淡入] [淡出]` 把一段解算贴进缓存副本；
  - `splice_windows.py` 拼接多段。
  
  注意：只修一小段时，接回旧缓存的过渡帧会重新穿模。用户在过渡帧（本例 1795）一眼就能看出来，所以给用户看之前就要把解算范围覆盖到问题区间之后。
- **验收必须看灰模**：用 Workbench 单一灰色加棚灯，关掉 MMD 描边的 solidify（脚本 `clay_ds2.py`）。贴图渲染会掩盖穿模和塌陷；每次检查都要用灰模，看用户指出的帧，并从正面、侧面、背面多个角度看。

## 速度与调度

- Vellum 逐帧依赖，单个解算即使在 180 核上也只用约 4 核；加速靠**分段并行**（每段带预热、段间 60 帧混合），段数受“授权份数 = 可同时用的机器数”限制，每台机器上能开几段由 CPU 决定（见下）。
- **`nproc` 会骗人**：容器里 `nproc`/`lscpu` 显示的是宿主机的核数（本次 180），实际只分到平台配额的 vCPU（本次 20 vCPU / 220 GiB）。核数以平台控制台为准。
- 每个 hython 默认按看到的核数开线程。13 个进程同时开在 20 vCPU 上时，每帧 15 s（本机单进程约 3 s）。正确做法是设 `HOUDINI_MAXTHREADS=4`，同时只跑约 `vCPU/4` 个进程（20 vCPU 跑 5 个），由排队脚本轮流认领各段。
- 实测吞吐：远端 Linux 容器 20 vCPU 跑 5 进程，每帧 6–9 s，合计约 0.7 帧/秒；本机 Ryzen 7 9850X3D（8 核 16 线程）跑 3 进程，每帧约 3.3 s，合计约 0.9 帧/秒。两台都有授权时同时跑，时间约减半。
- 排队认领：`seg_queue.sh HYTHON DIR BASE "starts..." LEN TAG OVJSON` 用 `mkdir 段.lock` 原子认领。两台机器分工时，先在远端为本机要跑的段建好 lock（如最后 4 段），本机从后往前、远端从前往后认领。
- 测速只看前 20–40 帧的 `SOLVE` 日志（5 分钟内就能判断），不要等整段跑完。
- 本次整首两人 4886 帧/人：本机两路并行约 58 分钟；远端整理约 11 分钟；蝴蝶结与拼接约 15 分钟。用户的重任务上限是同时 4 个。
- 解算日志经 `grep` 过滤会缓冲到结束才出现进度；要看进度用 `--line-buffered` 或直接写日志文件。
