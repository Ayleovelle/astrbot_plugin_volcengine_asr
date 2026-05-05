<!-- markdownlint-disable MD024 MD033 MD041 -->

<p align="center">
  <img src="./assets/VoiceMountain.svg" alt="火山引擎语音转文字 AstrBot 插件" width="920">
</p>

<p align="center">
  <sub>简洁扁平化头图：突出 QQ 语音识别、火山 ASR、纯文本注入和 LivingMemory 友好，并保留火山学者意象。</sub>
</p>

<p align="center">
  <img src="./assets/FuckUCodeScore.svg" alt="Fuck-U-Code 代码质量评分" width="250">
</p>

<h1 align="center">AstrBot 火山引擎语音转文字插件</h1>

<p align="center">
  <strong>让 QQ 语音像文字消息一样进入 AstrBot、LLM、TTS 和长期记忆流程。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0.0-brightgreen.svg" alt="Version 2.0.0">
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
| 1. [插件定位](#插件定位) | 10. [插件 Web UI](#插件-web-ui) |
| 2. [适合谁使用](#适合谁使用) | 11. [完整配置说明](#完整配置说明) |
| 3. [核心特性](#核心特性) | 12. [默认提示词与模板写法](#默认提示词与模板写法) |
| 4. [运行流程](#运行流程) | 13. [LivingMemory 兼容机制](#livingmemory-兼容机制) |
| 5. [安装方式](#安装方式) | 14. [命令与状态检查](#命令与状态检查) |
| 6. [火山引擎准备](#火山引擎准备) | 15. [常见问题与排障](#常见问题与排障) |
| 7. [推荐配置](#推荐配置) | 16. [目录结构与发布包说明](#目录结构与发布包说明) |
| 8. [情绪判断快速配置](#情绪判断快速配置) | 17. [第三方组件与许可证](#第三方组件与许可证) |
| 9. [情绪判断模块](#情绪判断模块) | |

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

## 运行流程

默认推荐流程如下：

```text
QQ 语音 Record
  -> 读取 file / url / path
  -> 下载或读取音频
  -> 检测格式与大小
  -> 必要时调用 ffmpeg 转码
  -> Base64 提交到火山引擎 ASR
  -> 得到纯转写文本
  -> 可选：情绪判断 LLM 分析转写文本和上下文
  -> 消息事件阶段只注入 Plain 纯文本
  -> LivingMemory 读取和存储干净文本
  -> LLM 请求阶段套 voice_prompt_template 和情绪辅助信息
  -> 主 LLM 按参考权重调整语气并生成回复
```

对应流程图：

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
    H --> I{启用情绪判断?}
    I -->|是| J[情绪判断 LLM 输出 JSON]
    J --> K[插件公式计算参考权重]
    I -->|否| L[跳过情绪增强]
    K --> M[构造主 LLM 情绪辅助块]
    L --> N[改写事件为 Plain 文本]
    M --> N
    N --> O[LivingMemory 检索和存储纯文本]
    O --> P[LLM 请求阶段套语音提示词]
    P --> Q[主 LLM 生成回复]
```

这个顺序很重要：记忆插件读到的是用户实际说的话，而不是“请尽量使用语音回复”这类提示词包装。

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
- 如果后续 AstrBot 暴露可稳定枚举的模型列表，可以在这里填写指定模型 ID，让情绪判断走更便宜或更快的模型。
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

- 留空：使用当前会话主 LLM。
- 填写模型 ID：尝试使用指定 AstrBot 模型。
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


## 插件 Web UI

Web UI 控制台在独立开发分支中提供，用于快速查看插件运行状态，并直接编辑插件配置。这样可以把核心语音识别逻辑和 Dashboard 页面开发拆开，后续改页面时不会影响 main 的 ASR/情绪判断链路。

状态页路径：

```text
pages/status/index.html
astrbot_plugin_volcengine_asr/pages/status/index.html
```

后端接口：

```text
/api/plug/astrbot_plugin_volcengine_asr/status
/api/plug/astrbot_plugin_volcengine_asr/config
```

页面展示内容：

| 区块 | 内容 |
| :--- | :--- |
| ASR 状态 | 鉴权、自动识别、提交模式、处理方式、最大音频大小。 |
| 转码链路 | 是否启用转码、输出格式、采样率、声道数、ffmpeg 来源。 |
| 情绪判断 LLM | 启用状态、模型、上下文轮数、最大参考权重、失败放行。 |
| 模型可视化 | 展示 ASR → 情绪 JSON → 熵确定性 → 证据强度 → 参考权重 → 主 LLM 的完整工作流，并用三维情绪云图表现情绪分布。 |
| 触发与兼容 | 私聊/群聊开关、仅 @ 或唤醒、忽略自身、LivingMemory 纯文本保护。 |

可编辑内容：

- 鉴权、接口、音频提交、转码参数、识别参数。
- 注入模式、回复模板、未听清处理、触发范围和排查开关。
- 情绪判断 LLM 的开关、模型 ID、上下文轮数、最大参考权重、超时和提示词模板。

交互设计：

- 配置区按功能分组，切换分组时有淡入和位移动画。
- 顶部状态卡片用于快速判断鉴权、提交模式、转码和情绪判断状态。
- 情绪模型可视化页提供三维情绪云图、负面到正面的平滑颜色过渡、公式展开、可调参数滑块和文献依据链接。
- 保存成功或失败会在右下角弹出过渡提示。
- 前端通过 AstrBot Plugin Pages 的 `window.AstrBotPluginPage.apiGet/apiPost` 调后端接口。
- 后端按 `_conf_schema.json` 做类型转换和可选值校验，再调用 `save_config()` 写回配置。
- 不提供音频上传测试，避免临时文件和权限复杂度。
- 页面通过 AstrBot Plugin Pages 的 `window.AstrBotPluginPage.apiGet("status")` 调后端接口。
- 如果离开 AstrBot iframe 单独调试，会 fallback 到 `/api/plug/astrbot_plugin_volcengine_asr/...`。

## 完整配置说明

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
2. 如果内置文件不可用，尝试 `imageio-ffmpeg` 提供的可执行文件。
3. 最后尝试系统 PATH 中的 `ffmpeg`。
4. 如果你在 `ffmpeg_path` 中填写绝对路径，则优先使用该路径。

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

- 是否已配置鉴权。
- 当前是否启用自动识别。
- 当前提交模式是 `base64` 还是 `url`。
- 是否启用转码。
- 当前是否优先使用内置 `ffmpeg`。

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

非 Linux x86_64 / amd64 环境建议：

```text
prefer_bundled_ffmpeg = false
ffmpeg_path = /usr/bin/ffmpeg
```

路径按你的实际系统修改。

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
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile main.py astrbot_plugin_volcengine_asr/main.py
```

```bash
python3 -c "import json,pathlib; [json.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['_conf_schema.json','astrbot_plugin_volcengine_asr/_conf_schema.json']]; print('OK')"
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests
```

如果本地没有 `pytest`，至少应确保纯函数 helper 的测试逻辑能运行，配置 JSON 能解析，Release zip 根目录结构正确。

## 版本说明

当前版本：`2.0.0`

本版本重点：

- 根目录入口轻量化，减少双份主逻辑维护成本。
- 修复语音转写内容包含 `{}` 时的提示词模板渲染边界问题。
- 保持 LivingMemory 两阶段注入语义。
- 明确 Release zip、仓库安装、源码 zip 的区别。
- 补齐 `ffmpeg` 查找顺序和配置项说明。
- 增加基础 helper 测试。
- 更新 README 视觉资源和项目展示。

完整更新记录见 [CHANGELOG.md](./CHANGELOG.md)。

## 第三方组件与许可证

本插件涉及或间接使用以下组件：

- 火山引擎豆包语音大模型录音文件极速版识别 API
- `httpx`
- `imageio-ffmpeg`
- `ffmpeg`

`imageio-ffmpeg` 的许可证文本见 [third_party_licenses/imageio-ffmpeg.LICENSE](./third_party_licenses/imageio-ffmpeg.LICENSE)。

本项目使用 MIT License。内置或间接使用的第三方组件遵循其各自许可证。
