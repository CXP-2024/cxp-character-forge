# 来源说明

本项目的代理适配工作基于 SucRunBug/tripo-3d 的 CLI 接口与公开工作流：
https://github.com/SucRunBug/tripo-3d

依赖固定于 commit 2162e925f1ed88e00e66346ba2b534237b710c9c。
`scripts/bootstrap.py` 从上游下载 `tripo.py` 与 `inspect_glb.py`，校验 upstream-lock.json 中 SHA-256。两份上游文件不纳入本仓库版本控制。

截至 2026-10-23，上游未声明仓库许可证。本仓库不为上游内容授予额外许可，使用或再分发依赖应遵守原作者权利与适用条款。API/商标属于各自提供方，代理和官方接口不能混用。参考教程链接在 references/character-workflow.md 中。

仓库中的代理适配、配置示例、安装辅助与新增工作流由 CXP-2024 维护。未附带人物设计、模型、贴图或付费服务凭据。
