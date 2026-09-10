# Clients（终端）

所有终端共用 **Device Protocol**（Runtime：`runtime/protocol/device.py`；共享副本：`clients/shared/protocol.py`）。  
过程显示：[`shared/turn_view.py`](./shared/turn_view.py)。  
会话状态机：[`shared/STATE_MACHINE.md`](./shared/STATE_MACHINE.md)。

**主机跑大脑**（Runtime / STT / TTS / Agent）；客户端只连 `ws://主机:8765`。

## 目录

| 路径 | 角色 |
|------|------|
| `web/` | **桌面预览 UI**（本机浏览器） |
| `desktop/` | 启动 Web UI / CLI 调试 |
| `pi/` | 树莓派随身终端 |
| `mobile/` | **正式手机端**（Flutter 瘦客户端） |
| `shared/` | 协议 + TurnView + 状态约定 |

## 推荐：桌面预览

```bash
python -m runtime.main   # 另开终端

python clients/desktop/main.py --ui
# 或：cd clients/web && python serve.py
```

**通话**：**点击开始收音 → 再点结束并发送**。

## 手机 App（Flutter）

```bash
cd clients/mobile
flutter create . --project-name agentdock_mobile --org com.agentdock --platforms=android
flutter pub get
flutter run
```

设置里填 `ws://电脑局域网IP:8765`。CI 打 APK：见仓库 Actions `Build Android APK`。

## 桌面 CLI（调试）

```bash
cd clients/desktop
python main.py --chat --agent pi --tts haibara
```

| 输入 | 作用 |
|------|------|
| 文字 + 回车 | 发送文本 |
| 空行 | 开始录音；再空行结束并发送 |
| `/r 5` | 定时录音 |
| `/cancel` | 取消当前轮 |
| `/q` | 退出 |

## Pi

```bash
cd clients/pi && python -m device
```

按键 / Enter：**第一次开始录音，第二次结束发送**。

跨网时改各端 Runtime 地址为 Tailscale 或 Tunnel。
