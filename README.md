# CXP Character Forge

参考立绘 → Tripo 兼容代理生成 → Blender 多角度验收 → 按需修整与动画 → 整理交付的 Codex skill。

支持请求离线校验、任务续作、未知提交恢复、原生下载与只读连接检查。保留原生贴图，区分静态模型、绑骨、MMD 表情及物理的实际完成程度。本项目不是 Tripo 官方产品，也不包含模型资产、密钥或商业服务额度。

## 安装

需要 Python 3.10+、Git。Blender 渲染阶段另需 Blender；仅使用 API CLI 无需 Blender。

```sh
git clone https://github.com/CXP-2024/cxp-character-forge.git
cd cxp-character-forge
python scripts/bootstrap.py
```

将仓库放在 Codex skills 目录，例如 `~/.codex/skills/cxp-character-forge`，然后使用 `$cxp-character-forge`。

## 配置

复制 `proxy-config.example.json` 为 `proxy-config.json`，填写你使用的兼容代理地址和本地密钥文件路径。密钥存放在仓库外，文件内容仅为服务提供的 token。也支持 `TRIPO_PROXY_BASE_URL` 与 `TRIPO_PROXY_KEY_FILE` 环境变量。

该适配器面向 `/v1`、`{code: "ok", data: ...}` 响应的兼容代理，密钥格式为 `tp_live_...` / `tp_test_...`；不是可直接接入官方 `/v3` 的客户端，也不保证任意代理兼容。

```sh
python scripts/tripo_proxy.py doctor
python scripts/tripo_proxy.py doctor --online
python scripts/tripo_proxy.py models
python scripts/test_proxy.py
```

只读检查不会提交模型生成。实际生成需要配置服务的有效额度，费用由服务决定。具体用法见 [SKILL.md](SKILL.md) 与 [代理接口说明](references/proxy-api.md)。

## 来源与边界

我们新增了代理客户端、离线回归和人物验收工作流。依赖与来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。固定版本下载有 SHA-256 校验。项目没有附带未经验证的自动修脸、连续眨眼或完整 MMD 物理承诺。
