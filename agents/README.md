# Agents

本地安装、启动、联调外部 Agent 的目录（功能侧，对应 Runtime 的 `type: http`）。

协议规范：[`docs/AGENT_PROTOCOL.md`](../docs/AGENT_PROTOCOL.md)

```text
agents/
  demo/           # 内置参考 Agent（协议合规，用于测链路）
  pi/             # Pi Coding Agent + HTTP 网关
  check_link.py   # 探测某个 Agent URL 是否可连、能否吐事件
  <your-agent>/   # 后续把 Claude / Codex / Hermes 网关装在这里
```

## 1. 用 demo 测通 Runtime ↔ Agent

```bash
# 终端 A：参考 Agent
python agents/demo/server.py
# → http://127.0.0.1:8080/v1/agent/run

# 终端 B：只测 Agent 协议（不启 Runtime）
python agents/check_link.py --url http://127.0.0.1:8080/v1/agent/run --text "你好"

# 终端 C：完整链路
# config.yaml → agent.default: http
python -m runtime.main
python clients/desktop/main.py --text "你好" --agent http
```

## 2. 安装自己的 Agent

推荐每个 Agent 一个子目录，自带 README 与启动方式：

```text
agents/pi/
  README.md          # 端口、依赖、如何启动
  # 或 clone / submodule / 启动脚本
```

在根目录 `config.yaml` 注册：

```yaml
agent:
  default: pi
  agents:
    pi:
      type: http
      name: Pi Agent
      url: "http://127.0.0.1:9000/v1/agent/run"
      mode: stream
      # auth_token: "${PI_AGENT_TOKEN}"
```

再：

```bash
python agents/check_link.py --url http://127.0.0.1:9000/v1/agent/run
python -m runtime.main
python clients/desktop/main.py --text "测试" --agent pi
```

## 3. 要求

Agent 须实现公开协议（至少 `POST …/run` → NDJSON/SSE/`events[]`）。  
未兼容时，在本目录放一层薄网关，把对方 API 转成协议事件后再配进 Runtime。
