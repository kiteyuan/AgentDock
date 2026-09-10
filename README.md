# AgentDock

> AgentDock is an open-source **Agent Bridge / Runtime** that connects devices to agents through sessions and event streams.

AgentDock 是一个开源 **Agent Bridge / Runtime**：通过 Session 与 Event Stream 连接 Device 与任意 Agent。支持 **纯文本** 与 **语音** 双通道。

公网 Agent 接入规范：[`docs/AGENT_PROTOCOL.md`](./docs/AGENT_PROTOCOL.md)（协议标识 `agentdock.agent/1.0`）。

统一客户端 UI：

```bash
python clients/desktop/main.py --ui
# 点击通话开始收音，再点结束
```

## 目录（按功能）

```text
runtime/          # 后端服务：协议、会话、Agent 适配、STT/TTS、网关
clients/          # 瘦终端（只连 WS；不算模型）
  web/            # 桌面预览 UI
  desktop/        # 启动 Web UI + CLI 调试
  pi/             # 树莓派随身终端
  mobile/         # Flutter 手机 App
  shared/         # 协议 / 状态机 / TurnView
agents/           # 本地安装 / 联调外部 Agent（demo + check_link）
voices/           # TTS 音色资源（如 Haibara）
docs/             # 文档
tests/            # 测试
config.yaml       # Runtime 配置
```

## 完整链路

```text
clients/*  ──WebSocket──►  runtime  ──Agent Protocol──►  外部 Agent
                              │
                         STT / TTS
                              │
clients/*  ◄──事件 + 语音────┘
```

## 快速开始

```bash
# Runtime（后端）
pip install -e .
python -m runtime.main
# 或：runtime / agentdock

# 统一 Web UI（另一终端）
python clients/desktop/main.py --ui

# CLI 调试
cd clients/desktop
pip install -r requirements.txt
python main.py --chat --agent pi --tts haibara
python main.py --text "帮我整理桌面的文件"
python main.py --record 5
python main.py --wav ./test.wav
```

## 接入公网 / 自建 Agent

```bash
# 参考 Agent + 链路探测（见 agents/）
python agents/demo/server.py
python agents/check_link.py --url http://127.0.0.1:8080/v1/agent/run

# config.yaml → agent.default: http
python clients/desktop/main.py --text "你好" --agent http
```

安装与联调说明：[`agents/README.md`](./agents/README.md) · 协议：[`docs/AGENT_PROTOCOL.md`](./docs/AGENT_PROTOCOL.md)。

## 默认能力

| 能力 | 默认 |
|------|------|
| STT | Whisper `small` |
| TTS | Edge `zh-CN-XiaoxiaoNeural` |
| Agent | `mock`（可换符合协议的 `http` / `import`） |

配置见 [`config.yaml`](./config.yaml)。跨网：[`docs/DEPLOY_TAILSCALE.md`](./docs/DEPLOY_TAILSCALE.md) · [`docs/DEPLOY_CLOUDFLARE.md`](./docs/DEPLOY_CLOUDFLARE.md)

## 终端客户端

| 客户端 | 路径 | 说明 |
|--------|------|------|
| Web UI | [`clients/web/`](./clients/web/) | 桌面预览：状态 / 回复 / 点击通话 |
| 桌面 | [`clients/desktop/`](./clients/desktop/) | `--ui` 打开 Web；`--chat` CLI |
| 树莓派 | [`clients/pi/`](./clients/pi/) | 按键点开点停 / OLED |
| 手机 | [`clients/mobile/`](./clients/mobile/) | Flutter：原生麦 + `ws://主机:8765` |

```bash
cd clients/web && python -m http.server 8090
cd clients/pi && pip install -r requirements.txt && python -m device
cd clients/mobile && flutter run   # 需本机 Flutter；APK 见 GitHub Actions
```

总览：[`clients/README.md`](./clients/README.md) · [`docs/DEVICES.md`](./docs/DEVICES.md) · [`docs/TECH_PLAN.md`](./docs/TECH_PLAN.md)

## License

MIT
