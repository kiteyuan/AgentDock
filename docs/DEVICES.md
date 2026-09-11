# Devices 路线图

## 边界

- **主机**：Runtime + STT + Agent + TTS
- **客户端**：WebSocket 瘦终端（连、录、播、显示）——不打包模型

状态机：[`clients/shared/STATE_MACHINE.md`](../clients/shared/STATE_MACHINE.md)

## 已落地

| Device | 形态 | 状态 |
|--------|------|------|
| Web UI | `clients/web/` | 桌面预览（本机 `127.0.0.1`）；不作为局域网开麦正式方案 |
| CLI | `clients/cli/` | `--ui` 打开 Web；`--chat` 调试 |
| Raspberry Pi | `clients/rpi/` | 按键点开点停、OLED |
| Mobile (Flutter) | `clients/mobile/` | 正式手机端骨架：原生麦 + `ws://主机:8765` |

## 打包

| 产物 | 方式 |
|------|------|
| Android APK | GitHub Actions [`build-clients.yml`](../.github/workflows/build-clients.yml) |
| Windows zip | 同上（`windows-latest`） |
| macOS zip | 同上（`macos-latest`） |
| iOS IPA（未签名） | 同上；给 **巨魔 / 侧载**，非 App Store |
| Runtime / TTS / 模型 | **不上 CI**；本机安装运行 |

触发：`main` 推送、tag `client-v*`、或手动 `workflow_dispatch`。  
PR 只跑 Android（省 macOS/Windows 分钟数）。

## 下一步

1. Flutter：联调真机 → UI 对齐 Web（角色 / 按句字幕 / 重播）
2. iOS：巨魔安装验证；若要上架再补 Apple 签名

最小能力对齐：连接 / token / 心跳、点按录音 WAV、播 TTS、状态 ONLINE / LISTENING / PROCESSING / SPEAKING。
