# astrbot_plugin_volcengine_asr

基于火山引擎豆包语音「大模型录音文件极速版识别 API」的 AstrBot 语音转文字插件。插件会监听 AstrBot 消息链中的 `Record` 语音段，适用于通过 OneBot v11 接入 NatCat/NapCat 后在 QQ 内收到语音并自动回复文字的场景。

本插件只做语音转文字，不依赖 AstrBot 自身的 TTS 功能，也不会调用 AstrBot 内置的 STT 提供商。

插件已内置 AstrBot v4.24.1 `StarMetadata.pages` 字段缺失的兼容处理，避免加载时出现“元数据载入失败: 'StarMetadata' object has no attribute 'pages'”警告。

## 功能

- 自动识别私聊和群聊中的 QQ 语音消息。
- 支持火山引擎新版控制台 `api_key` 鉴权，也支持旧版控制台 `app_key + access_key`。
- 默认使用 Base64 上传音频，适合 OneBot/NatCat 返回的本地或内网语音文件。
- 可配置只在被 @ 或唤醒时识别、识别后是否阻止事件继续进入后续 LLM/TTS 流程。
- 提供 `/volc_asr_status` 或 `/火山语音状态` 查看配置状态。

## 前提

1. 已部署 AstrBot，并通过 OneBot v11 接入 NatCat/NapCat 等 QQ 客户端。
2. 已在火山引擎开通豆包语音大模型录音文件极速版识别能力。
3. 已获得新版控制台的 `API Key`，或旧版控制台的 `App Key` 与 `Access Key`。
4. 火山引擎侧已开通资源 `volc.bigasr.auc_turbo`。

火山引擎极速版接口一次请求直接返回识别结果，无需提交任务后轮询。官方限制中音频大小上限为 100MB，格式支持 WAV、MP3、OGG OPUS；本插件默认限制为 20MB，便于 Base64 上传。

## 安装

将本目录放到 AstrBot 的插件目录：

```text
AstrBot/data/plugins/astrbot_plugin_volcengine_asr
```

确保目录中包含：

```text
main.py
metadata.yaml
_conf_schema.json
requirements.txt
README.md
```

然后在 AstrBot WebUI 的插件管理中重载插件，或重启 AstrBot。AstrBot 会依据 `requirements.txt` 安装 `httpx`。

## 配置

在 AstrBot WebUI 插件配置页填写以下关键配置：

| 配置项 | 说明 |
| --- | --- |
| `api_key` | 新版控制台 API Key。填写后优先使用。 |
| `app_key` / `access_key` | 旧版控制台鉴权信息；未填写 `api_key` 时才使用。 |
| `resource_id` | 默认 `volc.bigasr.auc_turbo`。 |
| `submit_mode` | 默认 `base64`。如果改为 `url`，必须保证火山引擎能公网访问语音 URL。 |
| `max_audio_mb` | 默认 20。火山引擎上限为 100MB。 |
| `enable_private` / `enable_group` | 控制私聊或群聊是否识别。 |
| `only_when_at_or_wake` | 群聊太吵时可开启，只在 @ 机器人或唤醒时识别。 |
| `stop_event_after_recognition` | 默认开启。识别后阻止消息继续进入后续 LLM/TTS 流程。 |
| `reply_template` | 回复模板，默认 `语音转文字：{text}`。 |
| `show_logid` | 排查火山引擎问题时可开启。 |

## 使用

配置完成后，在 QQ 私聊或群聊中发送语音。机器人会回复：

```text
语音转文字：这里是识别结果
```

查看状态：

```text
/volc_asr_status
```

或：

```text
/火山语音状态
```

## 关于 QQ 语音格式

火山引擎该接口官方列出的支持格式是 WAV、MP3、OGG OPUS。多数 OneBot v11 适配器会把语音文件暴露为可下载文件或 URL，本插件会默认下载后 Base64 上传。

如果你的 NatCat/NapCat 实际返回的是 silk、amr 等火山引擎不支持的格式，需要在 OneBot 端配置语音转码，或让适配器返回 MP3/WAV/OGG OPUS。否则火山引擎可能返回“音频格式不正确”。

## 排查

- 收到“未配置”：检查 `api_key`，或旧版 `app_key` 与 `access_key` 是否填写完整。
- 收到“音频格式不正确”：检查 OneBot/NatCat 返回的实际语音格式。
- URL 模式失败：切回默认 `base64`。URL 模式要求火山引擎服务器能直接访问该地址。
- 需要火山引擎工单定位时，打开 `show_logid` 后复现一次，把回复中的 `logid` 提供给火山引擎。
