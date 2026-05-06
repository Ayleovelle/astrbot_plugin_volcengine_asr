# 更新说明

## v2.0.3 - 加固 agent 音频残留清理

### 主要变更

- 继续修复 AstrBot v4.24.2 agent 阶段可能读取旧 `.amr` 语音段并报 `not a valid file: xxx.amr` 的问题。
- 识别成功或未听清注入时，先原地改写旧消息链 list，再同步替换 `event.message`、`event.message_chain`、`event.raw_message`、`message_obj.message`、`message_obj.message_chain`、`message_obj.raw_message` 等入口，避免 AstrBot 或其他插件持有旧 list 引用时继续读到 `Record`。
- LLM 请求阶段增加 `ProviderRequest` 净化，清空 `audio_urls`，并移除 `contexts`、`extra_user_content_parts`、`messages`、`content`、`files` 等字段中残留的音频附件、裸 `.amr` 路径和对象型 audio part。
- 事件缓存清理扩展到 `event.extras`、`event._extras`、`event.extra` 以及 `message_obj` 上的同名缓存，降低适配器私有缓存继续传递旧语音段的风险。
- `_find_records()` 增加裸 OneBot `record` dict 兼容，`raw_message={"type":"record","data":{"file":"x.amr"}}` 这类结构也能正常识别。
- 增加回归测试，覆盖旧消息链 list 原地改写、ProviderRequest 多字段音频净化、对象型 audio part 清理、message_obj 缓存清理和裸 record dict 读取。

## v2.0.2 - 修复语音 Record 残留

### 主要变更

- 修复 AstrBot v4.24.2 agent 阶段可能继续读取旧 `.amr` 语音段并报 `not a valid file: xxx.amr` 的问题。
- 识别成功或未听清注入时，插件会把 `event.message`、`event.message_chain`、`event.raw_message`、`message_obj.message`、`message_obj.message_chain`、`message_obj.raw_message` 等常见入口同步替换为纯 `Plain` 文本。
- LLM 请求阶段增加二次消息链净化，确保 LivingMemory 和主 LLM 链路继续使用干净转写文本。
- `_find_records()` 兼容 `message`、`message_chain`、`raw_message` 与 OneBot dict 形态，降低不同适配器消息结构差异带来的识别失败风险。
- `_extract_record_sources()` 支持对象属性、dict 顶层字段和 `data.file` / `data.url` / `data.path` 嵌套字段。
- 增加回归测试，覆盖语音段兼容查找、OneBot dict 来源解析，以及注入后原始 `Record` 不再残留。

## v2.0.1 - 代码与工作流程优化

### 主要变更

- 优化了代码以及工作流程。
- 拆分语音识别批处理逻辑，降低消息处理主流程复杂度。
- 复用 HTTP 客户端下载语音文件，并在下载前优先检查 `Content-Length`，减少超大音频的无效传输。
- 统一识别结果模板字段构造，降低回复文本和 LLM 注入文本字段不一致的风险。
- 为未来 Web UI 预留稳定接口：`get_webui_state()`、`get_webui_config_schema()`、`get_webui_config_snapshot()`、`update_webui_config()`。
- `update_webui_config()` 增加字段白名单、类型转换、选项校验、整数范围校验、密钥掩码跳过和运行时配置重载，避免 Web UI 保存时覆盖真实密钥。
- `get_webui_state()` 补充鉴权模式、校验错误、接口地址、资源 ID、超时、转码参数和识别参数，未来 Web UI 状态页可以直接复用。
- 优化事件 extra 写入路径，便于后续 Web UI 和排障流程复用状态数据。
- 新增可追踪的 Release zip 构建脚本 `scripts/build_release_zip.py`，生成 `output/astrbot_plugin_volcengine_asr.zip` 并保留内置 `ffmpeg` 可执行权限。
- 确认 `fuck-u-code` 分数由 GitHub Actions bot 接管，自动分析、更新两份 `FuckUCodeScore.svg`，人工不再直接改分数。
- 修复部分 AstrBot 仓库安装方式下根目录入口找不到 `astrbot_plugin_volcengine_asr` 包的问题。
- 修正安装说明，明确从链接安装必须使用完整 `https://github.com/...` 地址，不能省略 `https:`。
- 同步包内 `requirements.txt`，让仓库安装模式也能安装 `imageio-ffmpeg` 作为 ffmpeg 兜底。
- 扩展 helper 测试，覆盖 Web UI 预留接口、注入事件标记和识别结果模板字段。

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
