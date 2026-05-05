# 更新说明

## v1.4.7 - LivingMemory 兼容重构

本版本针对 `astrbot_plugin_livingmemory` 的消息处理方式重构了语音注入流程。

### 背景

旧版本在识别语音后，会直接把当前消息改写成带 `voice_prompt_template` 的完整提示词。这个做法能让 LLM 正常回复，但 LivingMemory 在记录群聊消息、私聊对话和执行记忆召回时，也会读到这段提示词包装内容，导致长期记忆里混入“请尽量使用语音回复”等模板文字，甚至在部分路径中仍然只能看到 `[语音]`。

### 主要变更

- 语音识别完成后，事件里的 `message_str`、`message_obj.message_str` 和消息链会先被改写为纯转写文本。
- 新增 `on_llm_request(priority=-10)` 处理阶段，在 LivingMemory 完成检索和存储之后，再把 LLM 请求里的纯转写文本替换为 `voice_prompt_template` 渲染后的内容。
- 未听清、静音或识别为空时，LivingMemory 记录的是简短的“用户发送了一条语音，但未识别出有效内容。”，LLM 仍然收到配置里的 `unclear_voice_prompt`。
- 保留 `volcengine_asr_text`，并新增内部事件标记用于区分纯转写文本和 LLM 提示词文本，便于排查插件链路。

### 适配效果

- LivingMemory 群聊全量捕获会记录语音的真实转写内容。
- LivingMemory 私聊记忆召回会用真实转写内容作为搜索关键词。
- LivingMemory 私聊消息存储不会再写入语音提示词模板。
- LLM 最终仍然能收到本插件配置的语音回复引导，不影响“语音进、语音出”的使用方式。

### 安装包说明

- GitHub 仓库根目录继续保留 `metadata.yaml`、`main.py`、`_conf_schema.json` 和 `requirements.txt`，支持 AstrBot 从仓库地址安装。
- Releases 中的 `astrbot_plugin_volcengine_asr.zip` 根目录直接包含插件文件，不再额外套一层同名目录，避免 AstrBot 安装时找不到 `metadata.yaml`。
- Releases 压缩包仍包含 Linux x86_64/amd64 内置 `ffmpeg`，适合 Docker 或 VPS 环境。

### 验证项目

- `python -m py_compile main.py astrbot_plugin_volcengine_asr/main.py`
- 重新打包 `astrbot_plugin_volcengine_asr.zip`
- 检查 zip 根目录包含 `metadata.yaml` 和 `main.py`
- 检查 zip 内 `metadata.yaml` 版本为 `1.4.7`
