# Device 客户端会话状态机

所有瘦客户端（Web / Pi / Flutter）共用同一套状态与消息。  
大脑在主机 Runtime；客户端只做连接、录音、播 TTS、展示。

## 状态

| 状态 | 含义 | 可点按通话 |
|------|------|------------|
| `offline` | 未连接 / 断线 | 否 |
| `connecting` | 正在连 WS / 等 `session.accept` | 否 |
| `idle` | 在线，可开下一轮 | 是 |
| `listening` | 正在录音 | 是（再点 = 结束发送） |
| `busy` | STT / Agent 处理中 | 否 |
| `speaking` | 正在收/播 TTS | 否（取消除外） |
| `error` | 出错；可重连或回 idle | 视实现 |

点按交互：**第一次开始录音 → 第二次结束并发送**（与 Web / Pi 一致）。

## 主流程

```text
offline
  │ connect + device.hello
  ▼
connecting ──session.accept──► idle
  │
  │ (用户点通话)
  ▼
listening ──再点──► audio.start + 二进制 WAV + audio.end
  │
  ▼
busy ◄── stt.final / agent.thinking / tool_* / agent.message(speak)
  │
  │ tts.start (+ 可选 text 字幕)
  ▼
speaking ◄── 二进制音频帧 ── tts.end（可多句排队）
  │
  │ agent.done 且播放队列空
  ▼
idle
```

`session.cancel` / `agent.cancel`：清空 TTS 队列 → `idle`。

## 消息（摘要）

**客户端 → Runtime**

| type | 作用 |
|------|------|
| `device.hello` | `device_id`, `device_type`, `protocol_version`, 可选 `token` / `tts_id` |
| `user.message` | 文本轮（可选） |
| `audio.start` / 二进制 / `audio.end` | 一轮语音；WAV 建议 16 kHz mono PCM |
| `tts.select` | 选音色 |
| `session.cancel` | 取消当前轮 |
| `device.ping` | 心跳 |

**Runtime → 客户端**

| type | 作用 |
|------|------|
| `session.accept` | 给 `session_id` |
| `stt.partial` / `stt.final` | 识别 |
| `agent.thinking` / `tool_*` / `agent.message` | 过程 / 回复；口语常带 `speak: true` |
| `tts.start` | 可带 `text`（按句字幕）、`format` |
| *(binary)* | TTS 音频块 |
| `tts.end` | 本句音频结束 |
| `agent.done` / `agent.cancel` / `error` | 收尾 |

权威类型表：`runtime/protocol/device.py`。  
Python 构造：`clients/shared/protocol.py`。

## 双通道

- **显示**：`thinking` / `tool_*` / 非 speak 的 `agent.message`
- **播报**：`agent.message` 且 `speak !== false` → 进 TTS；字幕宜跟 `tts.start.text` 按句出现

## 平台职责

| 层 | 职责 |
|----|------|
| Runtime | STT / Agent / TTS |
| `clients/shared` | 协议与状态约定 |
| 各端 UI | 麦、扬声器、按键/点按、字幕 |
