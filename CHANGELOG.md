# 更新说明

## v1.5.0 - 代码结构与发布包优化

### 主要变更

- 根目录 `main.py` 改为轻量入口，插件完整实现集中在 `astrbot_plugin_volcengine_asr/main.py`，降低双份主逻辑维护成本。
- 修复 `voice_prompt_template` 渲染边界问题：当语音转写内容包含 `{}` 时，不再误触发模板格式化回退。
- 保持 LivingMemory 两阶段注入语义：消息阶段写入干净转写文本，LLM 请求阶段再套语音提示词。
- README 补清 Release zip、GitHub 仓库安装、源码 zip 的区别，并说明 `ffmpeg` 查找顺序。
- README 补齐 `stop_event_after_recognition`、`send_empty_result_message` 配置说明，并写明火山 endpoint 默认值。
- 新增基础 helper 测试，覆盖提示词渲染、Base64 大小估算、音频后缀识别和首个文本替换。
- 更新 README 视觉资源：扁平化 VoiceMountain 头图，以及严格参考 ShitMountain 尺寸和布局的 fuck-u-code 小徽章。

### 安装包说明

- Release zip 根目录直接包含插件文件，不额外套同名目录。
- Release zip 包含 Linux x86_64/amd64 内置 `ffmpeg`，适合 Docker 或 VPS 环境。
- 不要使用 GitHub 绿色 Code 按钮下载的源码 zip 代替 Release zip。

### 验证项目

- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile main.py astrbot_plugin_volcengine_asr/main.py`
- 配置 JSON 校验通过。
- README 配置项覆盖检查通过。
- helper 测试通过。
- Release zip 根目录结构、版本和内置 `ffmpeg` 校验通过。

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
