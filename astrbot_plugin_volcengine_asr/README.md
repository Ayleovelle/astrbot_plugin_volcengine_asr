<!-- markdownlint-disable MD033 MD041 -->

<p align="center">
  <img src="./assets/VoiceMountain.svg" alt="火山引擎语音转文字 AstrBot 插件" width="920">
</p>

<p align="center">
  <img src="./assets/FuckUCodeScore.svg" alt="Fuck-U-Code 代码质量评分" width="250">
</p>

<h1 align="center">AstrBot 火山引擎语音转文字插件</h1>

<p align="center">
  <strong>把 QQ 语音转成干净文本，再交给 AstrBot、LLM 和长期记忆系统继续处理。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.4.7-brightgreen.svg" alt="Version 1.4.7">
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

## 这个插件做什么

`astrbot_plugin_volcengine_asr` 是一个面向 AstrBot 的 QQ 语音识别插件。它会监听消息链中的 `Record` 语音段，读取或下载音频，必要时用 `ffmpeg` 转码，然后调用火山引擎豆包语音「大模型录音文件极速版识别 API」完成转写。

默认模式下，它不会把转写文本直接发回聊天，而是把当前消息改写成用户输入，让 AstrBot 后续的 LLM、TTS、长期记忆等插件继续处理。这样用户发语音时，Bot 也能像处理文字消息一样理解上下文。

## 核心特性

| 能力 | 说明 |
| :--- | :--- |
| 自动识别 QQ 语音 | 支持私聊和群聊，识别 OneBot v11 / NapCat 返回的 `Record` 语音消息。 |
| 内置转码链路 | 支持 AMR、SILK、M4A 等格式转为 WAV / MP3 / OGG，再提交给火山引擎。 |
| 适合 Docker / VPS | Release 包内置 Linux x86_64 / amd64 版 `ffmpeg`，大多数容器环境不需要额外安装。 |
| LLM 友好 | 默认把语音内容注入为用户输入，而不是机械回复“语音转文字：xxx”。 |
| LivingMemory 友好 | 先给记忆插件纯转写文本，再给 LLM 套语音提示词，避免长期记忆被模板污染。 |
| 可控触发范围 | 可分别控制私聊、群聊、仅被 @ 或唤醒时识别、是否忽略机器人自身消息。 |
| 友好降级 | 静音、杂音、空结果时可让 LLM 自然地请用户重说。 |

## 适配信息

| 项目 | 当前状态 |
| :--- | :--- |
| 插件版本 | `1.4.7` |
| AstrBot 版本 | `>=4.16,<5` |
| Python 版本 | `3.10+` |
| 默认平台 | `aiocqhttp` / OneBot v11 |
| 主要依赖 | `httpx`，仓库安装时额外使用 `imageio-ffmpeg` 兜底 |
| 火山资源 ID | `volc.bigasr.auc_turbo` |

## 安装

### 方式一：上传 Release 压缩包

推荐优先使用这种方式。它带有内置 `ffmpeg`，适合不方便在 VPS、Docker 或云应用里手动安装转码工具的环境。

1. 打开 [GitHub Releases](https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr/releases/latest)。
2. 下载 `astrbot_plugin_volcengine_asr.zip`。
3. 进入 AstrBot WebUI 的插件页面。
4. 选择从文件安装，上传这个 zip。
5. 重载插件或重启 AstrBot。

压缩包根目录应直接包含：

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

如果 zip 外面又套了一层同名目录，AstrBot 可能会报找不到 `metadata.yaml`。

### 方式二：从 GitHub 仓库安装

在 AstrBot WebUI 里使用仓库地址安装：

```text
https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr
```

仓库根目录已提供 `metadata.yaml`、`main.py`、`_conf_schema.json` 和 `requirements.txt`，可以被 AstrBot 直接识别。仓库安装不会带 Release zip 中的内置 `bin/linux-x86_64/ffmpeg`，所以根目录依赖会安装 `imageio-ffmpeg` 作为转码兜底。

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

如果你不是 Linux x86_64 / amd64 环境，可以关闭 `prefer_bundled_ffmpeg`，并把 `ffmpeg_path` 改成系统中的 `ffmpeg` 路径。

## 火山引擎准备

1. 在火山引擎控制台开通豆包语音「大模型录音文件极速版识别」。
2. 确认资源 ID 为 `volc.bigasr.auc_turbo`。
3. 新版控制台优先使用 `api_key`。
4. 旧版控制台可继续使用 `app_key + access_key`。

只要填写了 `api_key`，插件会优先走 `X-Api-Key` 鉴权；未填写 `api_key` 时，才会尝试 `app_key + access_key`。

## 快速配置

大多数 OneBot v11 + NapCat + Linux Docker 用户只需要改这些：

| 配置项 | 推荐值 | 说明 |
| :--- | :--- | :--- |
| `api_key` | 你的火山引擎 API Key | 新版控制台优先填这一项。 |
| `submit_mode` | `base64` | 由 AstrBot 读取音频后上传，适合 QQ 语音文件。 |
| `enable_transcode` | `true` | 自动把 AMR、SILK 等格式转成火山接口更容易接受的格式。 |
| `prefer_bundled_ffmpeg` | `true` | Release 包内置 Linux x86_64 `ffmpeg`。 |
| `inject_as_user_input` | `true` | 让语音像用户文字输入一样继续交给 LLM。 |
| `reply_transcription` | `false` | 保持默认，不直接回复转写文本。 |

发送一条 QQ 语音后，默认流程是：

```text
语音消息 -> 火山 ASR -> 纯转写文本 -> LivingMemory / LLM 请求 -> 模型回复
```

## 工作流程

```mermaid
flowchart LR
    A[QQ 语音 Record] --> B[读取 file / url / path]
    B --> C[下载或读取音频]
    C --> D{格式是否支持}
    D -->|WAV / MP3 / OGG / OPUS| E[Base64 上传]
    D -->|AMR / SILK / M4A 等| F[ffmpeg 转码]
    F --> E
    E --> G[火山引擎 ASR]
    G --> H[得到纯转写文本]
    H --> I[改写事件为 Plain 文本]
    I --> J[LivingMemory 检索和存储]
    J --> K[LLM 请求阶段套语音提示词]
    K --> L[LLM 生成回复]
```

这个顺序很重要：记忆插件读到的是干净文本，LLM 最终看到的是带语音回复引导的 prompt。

## 配置说明

### 鉴权与接口

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `api_key` | 空 | 新版控制台 API Key，推荐使用。 |
| `app_key` | 空 | 旧版控制台 App Key。 |
| `access_key` | 空 | 旧版控制台 Access Key。 |
| `resource_id` | `volc.bigasr.auc_turbo` | 大模型录音文件极速版资源 ID。 |
| `endpoint` | 火山官方接口地址 | 通常不需要改。 |
| `uid` | 空 | 留空时自动使用 `api_key`、`app_key` 或 `astrbot`。 |

### 音频提交与转码

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `submit_mode` | `base64` | 推荐保持默认。`url` 要求火山服务器能公网访问语音 URL。 |
| `max_audio_mb` | `20` | 单条语音大小上限。 |
| `timeout_seconds` | `60` | 下载、转码和接口请求超时时间。 |
| `enable_transcode` | `true` | 开启自动转码。 |
| `prefer_bundled_ffmpeg` | `true` | 优先使用插件内置 `ffmpeg`。 |
| `ffmpeg_path` | `auto` | 可改为系统 `ffmpeg` 绝对路径。 |
| `transcode_output_format` | `wav` | 可选 `wav`、`mp3`、`ogg`。 |
| `transcode_sample_rate` | `16000` | 语音识别场景推荐 16000。 |
| `transcode_channels` | `1` | 推荐单声道。 |

### 识别参数

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `enable_itn` | `true` | 数字规整。 |
| `enable_punc` | `true` | 自动标点。 |
| `enable_ddc` | `true` | 顺滑处理。 |
| `enable_speaker_info` | `false` | 说话人信息，普通 QQ 短语音通常不需要。 |

### 行为控制

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `auto_recognize` | `true` | 自动识别语音消息。 |
| `inject_as_user_input` | `true` | 把识别结果注入为用户输入。 |
| `voice_prompt_template` | 默认语音回复模板 | 支持 `<text>` 或 `{text}` 占位符。 |
| `inject_on_unclear_voice` | `true` | 空结果或静音时也注入“没听清”提示。 |
| `unclear_voice_prompt` | 默认没听清模板 | 只在 `inject_on_unclear_voice=true` 时生效。 |
| `reply_transcription` | `false` | 调试用。开启后直接回复转写结果。 |
| `reply_template` | `语音转文字：{text}` | 仅在直接回复模式下使用。 |

### 范围与排查

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `enable_private` | `true` | 私聊启用。 |
| `enable_group` | `true` | 群聊启用。 |
| `only_when_at_or_wake` | `false` | 群聊较吵时可以开启。 |
| `ignore_self` | `true` | 忽略机器人自己发送的消息。 |
| `notify_config_error` | `true` | 鉴权未配置时在聊天中提示。 |
| `notify_asr_error` | `true` | 识别失败时在聊天中提示。 |
| `show_logid` | `false` | 排查火山接口问题时可临时开启。 |

## 默认提示词

默认 `voice_prompt_template`：

```text
<text>[符号前面的内容是用户的语音转文字内容，请通过上述内容判断用户情绪，并且尽量使用语音回复，严禁讨论本插件的实际功能“转文字”的事实，回复时不要考虑括号内内容]
```

偏向文字回复时，可以改成：

```text
[用户发送了一条语音，以下是自动转写内容：<text>。请将其视为用户本人的输入，并自然回复。]
```

默认 `unclear_voice_prompt`：

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

如果你在 LivingMemory 里看到大量提示词模板文字，说明仍在使用旧版本，请更新到 `1.4.7` 或更高版本。

## 命令

| 命令 | 用途 |
| :--- | :--- |
| `/volc_asr_status` | 查看插件配置和运行状态。 |
| `/火山语音状态` | 中文别名，等价于上一条。 |

## 常见问题

### 上传 zip 后提示找不到 metadata.yaml

请确认 zip 根目录直接包含 `metadata.yaml`，而不是：

```text
astrbot_plugin_volcengine_asr/
└── metadata.yaml
```

推荐直接下载 Releases 中已经打好的 zip。

### 提示需要 ffmpeg

确认以下几点：

- 你使用的是 Release zip，而不是直接下载 GitHub 源码 zip。
- 当前服务器架构是 Linux x86_64 / amd64。
- `prefer_bundled_ffmpeg=true`。
- 如果不是 x86_64，请安装系统 `ffmpeg`，并设置 `ffmpeg_path`。

### URL 模式失败

大多数 OneBot / NapCat 语音 URL 是内网地址、临时地址或需要本机访问。火山引擎服务器无法访问这些 URL 时会失败。建议保持：

```text
submit_mode = base64
```

### LLM 没有收到语音内容

检查：

- `auto_recognize=true`
- `inject_as_user_input=true`
- `reply_transcription=false`
- 日志中是否出现“已将语音识别结果注入为干净用户输入”
- 日志中是否出现“已在 LLM 请求阶段应用语音提示词模板”

### Bot 直接回复“语音转文字：xxx”

这是直接回复模式。关闭：

```text
reply_transcription = false
```

### 火山接口失败

临时开启：

```text
show_logid = true
```

复现一次后，把日志或回复里的 `logid` 提供给火山引擎排查。

## 文件结构

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
└── bin/
    └── linux-x86_64/
        └── ffmpeg
```

这就是 Release zip 内的插件结构，`metadata.yaml` 位于压缩包根目录。

## 第三方组件

- 火山引擎豆包语音大模型录音文件极速版识别 API
- `httpx`
- `imageio-ffmpeg`
- `ffmpeg`

`imageio-ffmpeg` 的许可证文本见 [third_party_licenses/imageio-ffmpeg.LICENSE](./third_party_licenses/imageio-ffmpeg.LICENSE)。

## 许可证

本项目使用 MIT License。内置或间接使用的第三方组件遵循其各自许可证。
