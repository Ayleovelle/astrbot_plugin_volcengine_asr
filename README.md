<!-- markdownlint-disable MD024 MD033 MD041 -->

<p align="center">
  <img src="./assets/VoiceMountain.svg" alt="火山引擎语音转文字 AstrBot 插件" width="920">
</p>

<p align="center">

</p>

<p align="center">
  <img src="./assets/FuckUCodeScore.svg" alt="Fuck-U-Code 代码质量评分" width="250">
</p>

<h1 align="center">AstrBot 火山引擎语音转文字插件</h1>

<p align="center">
  <strong>让 QQ 语音像文字消息一样进入 AstrBot、LLM、TTS 和长期记忆流程。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.1.5-brightgreen.svg" alt="Version 2.1.5">
  <img src="https://img.shields.io/badge/AstrBot-%3E=4.16,%3C5-orange.svg" alt="AstrBot >=4.16,<5">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License MIT">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/%E7%81%AB%E5%B1%B1%E5%BC%95%E6%93%8E-%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3-FF6A00.svg" alt="火山引擎豆包语音">
  <img src="https://img.shields.io/badge/OneBot-v11-12B7F3.svg" alt="OneBot v11">
  <img src="https://img.shields.io/badge/QQ-NapCat-12B7F3.svg" alt="NapCat">
  <img src="https://img.shields.io/badge/ffmpeg-%E5%86%85%E7%BD%AE-success.svg" alt="内置 ffmpeg">
</p>

---

## 快速导航

| 左列 | 右列 |
| :--- | :--- |
| 1. [插件定位](#插件定位) | 9. [情绪判断模块](#情绪判断模块) |
| 2. [适合谁使用](#适合谁使用) | 10. [完整配置说明](#完整配置说明) |
| 3. [核心特性](#核心特性) | 11. [默认提示词与模板写法](#默认提示词与模板写法) |
| 4. [重建后的语音工作流](#重建后的语音工作流) | 12. [LivingMemory 兼容机制](#livingmemory-兼容机制) |
| 5. [安装方式](#安装方式) | 13. [命令与状态检查](#命令与状态检查) |
| 6. [火山引擎准备](#火山引擎准备) | 14. [常见问题与排障](#常见问题与排障) |
| 7. [推荐配置](#推荐配置) | 15. [目录结构与发布包说明](#目录结构与发布包说明) |
| 8. [情绪判断快速配置](#情绪判断快速配置) | 16. [第三方组件与许可证](#第三方组件与许可证) |

---

## 插件定位

`astrbot_plugin_volcengine_asr` 是一个面向 AstrBot 的 QQ 语音识别插件。它会监听消息链中的 `Record` 语音段，读取或下载音频，必要时调用 `ffmpeg` 转码，然后通过火山引擎豆包语音「大模型录音文件极速版识别 API」把语音转成文本。

与“识别后直接回复一条语音转文字结果”的简单插件不同，本插件的默认目标是：

> 把语音转写结果注入为用户输入，让 AstrBot 后续的 LLM、TTS、长期记忆、上下文插件继续正常工作。

也就是说，用户发一条 QQ 语音后，Bot 可以像收到一条文字消息一样理解它、记住它，并自然回复。对于希望实现“用户语音输入，Bot 理解后尽量语音回复”的使用场景，这个插件更像是语音入口层，而不只是一个转写工具。

> [!IMPORTANT]
> 推荐优先使用 Releases 中的 `astrbot_plugin_volcengine_asr.zip` 安装。
>
> GitHub 页面绿色 Code 按钮下载的源码 zip 不等于本插件发布包：源码 zip 通常不包含 Release 包内置的 `bin/linux-x86_64/ffmpeg`，也可能因为目录层级不同导致 AstrBot 找不到 `metadata.yaml`。

## 适合谁使用

本插件比较适合以下场景：

- 你使用 AstrBot 接入 QQ / OneBot v11 / NapCat。
- 你希望用户可以直接发 QQ 语音，而不是必须打字。
- 你希望语音内容进入 LLM 对话，而不是 Bot 只机械回复“语音转文字：xxx”。
- 你正在使用长期记忆插件，例如 `astrbot_plugin_livingmemory`，并且不希望记忆里混入语音提示词模板。
- 你部署在 Docker、VPS 或 Linux x86_64 / amd64 环境，希望开箱就能处理 AMR、SILK、M4A 等常见 QQ 语音格式。
- 你希望在调试时可以切换到“直接回复转写文本”的旧行为。

如果你只是想偶尔手动转写一条语音，也可以开启 `reply_transcription=true`，让插件直接在聊天中回复识别结果。但本插件默认更推荐“注入为用户输入”的工作方式。

## 核心特性

| 能力 | 说明 |
| :--- | :--- |
| 自动识别 QQ 语音 | 支持私聊和群聊，识别 OneBot v11 / NapCat 返回的 `Record` 语音消息。 |
| 火山引擎 ASR | 使用豆包语音大模型录音文件极速版识别接口，默认资源 ID 为 `volc.bigasr.auc_turbo`。 |
| Base64 上传 | 默认由 AstrBot 所在机器读取或下载音频，再提交给火山接口，适合大多数 QQ 语音 URL 无法公网访问的情况。 |
| 自动转码 | 检测到 AMR、SILK、M4A、AAC、FLAC、WEBM 等格式时，可调用 `ffmpeg` 转为 WAV / MP3 / OGG。 |
| Release 包内置 ffmpeg | Release zip 内置 Linux x86_64 / amd64 版 `ffmpeg`，适合 Docker / VPS。 |
| LLM 友好 | 默认把转写文本注入为用户输入，让模型自然理解语音内容。 |
| 情绪判断 LLM | 2.0.0 新增，可选地在主 LLM 回复前分析用户语音情绪，并以公式化权重影响主 LLM 语气。 |
| LivingMemory 友好 | 消息阶段写入干净转写文本，LLM 请求阶段才套语音提示词，避免长期记忆被模板污染。 |
| 可控触发范围 | 可分别控制私聊、群聊、仅被 @ 或唤醒时识别、是否忽略机器人自身消息。 |
| 友好降级 | 静音、杂音、空结果时可让 LLM 自然地请用户重说。 |
| 可排障 | 支持显示火山接口 `logid`，便于向火山引擎或运维侧排查问题。 |

## 2.1.0 语音工作流重建说明

`2.1.0` 不是继续在旧链路上补字段，而是把语音处理拆成五段明确边界：

```text
VoiceInput -> AudioPayloadResult -> ASR -> VoiceInjectionPlan -> ProviderRequest
```

这样做的原因很直接：AstrBot 默认 agent 会在构造 LLM 请求时遍历 `event.message_obj.message`，如果里面还残留 `Record(file="xxx.amr")` 这种裸文件名，就可能触发 `Record.convert_to_file_path()` 并报 `not a valid file: xxx.amr`。所以新工作流先把原始语音输入收集成稳定快照，后续不再依赖会被其它插件或框架缓存改写的 `event` 原始结构。

| 阶段 | 新职责 |
| :--- | :--- |
| `VoiceInput` | 只在消息事件开始时收集一次语音段，兼容 AstrBot 消息链、`message_obj`、`raw_message`、裸 OneBot `record` dict，以及 NapCat 常见 `file` / `path` / `url` / `base64` 字段。 |
| `AudioPayloadResult` | 把一条语音变成火山 ASR 可消费的 `url` 或 `data`，同时记录来源、真实格式、输入大小、是否转码、输出格式和输出大小。 |
| `ASR` | 只负责调用火山引擎并返回 `AsrResult`，空文本、静音、下载失败、转码失败都会写入结构化诊断。 |
| `VoiceInjectionPlan` | 明确区分 `memory_text`、`llm_text`、`raw_text` 和 `unclear`，成功或未听清时统一把事件消息链改成纯 `Plain` 文本。 |
| `ProviderRequest` | 在 `on_llm_request` 阶段清理本轮请求里的音频残留，并强制让主 LLM 收到 `llm_text`。即使 `req.prompt` 被 AstrBot 或其它插件包装到找不到纯转写文本，也不再静默跳过。 |

这版的核心策略是：

- 成功注入路径不调用 `event.stop_event()`，因为 `stop_event()` 会阻止后续默认 LLM / agent 流程。
- 识别失败、直接回复转写、配置错误这类不需要默认 LLM 继续处理原语音的路径，仍按配置或错误状态阻断事件，避免旧 `Record` 继续流转。
- 默认继续推荐 `submit_mode=base64`：先由 AstrBot 所在机器读取、下载或转码，再提交给火山引擎，避免临时 URL、内网 URL、NapCat raw silk URL 被火山侧直接访问失败。
- `submit_mode=url` 只会直传明确属于 `.wav` / `.mp3` / `.ogg` / `.opus` 的 HTTP(S) URL；`.amr` / `.silk` 这类 QQ 语音会回落到下载、转码和 Base64 上传。

## 2.1.1 语音 Record 清理修复

`2.1.1` 继续收紧语音残留清理边界，重点修复情绪判断和直接回复路径可能让旧 `Record(file="xxx.amr")` 继续进入 agent 的问题。

- 情绪判断前会先清理当前语音 `Record`，再把转写文本和可用上下文交给情绪判断 LLM。
- 识别失败、配置错误、未听清直接提示、`reply_transcription=true` 直接回复转写等不需要默认 LLM 继续处理原语音的路径，会先 `stop_event()`，再发送回复。
- 这样可以避免后续 agent 或媒体转换逻辑继续读取裸 `.amr` 文件名，减少 `not a valid file: xxx.amr`。

## 2.1.4 AstrBot 更新器与官方 agent 兼容修复

`2.1.4` 修复两个 AstrBot 侧交接问题。

第一，修复插件页更新时报 `Plugin astrbot_plugin_volcengine_asr does not specify a repository URL.` 的问题。原因是 `metadata.yaml` 中的 `repo` 字段此前为空，AstrBot 更新器无法知道应该从哪个 GitHub 仓库检查新版。

第二，修复官方 agent 仍按旧 `Record(file="xxx.amr")` 消息链重新构造请求的问题。插件成功识别语音后，会直接向 AstrBot `ProcessStage` yield 一个干净 `ProviderRequest`，并调用 `event.should_call_llm(True)` 阻止默认 LLM 流程再次重入，避免 `agent_sub_stages` 再触发 `Record.convert_to_file_path()`。

- 根目录和发布包目录的 `metadata.yaml` 都已写入 `https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr`。
- 已安装旧版的用户建议先手动上传 `2.1.4` Release zip；安装后，后续 AstrBot 插件页更新才能读取到仓库地址。
- `preprocess_stage` 中官方语音预处理的 warning 发生在插件 handler 之前；若关闭插件仍看到这条 warning，需要关闭 AstrBot 官方 STT/语音预处理或让 NapCat 提供真实可读文件。但插件开启后不应再继续进入 `agent_sub_stages` 的旧 Record 媒体扫描。

## 2.1.3 发布通道修复

`2.1.3` 不改变语音识别主工作流，重点修复 GitHub Release 发布通道：`v2.1.2` 在 GitHub 侧已被 immutable release 机制占用，继续发布会出现 `tag name was used by an immutable release`。本版本使用新的 `v2.1.3` tag 重新构建发布包，并重新生成 UTF-8 发布说明，避免草稿页面正文乱码和不可变 tag 冲突。

- 插件代码沿用 `2.1.2` 的 QQ AMR 取回、`get_record` 兜底、干净 `provider_request` 与消息链原地清理逻辑。
- Release 附件仍只上传 `output/astrbot_plugin_volcengine_asr.zip`，不要上传仓库根目录旧 zip。
- 如果你看到旧 `v2.1.2` 草稿，不要继续发布它；请使用 `v2.1.3` Release。

## 2.1.2 干净 ProviderRequest 修复

`2.1.2` 继续修复 AstrBot 内置 agent 的前置媒体扫描问题：`build_main_agent` 在构造 `ProviderRequest` 前会扫描 `event.message_obj.message` / `Reply.chain`，如果里面还有 `Record(file="xxx.amr")`，就可能触发 `Record.convert_to_file_path()` 并报 `not a valid file: xxx.amr`。

- 新增干净 `provider_request`，在默认 agent 构造请求前绕开本轮语音媒体扫描，让主 LLM 只接收转写后的文本。
- 清理逻辑兼容非 list 形态的 `MessageChain`，避免消息链不是普通 list 时留下旧 `Record`。
- 当 OneBot / NapCat 只给出裸 `file="xxx.amr"` 且组件自身 `convert_to_base64()` 失败时，插件会尝试调用 `get_record(file, out_format)` 取回真实语音内容，再交给 `ffmpeg` 转码。

## 重建后的语音工作流

默认推荐流程如下：

```text
QQ 语音 Record
  -> 收集 VoiceInput 快照
  -> 读取 base64 / path / file / url
  -> 下载或读取音频
  -> 检测格式与大小
  -> 必要时调用 ffmpeg 转码
  -> Base64 提交到火山引擎 ASR
  -> 得到纯转写文本
  -> 可选：情绪判断 LLM 分析转写文本和上下文
  -> 生成 VoiceInjectionPlan
  -> 消息事件阶段只注入 Plain 纯文本 memory_text
  -> LivingMemory 读取和存储干净文本
  -> LLM 请求阶段清理音频残留并写入 llm_text
  -> 主 LLM 按参考权重调整语气并生成回复
```

对应流程图：

```mermaid
flowchart LR
    A[QQ 语音 Record] --> B[VoiceInput 快照]
    B --> C[读取 base64 / path / file / url]
    C --> D[下载或读取音频]
    D --> E{格式是否支持}
    E -->|WAV / MP3 / OGG / OPUS| F[Base64 上传]
    E -->|AMR / SILK / M4A 等| G[ffmpeg 转码]
    G --> F
    F --> H[火山引擎 ASR]
    H --> I[VoiceInjectionPlan]
    I --> J[事件消息链改写为 Plain memory_text]
    J --> K[LivingMemory 检索和存储纯文本]
    K --> L[on_llm_request 清理音频残留]
    L --> M[主 LLM 收到 llm_text]
    M --> N[生成回复]
```

这个顺序很重要：记忆插件读到的是用户实际说的话，而不是“请尽量使用语音回复”这类提示词包装。

## AstrBot / OneBot / NapCat 兼容依据

本次重建工作流同时参考了 AstrBot、OneBot v11 和 NapCat 的实际语义：

- AstrBot 的消息事件文档说明，`event.stop_event()` 会停止事件传播，后续步骤不会继续执行；所以本插件在“识别成功并希望默认 LLM 继续回复”的路径上不能使用它。详见 [AstrBot 处理消息事件文档](https://docs.astrbot.app/dev/star/guides/listen-message-event.html)。
- AstrBot v4.24.2 默认 agent 构造 `ProviderRequest` 时会读取 `event.message_str`，并遍历 `event.message_obj.message` 里的媒体段。若仍有 `Record(file="xxx.amr")` 裸文件名，就可能在 `Record.convert_to_file_path()` 阶段失败。因此插件必须在事件阶段把消息链改写成 `Plain(memory_text)`，并在 LLM 请求阶段兜底清理 `ProviderRequest.audio_urls`。
- OneBot v11 的语音消息段类型是 `record`，标准接收字段以 `data.file` 为核心，接收侧也可能带 `url`。详见 [OneBot v11 消息段类型：语音](https://283375.github.io/onebot_v11_vitepress/message/segment.html)。
- OneBot v11 的 `get_record` 标准动作以收到的 `file` 为参数，并通过 `out_format` 请求转换格式。详见 [OneBot v11 公开 API：get_record](https://raw.githubusercontent.com/botuniverse/onebot-11/master/api/public.md)。
- NapCat 的 `record` 消息段会出现 `file`、`path`、`url`、`file_id`、`file_size`、`file_unique` 等实现扩展字段，但 NapCat 文档也提示语音 URL 可能是 raw silk 资源，不能直接当通用音频交给 ASR。详见 [NapCat 消息格式兼容情况](https://www.napcat.wiki/develop/msg) 和 [NapCat 文件处理框架指南](https://napneko.github.io/develop/file)。

## 安装方式

### 方式一：上传 Release 压缩包

这是最推荐的安装方式，尤其适合 Docker、VPS、云服务器和不方便手动安装 `ffmpeg` 的环境。

1. 打开 [GitHub Releases](https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr/releases/latest)。
2. 下载 `astrbot_plugin_volcengine_asr.zip`。
3. 进入 AstrBot WebUI 的插件页面。
4. 选择“从文件安装”。
5. 上传这个 zip。
6. 重载插件或重启 AstrBot。
7. 打开插件配置页，填写火山引擎鉴权信息。

Release zip 根目录应直接包含：

```text
metadata.yaml
main.py
_conf_schema.json
requirements.txt
README.md
assets/VoiceMountain.svg
assets/FuckUCodeScore.svg
bin/linux-x86_64/ffmpeg
```

如果 zip 外面又套了一层同名目录，例如：

```text
astrbot_plugin_volcengine_asr/
└── metadata.yaml
```

AstrBot 可能会报找不到 `metadata.yaml`。这种情况通常说明你下载的是源码 zip，或者自己打包时目录层级错了。

### 方式二：从 GitHub 仓库安装

在 AstrBot WebUI 里使用仓库地址安装：

```text
https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr
```

如果 WebUI 输入框会自动补全 `.git`，也可以使用：

```text
https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr.git
```

不要省略协议头。也就是说，不要填写下面这种地址：

```text
//github.com/Ayleovelle/astrbot_plugin_volcengine_asr.git
```

少了 `https:` 会让 AstrBot 把它当成不完整链接处理，可能导致下载、依赖安装或插件加载路径异常。

仓库根目录提供了 `metadata.yaml`、`main.py`、`_conf_schema.json` 和 `requirements.txt`，可以被 AstrBot 直接识别。

需要注意：仓库安装不等同于 Release zip 安装。仓库根目录本身不会带 Release zip 中的内置 `bin/linux-x86_64/ffmpeg`，所以会依赖 `imageio-ffmpeg` 或系统 PATH 中的 `ffmpeg` 作为兜底。如果你的环境禁止安装 Python 依赖，或者 `imageio-ffmpeg` 无法下载二进制，请改用 Release zip 或手动配置系统 `ffmpeg`。

### 方式三：手动放入插件目录

将插件目录放入 AstrBot 的 `data/plugins/` 下，确保目录中至少包含：

```text
astrbot_plugin_volcengine_asr/
├── metadata.yaml
├── main.py
├── _conf_schema.json
├── requirements.txt
└── bin/linux-x86_64/ffmpeg
```

如果你不是 Linux x86_64 / amd64 环境，可以关闭 `prefer_bundled_ffmpeg`，并把 `ffmpeg_path` 改成系统中的 `ffmpeg` 绝对路径。

## 火山引擎准备

使用前需要在火山引擎控制台准备豆包语音识别能力：

1. 开通豆包语音「大模型录音文件极速版识别」。
2. 确认资源 ID 为 `volc.bigasr.auc_turbo`。
3. 新版控制台优先获取并填写 `api_key`。
4. 旧版控制台可以继续使用 `app_key + access_key`。
5. 确认账号配额、权限和计费状态正常。

鉴权优先级：

| 情况 | 插件行为 |
| :--- | :--- |
| 填写了 `api_key` | 优先使用 `X-Api-Key` 鉴权。 |
| 未填写 `api_key`，填写了 `app_key + access_key` | 使用旧版鉴权字段。 |
| 都未填写 | 识别不会正常工作；若 `notify_config_error=true`，会在聊天中提示配置错误。 |

默认接口地址：

```text
https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash
```

一般不需要修改 `endpoint`。只有在火山引擎官方文档明确要求更换接口，或你有代理网关时，才建议改它。

## 推荐配置

### OneBot v11 + NapCat + Linux Docker 推荐值

大多数用户只需要改这些：

| 配置项 | 推荐值 | 原因 |
| :--- | :--- | :--- |
| `api_key` | 你的火山引擎 API Key | 新版控制台优先使用这一项。 |
| `submit_mode` | `base64` | QQ 语音 URL 经常是内网、临时或需要本机访问，Base64 更稳定。 |
| `enable_transcode` | `true` | 自动处理 AMR、SILK、M4A 等格式。 |
| `prefer_bundled_ffmpeg` | `true` | Release 包内置 Linux x86_64 `ffmpeg`。 |
| `inject_as_user_input` | `true` | 让语音像用户文字输入一样进入 LLM。 |
| `reply_transcription` | `false` | 不直接回复“语音转文字：xxx”，保持自然对话。 |
| `inject_on_unclear_voice` | `true` | 没听清时让模型自然请用户重说。 |

### 想直接看转写结果的调试配置

如果你正在排查 ASR 是否成功，可以临时改成：

```text
reply_transcription = true
show_logid = true
```

这样 Bot 会直接回复转写结果，并在需要时附带火山引擎 `logid`。排查结束后，建议改回：

```text
reply_transcription = false
show_logid = false
```

### 群聊较吵时的配置建议

如果群里语音很多，但你只希望 Bot 在被叫到时识别，可以开启：

```text
only_when_at_or_wake = true
```

这样可以减少无关语音触发，也能降低调用火山接口的成本。

## 情绪判断快速配置

2.0.0 新增的情绪判断模块默认关闭。如果你希望主 LLM 在回复语音消息时更敏感地理解用户当前状态，可以按下面方式开启：

```text
enable_emotion_analysis = true
emotion_model_id = ""
emotion_context_turns = 4
emotion_max_respect_weight_percent = 60
emotion_fail_open = true
```

说明：

- `emotion_model_id` 留空时，插件会尝试使用当前会话的主 LLM 作为情绪判断 LLM。
- `emotion_model_id` 在 AstrBot WebUI 中支持点击选择已配置模型；留空时使用当前会话默认模型。
- `emotion_max_respect_weight_percent` 建议保持在 `30-70`。它不是情绪置信度，而是“主 LLM 最多应该在多大程度上参考情绪判断”的上限。
- `emotion_fail_open=true` 时，即使情绪判断模型超时、报错或输出 JSON 不合法，语音转写仍会按原流程进入主 LLM。

> [!WARNING]
> 情绪判断会额外请求一次 LLM，因此会增加 token 消耗、响应延迟和上下文暴露范围。它只用于调整回复语气，不是心理诊断，也不应该覆盖用户明确表达的请求。

## 情绪判断模块

情绪判断模块是 2.0.0 的核心更新。它的目标不是“判断用户真实心理状态”，而是在用户发语音时，给主 LLM 一个结构化、带权重、可忽略的语气参考。

### 模块解决什么问题

语音消息比文字多了一层表达语境：用户可能是在抱怨、撒娇、焦虑、兴奋、困惑，也可能只是普通陈述。ASR 只能给出文字，不会直接告诉主 LLM“这个语音听起来该被温柔对待还是正常回答”。

本模块在 ASR 得到纯转写文本后，额外调用一次情绪判断 LLM，让它输出结构化 JSON。插件随后用本地公式计算 `respect_weight`，再把结果追加到主 LLM 的提示词里。主 LLM 可以根据该权重调整语气、安抚强度和共情程度，但不能把情绪判断当成事实。

### 完整工作流

```text
1. 用户发送 QQ 语音。
2. 插件通过火山引擎 ASR 得到纯转写文本。
3. 如果 enable_emotion_analysis=false：
   - 直接走原来的 LivingMemory 友好注入流程。
4. 如果 enable_emotion_analysis=true：
   - 插件构造情绪判断 prompt。
   - 情绪判断 LLM 读取当前语音转写和可用上下文。
   - 情绪判断 LLM 只允许输出 JSON。
   - 插件解析 JSON，清洗情绪标签和权重。
   - 插件用 Shannon entropy、LLM 置信度、文本证据强度计算 respect_weight。
   - 插件把情绪结果作为辅助块追加到主 LLM prompt。
5. 消息事件阶段仍然只把纯转写文本写入 event.message_str。
6. LivingMemory 仍然只读取和存储干净文本。
7. 主 LLM 最终看到：语音提示词 + 情绪辅助信息 + 原本上下文。
8. 主 LLM 按参考权重调整语气并回复。
```

关键点：情绪判断结果不会写入 `event.message_str`，也不会写入 `message_obj.message_str`。LivingMemory 看到的仍然是用户原话的纯转写文本。

### 情绪判断 LLM 输出格式

情绪判断 LLM 必须输出 JSON，例如：

```json
{
  "label": "anxious",
  "emotion_weights": {
    "anxious": 0.62,
    "sad": 0.18,
    "neutral": 0.12
  },
  "confidence": 0.71,
  "valence": -0.45,
  "arousal": 0.68,
  "voice_text_support": 0.75,
  "context_support": 0.40,
  "reason": "用户表达了担心和不确定，但没有明显愤怒。"
}
```

字段解释：

| 字段 | 含义 |
| :--- | :--- |
| `label` | 主情绪标签。当前支持 `neutral`、`happy`、`sad`、`angry`、`anxious`、`frustrated`、`excited`、`confused`、`tired`。 |
| `emotion_weights` | 情绪分布。插件会裁剪到 `[0,1]`，总和超过 1 时会重新归一化。 |
| `confidence` | 情绪判断 LLM 对自己判断的置信度，只是输入信号之一，不会被完全信任。 |
| `valence` | 效价，范围 `[-1,1]`。负值偏不愉快，正值偏愉快。 |
| `arousal` | 唤醒度，范围 `[0,1]`。越高表示情绪越激活、越强烈。 |
| `voice_text_support` | 当前语音转写文本本身对该判断的支持度。 |
| `context_support` | 上下文对该判断的支持度。 |
| `reason` | 一句话短解释，不需要链式思考。 |

如果模型输出不是合法 JSON，或字段无法解析，插件会跳过情绪增强，并继续正常语音转写流程。

### 理论依据

本模块采用“维度情绪 + 分类情绪 + 不确定性校准 + 语境评价”的混合方案。需要先说明边界：插件里的 `respect_weight` 是工程化融合公式，不是某篇心理学论文或机器学习论文的原样复现；它把下列可检索文献中的思想压缩成一个可控、可解释、默认保守的提示词权重。

1. **Russell 环状情绪模型**
   Russell 的 Circumplex Model of Affect 将情绪放在二维空间中理解：`valence` 表示愉快/不愉快，`arousal` 表示激活/平静。这样比只给一个“开心/难过”标签更细，因为“愤怒”和“焦虑”都可能是负效价高唤醒，而“疲惫”更接近负效价低唤醒。该思路来自 Russell 对情绪词空间的二维建模，后续也被 Posner、Russell 与 Peterson 用于整合情感神经科学、认知发展和精神病理学研究。

2. **分类情绪标签**
   主 LLM 实际调整回复时仍需要可读标签，所以插件保留 `anxious`、`sad`、`happy` 等离散情绪。标签负责“怎么说”，效价/唤醒度负责“强度和方向”。这里借用了基础情绪研究中“离散标签有助于表达和识别”的工程价值，但不等同于完整采纳某一种基础情绪理论。

3. **Shannon entropy 不确定性**
   如果情绪分布很集中，例如 `anxious=0.90, neutral=0.10`，说明分类结果更确定；如果分布很平，例如 `anxious=0.34, sad=0.33, neutral=0.33`，说明模型其实不确定。插件用 Shannon 在信息论中提出的 entropy 形式，把情绪分布的不确定性转成 `certainty`。

4. **置信度不直接等于参考权重**
   LLM 自报的 `confidence` 可能过高或不稳定，所以插件不会直接把它当成主 LLM 的服从程度，而是把它和分类确定性、文本证据强度一起计算。这个设计参考了现代神经网络校准研究中的基本结论：模型给出的概率或置信度不必然等于真实正确率，实际系统中需要额外校准或约束。

5. **语境证据加权**
   情绪不能只看一个词，也不能完全靠上下文脑补。认知评价理论强调情绪与个体对事件、责任、确定性、控制感等语境因素的评价有关。因此插件默认更重视当前语音文本，较轻参考上下文：`voice_text_support` 权重 0.7，`context_support` 权重 0.3。

### 计算过程

插件先把情绪权重清洗成概率分布 `p`，再计算分类确定性：

```text
H(p) = -Σ p_i log(p_i)
certainty = 1 - H(p) / log(N)
```

解释：

- `H(p)` 是 Shannon entropy。
- `N` 是非零情绪标签数量。
- `certainty` 越接近 1，说明情绪分布越集中。
- `certainty` 越接近 0，说明模型在多个情绪之间摇摆。

然后计算证据强度：

```text
length_factor = min(1, log(1 + transcript_chars) / log(81))
evidence = length_factor * (0.7 * voice_text_support + 0.3 * context_support)
```

解释：

- 很短的语音文本信息量不足，例如“嗯”“啊？”“好吧”，即使模型给出高置信，也不应该让主 LLM 过度反应。
- `length_factor` 会压低短文本的证据强度。
- 当前语音文本比上下文更重要，所以权重是 0.7 / 0.3。

最后计算主 LLM 参考权重：

```text
respect_weight = clamp(
  max_respect_weight * (0.50 * confidence + 0.30 * certainty + 0.20 * evidence),
  0,
  max_respect_weight
)
```

默认：

```text
max_respect_weight = 0.60
```

额外保护：

- 如果转写文本少于 12 个字符，`respect_weight` 最高压到 `0.25`。
- 如果语音未听清，不进行情绪判断。
- 如果 JSON 解析失败，不进行情绪增强。
- 如果情绪判断 LLM 调用失败，默认 fail-open，继续普通 ASR 流程。

### 可检索参考文献

下面这些文献都可以在 Google Scholar 中按标题检索到：

| 作用 | 文献 |
| :--- | :--- |
| `valence/arousal` 二维情绪空间 | Russell, J. A. (1980). [A circumplex model of affect](https://doi.org/10.1037/h0077714). *Journal of Personality and Social Psychology*, 39(6), 1161-1178. |
| 环状情绪模型的神经科学与发展心理学综述 | Posner, J., Russell, J. A., & Peterson, B. S. (2005). [The circumplex model of affect: An integrative approach to affective neuroscience, cognitive development, and psychopathology](https://doi.org/10.1017/S0954579405050340). *Development and Psychopathology*, 17(3), 715-734. |
| 离散情绪标签的基础情绪理论来源 | Ekman, P. (1992). [An argument for basic emotions](https://doi.org/10.1080/02699939208411068). *Cognition and Emotion*, 6(3-4), 169-200. |
| entropy / 不确定性度量 | Shannon, C. E. (1948). [A mathematical theory of communication](https://doi.org/10.1002/j.1538-7305.1948.tb01338.x). *The Bell System Technical Journal*, 27(3), 379-423. |
| 语境评价与情绪差异 | Smith, C. A., & Ellsworth, P. C. (1985). [Patterns of cognitive appraisal in emotion](https://doi.org/10.1037/0022-3514.48.4.813). *Journal of Personality and Social Psychology*, 48(4), 813-838. |
| 评价理论的多层顺序检查模型 | Scherer, K. R. (2001). [Appraisal considered as a process of multilevel sequential checking](https://doi.org/10.1093/oso/9780195130072.003.0005). In *Appraisal Processes in Emotion: Theory, Methods, Research* (pp. 92-120). Oxford University Press. |
| 现代神经网络置信度校准 | Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). [On calibration of modern neural networks](https://arxiv.org/abs/1706.04599). *Proceedings of ICML 2017*. |

### 主 LLM 最终看到什么

主 LLM 不会收到情绪判断 LLM 的原始长输出，而是收到插件整理后的辅助块：

```text
[情绪判断辅助信息]
- 推测情绪：anxious
- 情绪分布：anxious=0.62, sad=0.18, neutral=0.12
- 置信度：0.71
- 效价 valence：-0.45
- 唤醒度 arousal：0.68
- 建议参考权重：0.42
- 简短依据：用户表达了担心和不确定，但没有明显愤怒。

请只按该权重调整语气、共情程度和安抚强度。不要把该判断当作事实，不要替用户断言情绪，不要覆盖用户明确表达的请求。
```

这里最重要的是最后一句限制：情绪结果只是语气参考，不是事实，也不是命令。用户明确提出的需求永远优先。

### 模型选择与回退

`emotion_model_id` 是预留的模型选择接口：

- 留空：使用当前会话默认模型。
- 在 AstrBot WebUI 中点击选择已配置模型：尝试使用指定 AstrBot 模型。
- 当前 AstrBot 环境不支持指定模型或 LLM 调用失败：按 `emotion_fail_open` 决定是否跳过。

推荐做法：

- 如果你追求稳定，先留空，用主 LLM 判断。
- 如果你希望降低成本，后续可以选择更便宜、更快的小模型做情绪判断。
- 如果你不希望额外消耗 token，保持 `enable_emotion_analysis=false`。

### 与 LivingMemory 的关系

情绪判断模块只影响主 LLM prompt，不影响 LivingMemory 存储内容。

| 阶段 | 内容 |
| :--- | :--- |
| 消息事件阶段 | 只写入纯转写文本。 |
| LivingMemory 读取阶段 | 只看到用户语音的干净转写。 |
| LLM 请求阶段 | 才追加语音提示词和情绪辅助信息。 |
| 长期记忆结果 | 不会保存 `anxious=0.62`、`respect_weight=0.42` 这类分析文本。 |

这样做是为了避免长期记忆被模型分析、插件提示词、情绪标签污染。


> 本插件使用 AstrBot 原生插件配置页。下面按功能分组解释每一个配置项。

<details>
<summary>点击查看完整配置项详解</summary>

### 1. 鉴权与接口

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `api_key` | string | 空 | 新版控制台 API Key。填写后优先使用 `X-Api-Key` 鉴权。 |
| `app_key` | string | 空 | 旧版控制台 App Key。仅在未填写 `api_key` 时使用。 |
| `access_key` | string | 空 | 旧版控制台 Access Key。需要和 `app_key` 一起填写。 |
| `resource_id` | string | `volc.bigasr.auc_turbo` | 火山引擎大模型录音文件极速版资源 ID。 |
| `endpoint` | string | `https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash` | 火山官方识别接口地址。 |
| `uid` | string | 空 | 用户标识。留空时自动使用 `api_key`、`app_key` 或 `astrbot`。 |

填写建议：

- 新用户优先只填 `api_key`。
- 旧版控制台用户再考虑 `app_key + access_key`。
- 不要随意修改 `resource_id` 和 `endpoint`，除非你明确知道火山侧要求变更。

### 2. 音频提交与转码

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `submit_mode` | string | `base64` | 音频提交方式，可选 `base64` / `url`。 |
| `max_audio_mb` | int | `20` | 单条语音大小上限。Base64 上传建议保持 20MB 以内。 |
| `timeout_seconds` | int | `60` | 下载、转码和接口请求超时时间。 |
| `enable_transcode` | bool | `true` | 遇到不支持格式时自动调用 `ffmpeg` 转码。 |
| `prefer_bundled_ffmpeg` | bool | `true` | 优先使用 Release 包内置 `ffmpeg`。 |
| `ffmpeg_path` | string | `auto` | `ffmpeg` 可执行文件路径。可填写绝对路径。 |
| `transcode_output_format` | string | `wav` | 转码输出格式，可选 `wav` / `mp3` / `ogg`。 |
| `transcode_sample_rate` | int | `16000` | 转码采样率。语音识别推荐 16000。 |
| `transcode_channels` | int | `1` | 转码声道数。语音识别推荐单声道。 |

`ffmpeg` 查找顺序：

1. 当 `prefer_bundled_ffmpeg=true` 且 `ffmpeg_path=auto` 或 `ffmpeg` 时，优先尝试 Release zip 内置 `bin/linux-x86_64/ffmpeg`。
2. 如果内置文件不能通过 `ffmpeg -version` 启动探测，会自动尝试 `imageio-ffmpeg` 提供的可执行文件。
3. 如果 `imageio-ffmpeg` 也不可启动，最后尝试系统 PATH 中的 `ffmpeg`。
4. 如果你在 `ffmpeg_path` 中填写绝对路径，则只探测并使用该路径。

`/volc_asr_status` 会显示 `ffmpeg来源` 和 `ffmpeg状态`。如果状态为不可用，插件不会在加载阶段崩溃，但遇到 AMR / SILK / M4A 等需要转码的语音时会给出明确错误，并提示你安装系统 `ffmpeg` 或配置 `ffmpeg_path`。

关于 `submit_mode`：

- `base64`：推荐。AstrBot 所在机器先读取或下载音频，再把内容提交给火山引擎。
- `url`：只有当火山引擎服务器可以公网访问该语音 URL 时才适合。大多数 OneBot / NapCat 的 QQ 语音 URL 不满足这个条件。

### 3. 识别参数

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `enable_itn` | bool | `true` | 启用数字规整，例如把口语数字规整成更适合阅读的文本。 |
| `enable_punc` | bool | `true` | 启用自动标点。 |
| `enable_ddc` | bool | `true` | 启用顺滑处理。 |
| `enable_speaker_info` | bool | `false` | 启用说话人信息。普通 QQ 短语音通常不需要。 |

建议保持默认。QQ 短语音大多数是单人短句，开启说话人信息通常收益不大。

### 4. 注入与回复行为

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `auto_recognize` | bool | `true` | 自动识别语音消息总开关。 |
| `inject_as_user_input` | bool | `true` | 将识别结果注入为用户输入，继续交给 LLM。 |
| `voice_prompt_template` | string | 默认语音回复模板 | LLM 请求阶段使用的语音提示词模板。 |
| `inject_on_unclear_voice` | bool | `true` | 静音、杂音、空结果时也注入“没听清”提示。 |
| `unclear_voice_prompt` | string | 默认没听清模板 | 仅在 `inject_on_unclear_voice=true` 时生效。 |
| `reply_transcription` | bool | `false` | 直接回复转写结果。主要用于调试或兼容旧行为。 |
| `reply_template` | string | `语音转文字：{text}` | 直接回复模式下的回复模板。 |
| `stop_event_after_recognition` | bool | `true` | 直接回复或报错后停止事件继续传递，避免后续插件重复处理。 |
| `send_empty_result_message` | bool | `true` | 直接回复模式下，静音或空结果时发送提示。 |

推荐组合：

```text
inject_as_user_input = true
reply_transcription = false
inject_on_unclear_voice = true
```

这组配置能让用户语音自然进入 LLM，同时让 LivingMemory 记录干净文本。

### 5. 场景范围与触发控制

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `enable_private` | bool | `true` | 私聊启用。 |
| `enable_group` | bool | `true` | 群聊启用。 |
| `only_when_at_or_wake` | bool | `false` | 群聊中仅被 @ 或唤醒时识别。 |
| `ignore_self` | bool | `true` | 忽略机器人自己发送的消息。 |

群聊建议：

- 小群或语音量少：可以保持 `only_when_at_or_wake=false`。
- 大群或语音量多：建议开启 `only_when_at_or_wake=true`。

### 6. 错误提示与排查

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `notify_config_error` | bool | `true` | 未配置鉴权时在聊天中提示。 |
| `notify_asr_error` | bool | `true` | 识别失败时在聊天中提示。 |
| `show_logid` | bool | `false` | 回复中显示火山引擎 `logid`，方便排查。 |

排障时可以临时开启：

```text
show_logid = true
notify_asr_error = true
```

复现后把日志或回复中的 `logid` 记录下来，再向火山引擎侧排查。

</details>

## 默认提示词与模板写法

默认 `voice_prompt_template`：

```text
<text>[符号前面的内容是用户的语音转文字内容，请通过上述内容判断用户情绪，并且尽量使用语音回复，严禁讨论本插件的实际功能“转文字”的事实，回复时不要考虑括号内内容]
```

这个模板的目的不是告诉用户“我把语音转成了文字”，而是让 LLM 把语音内容当作用户原话处理，并在合适时倾向语音回复。

### 支持的占位符

| 占位符 | 说明 |
| :--- | :--- |
| `<text>` | 推荐写法，表示识别出的语音文本。 |
| `{text}` | 等价写法，表示识别出的语音文本。 |
| `{logid}` | 火山引擎接口返回的 logid。 |
| `{request_id}` | 请求 ID。 |
| `{duration_ms}` | 本次识别耗时，单位毫秒。 |

如果你在自定义模板中需要字面量 `{` 或 `}`，请写成 `{{` 和 `}}`，避免被 Python 模板格式化解析。

### 偏向文字回复的模板示例

```text
[用户发送了一条语音，以下是自动转写内容：<text>。请将其视为用户本人的输入，并自然回复。]
```

### 偏向语音回复的模板示例

```text
<text>[上面是用户刚刚说出的语音内容。请把它当作用户原话理解，结合上下文自然回复；如果当前系统支持语音输出，请优先使用语音风格进行回应。]
```

### 默认没听清提示词

```text
[用户刚刚发送了一条语音，但系统没有听清内容（可能是静音、杂音或识别失败）。请以没听清为由，自然地请用户再说一次或改用文字补充，不要直接说是系统错误。]
```

## LivingMemory 兼容机制

从 `1.4.7` 开始，插件采用两阶段注入：

1. 消息事件阶段：把语音识别结果写成纯转写文本。
2. LLM 请求阶段：在 `on_llm_request(priority=-10)` 中，把 `req.prompt` 里的纯文本替换成语音提示词模板。

这样可以同时满足两个目标：

- `astrbot_plugin_livingmemory` 记录和召回的是干净的用户原话。
- LLM 最终仍然收到“这是语音转写内容，请自然回复”的提示。

如果旧版本直接把 `voice_prompt_template` 写进消息事件，长期记忆里就可能出现大量类似“请尽量使用语音回复”“不要讨论转文字事实”的模板内容。这个版本避免了这个问题。

如果你在 LivingMemory 中仍看到大量提示词模板文字，请检查：

- 插件版本是否为 `1.4.7` 或更高。
- 是否确实安装了最新 Release zip。
- 是否有其他插件在更早阶段改写了消息内容。
- 日志中是否出现“已将语音识别结果注入为干净用户输入”和“已在 LLM 请求阶段应用语音提示词模板”。

## 命令与状态检查

| 命令 | 用途 |
| :--- | :--- |
| `/volc_asr_status` | 查看插件配置和运行状态。 |
| `/火山语音状态` | 中文别名，等价于上一条。 |

状态检查适合用于确认：

- 当前插件版本和仓库 URL，确认 AstrBot 更新器能找到仓库。
- 是否已配置鉴权。
- 当前是否启用自动识别。
- 当前提交模式是 `base64` 还是 `url`。
- 是否启用转码。
- 当前是否优先使用内置 `ffmpeg`。
- `ffmpeg` 是否真正可启动，以及官方 `preprocess_stage` warning 是否属于插件前置阶段。

## 常见问题与排障

### 上传 zip 后提示找不到 metadata.yaml

请确认你上传的是 Release 页面里的 `astrbot_plugin_volcengine_asr.zip`，并且 zip 根目录直接包含：

```text
metadata.yaml
main.py
_conf_schema.json
requirements.txt
```

不要使用 GitHub 绿色 Code 按钮下载的源码 zip 代替 Release zip。

### 提示需要 ffmpeg

按顺序检查：

1. 你是否使用的是 Release zip。
2. 当前服务器是否为 Linux x86_64 / amd64。
3. `prefer_bundled_ffmpeg` 是否为 `true`。
4. `ffmpeg_path` 是否为 `auto` 或正确的绝对路径。
5. 如果不是 x86_64 架构，是否已经安装系统 `ffmpeg`。
6. 运行 `/volc_asr_status`，查看 `ffmpeg状态` 是否为可用；如果不可用，日志会说明内置、`imageio-ffmpeg`、PATH 分别为什么启动失败。

非 Linux x86_64 / amd64 环境建议：

```text
prefer_bundled_ffmpeg = false
ffmpeg_path = /usr/bin/ffmpeg
```

路径按你的实际系统修改。

### preprocess_stage 提示 Voice processing failed: not a valid file: xxx.amr

如果日志里出现：

```text
[preprocess_stage.stage:81]: Voice processing failed: not a valid file: xxx.amr
```

先看一件事：关闭本插件后这条 warning 是否仍然出现。

如果关闭本插件仍出现，说明它发生在本插件 handler 之前，是 AstrBot 官方 `PreProcessStage` 在尝试把 `Record(file="xxx.amr")` 转成本地 WAV。这个阶段不等于本插件 ffmpeg 转码，也不等于火山 ASR 失败。

AstrBot v4.24.2 的官方预处理大致会做：

```text
event.get_messages()
  -> 找到 Record
  -> component.convert_to_file_path()
  -> ensure_wav(original_path)
  -> 写回 component.file / component.path
```

在 Ubuntu 宝塔面板 Docker 里，这条 warning 很常见：NapCat / OneBot 给出的 `xxx.amr` 可能是 NapCat 容器里的临时文件名，或只是 OneBot file id，并不是 AstrBot 容器内真实存在的路径。

排查顺序：

1. AstrBot 官方 STT 不用时，确认 `provider_stt_settings.enable=false`，并清空或不配置 `provider_stt_settings.provider_id`。
2. 如果还出现 warning，继续检查 `platform_settings.path_mapping` 和 Docker volume。官方 Record 转 WAV 预处理不完全受 STT 开关控制。
3. 如果 NapCat 和 AstrBot 分在不同容器，尽量让两边共享同一个数据目录，例如都能看到 `/AstrBot/data`。
4. 保持本插件 `submit_mode=base64`，让插件通过 OneBot `get_record(file, out_format)` 尝试取回真实语音内容，再交给插件自己的 ffmpeg 转码链路。
5. 插件开启后重点观察是否还出现 `agent_sub_stages.internal:402` 的 `not a valid file: xxx.amr`。如果只剩 `preprocess_stage` warning，而没有 agent 阶段 error，说明插件后续接管链路已经生效，剩下的是官方前置预处理与 Docker/NapCat 文件可读性问题。

简短判断：

```text
preprocess_stage warning = 官方预处理在插件之前读不到 Record 文件
agent_sub_stages error = 官方 agent 后续仍扫到旧 Record
本插件 ffmpeg 失败 = 日志通常会出现在“语音识别准备失败”或 /volc_asr_status 的 ffmpeg状态中
```

### Agent 阶段报 not a valid file: xxx.amr

如果 AstrBot 日志中出现类似：

```text
Error occurred while processing agent: not a valid file: d288c78e8c3716a65e75983adcdd4a5a.amr
```

通常不是火山 ASR 不支持 AMR，也不是插件 `ffmpeg` 转码阶段失败，而是消息在识别成功后继续流向 agent 阶段时，旧消息链里还残留了 OneBot / NapCat 的 `Record(file="xxx.amr")`。这类 `file` 很多时候只是平台临时文件名，不是 AstrBot 机器上的真实本地路径，所以后续组件把它当文件校验时会报错。

`2.1.2` 继续加固了这条链路：

- 情绪判断前会先清理当前语音 `Record`，避免情绪判断路径把旧 `.amr` 残留带到后续 agent。
- 识别失败、配置错误、未听清直接提示、`reply_transcription=true` 直接回复转写等直接回复路径，会先 `stop_event()` 再发送回复，避免默认 agent 继续处理原语音。
- 识别成功或未听清注入时，会把 `event.message`、`event.message_chain`、`event.raw_message`、`message_obj.message`、`message_obj.message_chain`、`message_obj.raw_message` 等常见入口同步替换为纯 `Plain` 文本。
- 替换前会先原地改写旧消息链 list。即使 AstrBot 或其他插件已经持有旧 list 引用，也会看到纯文本，而不是旧 `Record(file="xxx.amr")`。
- 对 AstrBot 内置 agent `build_main_agent` 的前置扫描路径，`2.1.2` 会额外提供干净 `provider_request`，绕开 `event.message_obj.message` / `Reply.chain` 中残留媒体段被扫描和转换。
- 消息链清理支持非 list `MessageChain`，避免链对象不是普通 list 时跳过清理。
- LLM 请求阶段会清空 `ProviderRequest.audio_urls`，并净化 `contexts`、`extra_user_content_parts`、`messages`、`content`、`files` 等可能残留音频附件的字段。
- 语音段查找兼容 `message`、`message_chain`、`raw_message`、裸 OneBot `record` dict 以及嵌套 dict 形态。
- 对只有裸 `file="xxx.amr"` 的 OneBot / NapCat 语音，插件会先尝试组件 `convert_to_base64()`；失败后再尝试 OneBot `get_record` 获取真实语音内容。拿到 AMR bytes 后仍会正常进入插件 `ffmpeg` 转码链路。

如果你仍然看到这个错误，请先确认安装的是 Release 页面中的 `2.1.2` 或更高版本 zip，并重启 AstrBot。然后检查平台是否只提供了裸文件名、没有可下载 URL 或 base64 数据；这种情况下插件会尽量走 `convert_to_base64()`，但平台适配器本身也需要能取得原语音内容。

### URL 模式失败

大多数 OneBot / NapCat 语音 URL 是内网地址、临时地址，或需要 AstrBot 所在机器携带上下文访问。火山引擎服务器通常无法直接访问这些 URL。

建议保持：

```text
submit_mode = base64
```

只有当你确认语音 URL 能被公网匿名访问时，才建议尝试 `submit_mode=url`。

### LLM 没有收到语音内容

检查这些配置：

```text
auto_recognize = true
inject_as_user_input = true
reply_transcription = false
```

再看日志中是否出现：

```text
已将语音识别结果注入为干净用户输入
已在 LLM 请求阶段应用语音提示词模板
```

如果第一条没有出现，说明 ASR 或事件注入阶段可能没有成功。如果第二条没有出现，说明 LLM 请求阶段可能没有走到，或事件没有携带对应标记。

### Bot 直接回复“语音转文字：xxx”

这是直接回复模式。关闭：

```text
reply_transcription = false
```

默认推荐让语音进入 LLM，而不是直接把转写结果发回聊天。

### 静音或杂音时回复很机械

建议开启：

```text
inject_on_unclear_voice = true
```

然后优化 `unclear_voice_prompt`，让模型用更自然的方式请用户重说。

### 群聊里所有语音都会触发，太吵了

开启：

```text
only_when_at_or_wake = true
```

这样只有 Bot 被 @ 或被唤醒时才识别群聊语音。

### 火山接口失败，需要排查

临时开启：

```text
show_logid = true
notify_asr_error = true
```

复现一次后，记录日志或回复中的 `logid`，再结合火山引擎控制台、接口权限、资源 ID、账户余额和网络连通性排查。

### 仓库安装和 Release 安装有什么区别

| 项目 | Release zip | GitHub 仓库安装 | GitHub 源码 zip |
| :--- | :--- | :--- | :--- |
| AstrBot 推荐程度 | 推荐 | 可用 | 不推荐直接当发布包用 |
| 根目录是否直接含 `metadata.yaml` | 是 | 是 | 通常外层会套目录 |
| 是否带内置 `ffmpeg` | 是 | 否 | 否 |
| 适合 Docker / VPS | 是 | 依赖环境 | 依赖环境 |
| 适合普通用户 | 最适合 | 适合能处理依赖的人 | 容易装错 |

## 目录结构与发布包说明

仓库结构大致如下：

```text
.
├── assets/
│   ├── VoiceMountain.svg
│   └── FuckUCodeScore.svg
├── main.py
├── metadata.yaml
├── _conf_schema.json
├── requirements.txt
├── CHANGELOG.md
├── README.md
├── third_party_licenses/
│   └── imageio-ffmpeg.LICENSE
└── astrbot_plugin_volcengine_asr/
    ├── assets/
    │   ├── VoiceMountain.svg
    │   └── FuckUCodeScore.svg
    ├── main.py
    ├── metadata.yaml
    ├── _conf_schema.json
    ├── requirements.txt
    ├── CHANGELOG.md
    ├── README.md
    └── bin/linux-x86_64/ffmpeg
```

说明：

- 仓库根目录用于支持 AstrBot 从 GitHub 仓库地址安装。
- `astrbot_plugin_volcengine_asr/` 用于生成 Release zip。
- 根目录 `main.py` 是轻量入口，插件完整实现位于 `astrbot_plugin_volcengine_asr/main.py`。
- Release zip 根目录不会额外套一层同名目录。
- Release zip 会包含 Linux x86_64 / amd64 内置 `ffmpeg`。

## 验证与维护说明

发布前建议至少确认：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile main.py astrbot_plugin_volcengine_asr/main.py scripts/update_fuck_u_code_score.py scripts/build_release_zip.py
```

```bash
python3 -c "import json,pathlib; [json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['_conf_schema.json','astrbot_plugin_volcengine_asr/_conf_schema.json']]; print('OK')"
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests
```

如果本地没有 `pytest`，至少应确保纯函数 helper 的测试逻辑能运行，配置 JSON 能解析，Release zip 根目录结构正确。

构建 Release zip：

```bash
python3 scripts/build_release_zip.py
```

发布时只上传 `output/astrbot_plugin_volcengine_asr.zip`。根目录旧 zip、`_release_body.json`、`_release_draft.json` 都不是 2.1.0 的发布依据。

## Web UI 接口预留

当前 `main` 仍不把完整 Web UI 合进来，但已经为后续独立 Web UI 分支预留稳定后端接口。未来插件配置页、状态页、情绪计算可视化，都应优先调用这些方法，而不是直接读取插件内部属性。

| 接口 | 用途 |
| :--- | :--- |
| `get_webui_state()` | 返回运行状态快照，包括鉴权模式、接口地址、提交模式、转码参数、情绪判断状态、LivingMemory 兼容状态。 |
| `get_webui_config_schema()` | 返回 `_conf_schema.json`，供 Web UI 渲染配置表单。 |
| `get_webui_config_snapshot()` | 返回当前配置值，并对 `api_key`、`access_key` 做掩码，避免前端直接暴露密钥。 |
| `update_webui_config(updates)` | 预留给 Web UI 保存配置；会执行字段白名单、类型转换、选项校验、范围校验、密钥掩码跳过和运行时重载。 |

`update_webui_config()` 返回结构：

```json
{
  "applied": {
    "submit_mode": "base64"
  },
  "skipped": {
    "api_key": "密钥未变更"
  },
  "errors": {}
}
```

密钥字段有一个专门保护：如果 Web UI 把 `get_webui_config_snapshot()` 中的掩码值原样传回，插件会认为密钥未变更，不会把真实密钥覆盖成 `****` 或 `abcd...wxyz`。后续开发配置型 Web UI 时必须保留这个语义。

## 版本说明

当前版本：`2.1.5`

本版本重点：

- 重新构建语音工作流：`VoiceInput -> AudioPayloadResult -> ASR -> VoiceInjectionPlan -> ProviderRequest`。
- 新增干净 `provider_request`，绕开 AstrBot 内置 agent `build_main_agent` 在构造请求前对 `event.message_obj.message` / `Reply.chain` 的媒体扫描，并兼容非 list `MessageChain`。
- 裸 OneBot / NapCat `Record(file="xxx.amr")` 会在组件转换失败后尝试 `get_record(file, out_format)`，确保能取到真实 AMR 内容并交给 ffmpeg 转码。
- 情绪判断前先清理语音 `Record`，直接回复和失败路径先 `stop_event()` 再回复，避免 `not a valid file: xxx.amr`。
- `emotion_model_id` 在 WebUI 中支持点击选择已配置模型；留空时使用当前会话默认模型。
- 成功识别后，消息阶段只写入干净 `Plain` 文本，LLM 请求阶段再应用语音提示词和情绪辅助。
- `ProviderRequest` 阶段继续清理音频残留，并在找不到原始转写文本时前置 `llm_text`、保留原 prompt，避免丢失 LivingMemory 或 provider 上下文。
- `submit_mode=url` 不再信任 `.amr` / `.silk` 这类 QQ 语音 URL，会回落到下载、转码和 Base64 上传。
- 保留 2.0.4 的 ffmpeg 启动探测、降级、`/volc_asr_status` 状态显示和 Release zip 权限校验。
- 增加工作流回归测试，覆盖成功注入、未听清注入、错误阻断、裸 `.amr` 转换失败、URL AMR 不直传和 LLM 请求兜底。

完整更新记录见 [CHANGELOG.md](./CHANGELOG.md)。

## 第三方组件与许可证

本插件涉及或间接使用以下组件：

- 火山引擎豆包语音大模型录音文件极速版识别 API
- `httpx`
- `imageio-ffmpeg`
- `ffmpeg`

`imageio-ffmpeg` 的许可证文本见 [third_party_licenses/imageio-ffmpeg.LICENSE](./third_party_licenses/imageio-ffmpeg.LICENSE)。

本项目使用 MIT License。内置或间接使用的第三方组件遵循其各自许可证。
