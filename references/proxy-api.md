# Tripo 兼容代理接口

这是已验证代理的接口约定，不等同于官方 API。接口与价格应以配置服务的 models 与 OpenAPI 为准。

## 查询与错误

CLI：doctor --online、balance、usage、models、status/flags/animations --task-id ID。查询免费，doctor 只 GET balance/models/openapi.json。

成功 JSON `{code:"ok",data:...,request_id:...}`；错误按 HTTP 和 code 分支，保留 request_id。400 修改请求；429 rate_limited 遵循 Retry-After；配额超限等待重置；502/503 可退避重试查询。客户端不自动重试 POST，避免未知结果重复扣费。

任务列表 GET /tasks?page=0&size=20 可用于对账，通过 Client.api 调用；usage 只有用量汇总。密钥只在代理 API 的 Authorization: Bearer 中发送，API 重定向被拒绝；CDN 使用独立无鉴权连接。

## 上传与模型

`upload --file front.png --record uploads/front.json`：POST /uploads，multipart 字段 file，整个 body ≤20 MiB，图片 png/jpg/jpeg/webp/gif/bmp，返回 file_token。

`upload --file own.glb --record uploads/own.json`：POST /uploads/model，模型 glb/obj/fbx/stl ≤150 MiB，直接导入并返回 task_id。不能把它当 file_token，也不再 POST import_model。上传免费但有真实上游动作，连接检查不用上传。

模型字段是 model，不是 model_version。使用前查 models，目前 H3.1=v3.1-20260211、H3.0=v3.0-20250812、H2.5=v2.5-20250123、P2=Nexus-v2.0-20260801、P1=Nexus-v1.0-20260214。P2 目录当前三角面上限50000、四边面25000。价格缺失表示未知/阶梯价，不是免费。

## 原生请求模板

以下占位符必须替换，不代表已生成。submit 必须显式 --dry-run 或 --execute；dry-run 不读取密钥、不联网，也不完整验证上游参数。

单图 P2 人物：
```json
{"endpoint":"/tasks","payload":{"type":"image_to_model","input":"FILE_TOKEN","model":"Nexus-v2.0-20260801","face_limit":15000,"quad":true,"texture":true,"pbr":true,"texture_quality":"standard"}}
```

多视图：files 严格四槽位正/左/背/右，正面必填且至少两张，每项是对象，空位 null：
```json
{"endpoint":"/tasks","payload":{"type":"multiview_to_model","files":[{"file_token":"FRONT_TOKEN"},null,{"file_token":"BACK_TOKEN"},null],"model":"Nexus-v2.0-20260801","quad":true,"face_limit":15000}}
```

文生模型 type=text_to_model，加 prompt。generate_parts=true 时 texture=false、pbr=false。其他类型与必填参数查 x-task-params；客户端的基本校验不替代服务端规格。

绑定检查（本代理同步返回，保存在 job.result，无需轮询）：
```json
{"endpoint":"/tasks","payload":{"type":"animate_prerigcheck","original_model_task_id":"MODEL_TASK_ID"}}
```

查看实际检查输出确认可绑骨，不能假设官方 result.output.riggable schema。绑定仍引用原模型 ID，而不是检查记录 ID：
```json
{"endpoint":"/tasks","payload":{"type":"animate_rig","original_model_task_id":"MODEL_TASK_ID","spec":"mixamo"}}
```
spec 以代理文档为准：actorcore/mixamo/unreal/unity/vrm，不能套用官方旧例 spec=tripo。等绑骨成功，再应用动作：
```json
{"endpoint":"/tasks","payload":{"type":"animate_retarget","original_model_task_id":"RIG_TASK_ID","animations":["idle","walk"]}}
```
提交动作前客户端确认 flags.is_rigged=true；动作名/骨架以 animations 和 x-animation-presets 为准。animations 与 motion_asset_id 二选一。检查下载文件真正包含的 clips。

贴图：type=texture_model、original_model_task_id、texture_quality=standard/detailed/extreme。转换：type=convert_model、original_model_task_id、format=glb/gltf/fbx/obj/stl/usdz/3mf（小写），会计费。不开放 local_edit、stylize_model、import_model、refine_model 等。

## 下载与恢复

download 先 GET /tasks/{id}/download?link=1，取 data.url/filename/expires_at/expires_in，不传 type、不触发转换。CDN 下载不带密钥；链接过期重取，不重新生成。helper 当前取默认产物，不代表所有图片/动画附件都已收齐。多图按 index/view 用 Client.api 取直链，再用原版 fetch_asset 无鉴权下载；动画先查 animations 并按产物逐项收集。

POST 网络异常保持 unknown。同 job 不自动重提，即使之前拒绝也先核对。核对任务列表、时间、输入后使用 `recover --job jobs/model-v1 --task-id EXISTING_ID`，该命令只关联现有任务，不自动证明请求内容一致。API 返回过期链接或失败，不默默创建替代任务。

模型报价以当前目录和后台档位为准，P2 查询曾返回 credits=100；附加计费不能套用官方价格。余额/frozen/积分有效期查 balance；接口未标时区不要猜。正式生成与上传、同步检查、下载尚需在用户授权的具体制作中真实验证，本次只验证只读连接与离线行为。
