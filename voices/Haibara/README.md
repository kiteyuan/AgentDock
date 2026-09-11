# Haibara voice pack

GPT-SoVITS v2 音色包（`models/` + `reference/`）。Runtime 通过 `type: gpt-sovits` 调用本机 API。

> **不进公开仓库**：`models/*.ckpt` / `*.pth` 与参考 `*.wav` 已由根目录 `.gitignore` 排除（体积大，且权重通常不宜公开分发）。本机自行放入 `models/` 与 `reference/ref.wav`。

## 启动推理 API（必开）

在 GPT-SoVITS 工程里启动 API（默认 `http://127.0.0.1:9880`），例如：

```bash
python api_v2.py -a 127.0.0.1 -p 9880
```

然后 AgentDock：

```yaml
tts:
  default: haibara
  providers:
    haibara:
      type: gpt-sovits
      voice_dir: voices/Haibara
      url: http://127.0.0.1:9880
```

客户端：设置里从 `tts.list` 下拉选择（见 [`../clients/CUSTOM_ASSETS.md`](../clients/CUSTOM_ASSETS.md)）。

若 API 未启动，Runtime 会自动回退到 Edge TTS（仍会先做口语清洗，避免念 Markdown/emoji）。
