# 更新说明

## v2.0.0 - 情绪判断 LLM

### 主要变更

- 新增可选的情绪判断 LLM 流程，默认关闭。语音转写成功后，插件可以额外请求一次 LLM，根据当前转写文本和可用上下文输出结构化情绪 JSON。
- 新增本地量化公式，使用情绪分布的 Shannon entropy 确定性、情绪判断 LLM 自评置信度、文本/上下文证据强度计算 `respect_weight`，限制主 LLM 对情绪判断的参考程度。
- 情绪判断结果只追加到主 LLM 的 `llm_text` 辅助提示，不写入 `event.message_str`、`message_obj.message_str` 或消息链，继续保证 LivingMemory 只记录干净转写文本。
- 新增情绪判断配置项：`enable_emotion_analysis`、`emotion_model_id`、`emotion_context_turns`、`emotion_max_respect_weight_percent`、`emotion_timeout_seconds`、`emotion_fail_open`、`emotion_prompt_template`。
- `/volc_asr_status` 增加情绪判断状态、模型选择和最大参考权重展示。
- README 新增情绪判断模块说明，覆盖工作流、JSON 输出格式、理论依据、计算过程、主 LLM 辅助块示例和 LivingMemory 兼容边界。
- helper 测试扩展，覆盖 JSON 解析、情绪权重归一化、熵确定性、参考权重计算、情绪提示词构造和主 LLM 辅助块追加。

### 注意事项

- 情绪判断默认关闭；开启后会增加一次额外 LLM 调用，带来 token 消耗、响应延迟和上下文暴露范围增加。
- 情绪判断不是心理诊断，只用于帮助主 LLM 调整回复语气、共情程度和安抚强度。
- Web UI 相关开发将从 main 拆分到独立分支，不包含在本次 v2.0.0 主线更新中。

## Web UI 分支更新

### 主要变更

- 新增 AstrBot Plugin Pages Web UI 控制台：`pages/status/index.html`。
- 新增状态和配置接口：`/api/plug/astrbot_plugin_volcengine_asr/status`、`/api/plug/astrbot_plugin_volcengine_asr/config`。
- 控制台展示 ASR 鉴权、提交模式、转码链路、情绪判断 LLM 配置、触发范围和 LivingMemory 兼容状态。
- 支持在 Web UI 中编辑插件配置，并按 `_conf_schema.json` 做类型转换和可选值校验后写回配置。
- 配置分组切换、状态卡片和保存提示加入过渡动画。

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
