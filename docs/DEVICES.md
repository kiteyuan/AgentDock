# Devices 路线图

## 边界

- **主机**：Runtime + STT + Agent + TTS
- **客户端**：WebSocket 瘦终端（连、录、播、显示）——不打包模型

状态机：[`clients/shared/STATE_MACHINE.md`](../clients/shared/STATE_MACHINE.md)

## 已落地

| Device | 形态 | 状态 |
|--------|------|------|
| Web UI | `clients/web/` | 桌面预览（本机 `127.0.0.1`）；不作为局域网开麦正式方案 |
| Desktop | `clients/desktop/` | `--ui` 打开 Web；`--chat` CLI |
| Raspberry Pi | `clients/pi/` | 按键点开点停、OLED |
| Mobile (Flutter) | `clients/mobile/` | 正式手机端骨架：原生麦 + `ws://主机:8765` |

## 打包

| 产物 | 方式 |
|------|------|
| Android APK | GitHub Actions [`.github/workflows/build-android.yml`](../.github/workflows/build-android.yml) |
| Web 静态 zip | 可选 [`.github/workflows/pack-web.yml`](../.github/workflows/pack-web.yml) |
| Runtime / TTS / 模型 | **不上 CI**；本机安装运行 |

触发 APK：`main` 推送、tag `client-v*`，或手动 `workflow_dispatch`。

## 下一步

1. Flutter：联调真机 → UI 对齐 Web（角色 / 按句字幕 / 重播）
2. 需要时再加 iOS（证书 + macOS runner）

最小能力对齐：连接 / token / 心跳、点按录音 WAV、播 TTS、状态 ONLINE / LISTENING / PROCESSING / SPEAKING。
