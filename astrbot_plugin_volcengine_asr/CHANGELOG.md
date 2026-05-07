# 更新说明

## v2.2.0 - LivingMemory 适配正式版

### 主要变更

- 将 `2.1.12-pr2` 的 LivingMemory 适配实测结果整理为正式发布版，版本号推进到 `2.2.0`。
- 识别成功后保护 `event.get_message_str()` 的返回值，避免 LivingMemory 或其它插件读取到旧的空文本、旧消息链或 `Record` 附件引用。
- `ProviderRequest` 内容清理继续保留对象形态，只在确认存在音频引用时清理，降低 `'dict' object has no attribute 'model_dump_for_context'` 复发风险。
- 延续 2.1.x 对 `event.extras`、`message_obj.extras`、`run_context`、缓存请求对象与音频引用的清理，减少旧 `.amr/.silk/.wav` 残留进入官方 agent 后段的概率。
- README 从实验版叙事改为 `2.2.0` 正式版叙事，同时保留风险提示：部署差异、第三方插件缓存和未来 AstrBot 内部结构变化仍可能需要单独适配。

### 验证

- `python scripts/run_local_iteration_tests.py`
- `python -m py_compile astrbot_plugin_volcengine_asr/main.py main.py tests/test_helpers.py tests/test_voice_workflow.py scripts/build_release_zip.py`
- 本地回归：95 项通过。
- 测试服 WebChat Record -> 火山 ASR -> LLM -> LivingMemory conversation 实测通过。

## v2.1.12 - 修复 AstrBot 上传安装包目录结构

### 主要变更

- 修复 Release zip 顶层平铺 `CHANGELOG.md`、`main.py`、`metadata.yaml` 时，AstrBot v4.24.2 上传安装器可能报 `[Errno 20] Not a directory: .../CHANGELOG.md` 的问题。
- Release zip 现在固定以 `astrbot_plugin_volcengine_asr/` 作为唯一顶层目录，插件文件放在该目录内，兼容 AstrBot 的 `updator.unzip_file()` 解压逻辑。
- `scripts/build_release_zip.py` 和旧 `_pack.py` 均改为生成单目录包裹结构，并校验 zip 第一项、顶层目录、必需文件和内置 `ffmpeg` 可执行权限。
- README 同步修正上传安装说明：WebUI 上传 Release zip 要用单目录包裹结构；仓库安装仍使用仓库根目录的轻量入口文件。
- 新增回归测试锁定 Release zip 结构，避免后续又打出平铺包。
- 本版本不改变 `v2.1.11` 的 ASR、ffmpeg、ProviderRequest 活对象保护、agent 缓存清理和情绪权重接口逻辑。

## v2.1.11 - 修复 ProviderRequest 活对象保护与 agent request 缓存清理

### 主要变更

- 修复 `agent request` 阶段可能从 `not a valid file: xxx.amr` 进一步变成 `'dict' object has no attribute 'model_dump_for_context'` 的问题。
- `event.extras` / `message_obj.extras` 中的 `request`、`req`、`llm_request` 等 `ProviderRequest` 别名现在会被原地净化，不再被跳过，也不会被替换成普通 `dict`。
- `_looks_like_provider_request()` 现在会保护带 `model_dump_for_context()` 的 AstrBot 请求对象，避免清理逻辑调用该接口后把活对象序列化并写回缓存。
- `run_context` 支持 mapping 形态清理，并扩展 `cached_content`、`cached_messages`、`history`、`input_messages`、`conversation`、`session` 等缓存字段。
- 清理逻辑继续保留普通 URL、普通 `files/path` 和普通 extras；只有确认含音频引用、`Record` 或 `.amr/.silk` 等音频痕迹时才净化。
- 新增回归测试覆盖 ProviderRequest 别名、mapping `run_context`、无 `prompt` 但带 `model_dump_for_context()` 的请求对象、普通 URL 不误删。

## v2.1.10 - 重发 v2.1.9 修复并规避 immutable release 锁

### 主要变更

- 运行时代码沿用 `v2.1.9` 的 agent 前未知缓存与 `run_context` 清理加固。
- 版本推进到 `2.1.10`，用于规避 GitHub 对已创建 `v2.1.9` Release 的 immutable 限制，确保正式 Release 页面可以携带 `astrbot_plugin_volcengine_asr.zip` 附件。
- 安装时请使用 `v2.1.10` Release 附件，不要使用没有发布附件的 `v2.1.9` tag 或 GitHub 自动源码 zip。

## v2.1.9 - 加固 agent 前未知缓存与 run_context 清理

### 主要变更

- 继续修复真实 AstrBot v4.24.2 场景中 `agent_sub_stages.internal:402` 仍可能读取旧 `Record(file="xxx.amr")` 的后段残留问题。
- `on_agent_begin` 现在会把 AstrBot 传入的 `run_context` 一并交给兜底清理，覆盖 `messages`、`stage_data`、`cache`、`payload` 等可见缓存字段。
- `event.extras` / `message_obj.extras` 的清理从固定字段扩展到未知缓存 key，递归移除其中嵌套的 record/audio/file/path 等音频残留。
- 清理时会保留 `ProviderRequest` 对象和事件对象引用，例如 `run_context.event`，避免把后续 agent 阶段仍需使用的活对象替换成普通 dict/list。
- 新增回归测试覆盖未知 extras 缓存、run_context 缓存，以及 `run_context.event` 引用保持不变。
- 本版本仍不做 AstrBot 私有 pipeline monkey patch；官方 `preprocess_stage` warning 仍需从 AstrBot/NapCat/Docker 文件路径侧排查。

## v2.1.8 - 修复 agent 缓存残留并抽出情绪权重接口

### 主要变更

- 修复 `agent_sub_stages.internal:402` 仍可能报 `not a valid file: xxx.amr` 的后段残留问题。
- 事件缓存清理面与 `_find_records()` 的发现面进一步对齐，新增清理 `event.extras` / `message_obj.extras` 中的 `data`、`segments`、`original_message` 等异形缓存字段。
- 新增 `on_agent_begin` 兜底清理，在 AstrBot 构建 agent 前再次净化已注入语音事件和已存在的干净 `ProviderRequest`。
- 新增 `EmotionWeightingInput`、`EmotionWeightingPolicy`、`DefaultEmotionWeightingPolicy`，把情绪 `respect_weight` 计算公式抽成可替换接口。
- `_compute_emotion_respect_weight()` 继续保留为兼容包装器，默认策略完全沿用旧公式；分支开发可替换 `self.emotion_weighting_policy`，避免改动 ASR 主流程。
- 新增回归测试覆盖识别成功后 extras 异形缓存、provider request 音频残留、agent 前兜底清理，以及自定义情绪权重策略注入。
- 本版本仍不能早于官方 `preprocess_stage` 执行；`preprocess_stage` warning 需要继续从 AstrBot/NapCat/Docker 文件路径侧排查。

## v2.1.7 - 加固异形缓存 Record 发现

### 主要变更

- `_find_records()` 现在会额外扫描 `event.extras`、`event._extras`、`event.extra` 以及 `message_obj` 上的同名缓存容器。
- 当适配器或其它插件把 OneBot / NapCat `Record(file="xxx.amr")` 藏在 `request`、`input`、`messages`、`content` 等缓存字段里时，本插件也能发现并接管语音。
- 新增回归测试覆盖 extras / message_obj.extras 中的嵌套 record 结构，降低旧语音段漏进 `agent_sub_stages` 的风险。
- 本版本不做 AstrBot 私有 pipeline monkey patch。AstrBot v4.24.2 的官方 `preprocess_stage` 仍位于插件 handler 之前；若只剩该 warning，请继续按 Docker / NapCat 共享卷和 `get_record` 路径排查。

## v2.1.5 - 增强 Docker / NapCat / 官方预处理排障信息

### 主要变更

- `/volc_asr_status` 增加插件版本、仓库地址和官方 `preprocess_stage` 责任边界提示。
- README 在常见问题中单独补充 AstrBot 官方语音预处理 warning、Docker 共享卷、NapCat `get_record` 和官方 STT 配置的排障说明。
- 说明 `preprocess_stage.stage:81 Voice processing failed` 发生在插件 handler 之前，关闭本插件仍可能出现；插件开启后应重点观察是否还进入 `agent_sub_stages` 的旧 Record 媒体扫描。
- 本版本不改变 ASR、ffmpeg、ProviderRequest 注入或消息链清理主逻辑。

## v2.1.4 - 修复 AstrBot 更新器仓库地址与官方 agent 重入

### 主要变更

- 修复 AstrBot 插件页更新时报 `Plugin astrbot_plugin_volcengine_asr does not specify a repository URL.` 的问题。
- 根目录 `metadata.yaml` 和发布包目录 `astrbot_plugin_volcengine_asr/metadata.yaml` 均补充 `repo: "https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr"`。
- 成功识别和未听清注入路径会直接向 AstrBot `ProcessStage` yield 干净 `ProviderRequest`，避免官方 agent 重新按旧 `Record(file="xxx.amr")` 消息链构造请求。
- 写入 `provider_request` 后同步调用 `event.should_call_llm(True)`，避免默认 LLM 流程在插件提供请求之后再次重入。
- 继续保留 ASR、ffmpeg、情绪判断和消息链清理工作流；本次只收紧与 AstrBot 官方 agent 的交接方式。

## v2.1.3 - 修复 GitHub Release 发布通道

### 主要变更

- 规避 `v2.1.2` 在 GitHub 侧被 immutable release 机制占用后无法发布的问题，改用新的 `v2.1.3` tag 重新发布。
- 重新生成 UTF-8 发布说明，避免草稿 Release 正文出现乱码。
- 重新构建 `output/astrbot_plugin_volcengine_asr.zip`，发布包内 `metadata.yaml` 已更新为 `2.1.3`。
- 插件运行时代码沿用 `2.1.2` 的 QQ AMR 取回、OneBot `get_record` 兜底、干净 `provider_request` 和消息链原地清理逻辑。
- 安装时仍然只应上传 Release 附件 `astrbot_plugin_volcengine_asr.zip`，不要上传仓库根目录旧 zip 或 GitHub 绿色 Code 源码 zip。

## v2.1.2 - 绕过内置 agent 媒体扫描

### 主要变更

- 继续修复 AstrBot v4.24.2 内置 agent 在 `build_main_agent()` 阶段扫描旧语音段并报 `not a valid file: xxx.amr` 的问题。
- 查明报错并不发生在本插件 ffmpeg 转码阶段，而是 AstrBot 内置 agent 构造 `ProviderRequest` 前遍历 `event.message_obj.message` 和 `Reply.chain`，对残留 `Record` 调用 `convert_to_file_path()`。
- 成功识别和未听清注入路径会提前写入干净 `provider_request`，让内置 agent 直接使用纯文本请求，绕过媒体附件扫描分支。
- `_find_records()` 兼容非 `list` 的 `MessageChain` 对象，包括只暴露 `.chain` 且本体不可迭代的真实 AstrBot 消息链，避免漏掉 `Record`。
- 消息链替换会原地改写 `MessageChain.chain`，防止旧对象引用继续把 `.amr` 语音段带入默认 agent。
- 裸 OneBot / NapCat `Record(file="xxx.amr")` 在组件 `convert_to_base64()` 失败后会尝试 `get_record(file, out_format)`，取回真实 AMR 内容后再进入插件 ffmpeg 转码链路。
- README 同步补充 2.1.2 排障说明，提示升级后可通过干净 `provider_request` 绕开媒体扫描，并支持非 list `MessageChain`。

## v2.1.1 - 清理情绪判断与直接回复路径的语音残留

### 主要变更

- 情绪判断前先清理当前语音 `Record`，避免情绪判断 LLM 路径把旧 `Record(file="xxx.amr")` 带入后续 agent。
- 识别失败、配置错误、未听清直接提示、`reply_transcription=true` 直接回复转写等路径，先 `stop_event()` 再发送回复，避免默认 LLM / agent 继续处理原语音。
- 修复直接回复或失败路径仍可能触发 `not a valid file: xxx.amr` 的问题。
- `emotion_model_id` 配置增加 `_special: select_provider`，AstrBot WebUI 可点击选择已配置模型；留空时使用当前会话默认模型。
- README 同步补充 v2.1.1 行为说明、模型选择说明和 `not a valid file: xxx.amr` 排障提示。

## v2.1.0 - 重新构建语音工作流

### 主要变更

- 重新构建 QQ 语音从 AstrBot 事件进入 LLM 的完整工作流，主链路拆为 `VoiceInput -> AudioPayloadResult -> ASR -> VoiceInjectionPlan -> ProviderRequest`。
- 进入消息事件时先收集稳定 `VoiceInput` 快照，后续不再依赖可能被 AstrBot、适配器或其它插件缓存改写的原始 `event`。
- 加强 Record 来源发现，兼容 AstrBot 消息链、`message_obj`、`raw_message`、裸 OneBot `record` dict，以及 NapCat 常见 `file` / `path` / `url` / `base64` 字段。
- 优化音频读取与提交路径，默认继续推荐 `submit_mode=base64`，先在 AstrBot 侧读取、下载或转码语音，再提交给火山引擎。
- `submit_mode=url` 只直传明确支持的 `.wav` / `.mp3` / `.ogg` / `.opus` HTTP(S) URL；`.amr` / `.silk` 等 QQ 语音会回落到下载、转码和 Base64 上传。
- 成功识别或未听清注入时，统一通过 `VoiceInjectionPlan` 将事件消息链改写为干净 `Plain` 文本，并保留结构化语音处理诊断。
- `on_llm_request` 阶段继续清理 `ProviderRequest.audio_urls`、上下文、临时内容和缓存字段中的音频残留；当找不到原始转写文本时，会前置 `llm_text` 并保留原 prompt，避免丢失 LivingMemory 或 provider 已组装的上下文。
- 保持 LivingMemory 友好的两阶段语义：消息阶段只写入用户语音的纯转写文本，LLM 请求阶段再应用 `voice_prompt_template` 和可选情绪辅助信息。
- 增加工作流回归测试，覆盖成功注入、未听清注入、错误阻断、裸 `.amr` 转换失败、URL AMR 不直传和 LLM 请求兜底。
- README 新增 AstrBot / OneBot v11 / NapCat 兼容依据，补充安装、错包、乱码和 `not a valid file: xxx.amr` 排障说明。

### 安装与升级提醒

- 推荐从 GitHub Releases 下载 `astrbot_plugin_volcengine_asr.zip` 后，在 AstrBot WebUI 插件页上传安装。
- 不要使用 GitHub 绿色 Code 按钮下载的源码 zip 代替 Release zip。
- 发布包 zip 根目录应直接包含 `metadata.yaml`、`main.py`、`_conf_schema.json`、`requirements.txt`，不应再套一层同名目录。
- 只上传 `output/astrbot_plugin_volcengine_asr.zip`；不要上传仓库根目录旧 zip、`_release_body.json` 或 `_release_draft.json`。
- README、CHANGELOG 和发布说明均按 UTF-8 保存；Windows 终端乱码通常是控制台编码问题，不代表文件损坏。

## v2.0.4 - 修复 ffmpeg 启动探测与打包校验

### 主要变更

- 修复内置 `ffmpeg` 文件存在但无法正常启动时，插件仍优先选中它并导致 AMR / SILK / M4A 转码失败的问题。
- ffmpeg 查找流程改为逐个执行 `ffmpeg -version` 启动探测；内置 ffmpeg 不可用时，会自动尝试 `imageio-ffmpeg` 和系统 PATH 中的 `ffmpeg`。
- `ffmpeg_path` 配置为绝对路径时，会只探测该路径；不可启动时保留诊断，不会让插件加载阶段直接崩溃。
- 转码启动阶段会捕获 `PermissionError`、`Exec format error`、`noexec` 等底层 `OSError`，并转换成用户可读错误，提示安装系统 ffmpeg 或配置 `ffmpeg_path`。
- `/volc_asr_status` 增加 `ffmpeg状态`，Web UI 预留状态接口增加 `ffmpeg_status` 与 `ffmpeg_error`。
- Release zip 构建脚本强制校验 `bin/linux-x86_64/ffmpeg` 源文件存在，并回读 zip 确认 entry 权限位为 `0o100755`。
- 增加回归测试，覆盖 `ffmpeg -version` 输出解析、启动探测成功/失败、转码启动异常转为 `UserVisibleError`、探测失败时不继续 spawn ffmpeg。

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

- Release zip 顶层固定为一个插件目录，插件文件放在该目录内。
- Release zip 包含 Linux x86_64/amd64 内置 `ffmpeg`，适合 Docker 或 VPS 环境。
- 不要使用 GitHub 绿色 Code 按钮下载的源码 zip 代替 Release zip。

### 验证项目

- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile main.py astrbot_plugin_volcengine_asr/main.py`
- 配置 JSON 校验通过。
- README 配置项覆盖检查通过。
- helper 测试通过。
- Release zip 顶层目录结构、版本和内置 `ffmpeg` 校验通过。

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
