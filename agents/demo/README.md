# Reference Agent — Agent Protocol compliant demo

用于安装/联调前的对照实现。规范见 `docs/AGENT_PROTOCOL.md`。

```bash
python agents/demo/server.py
# GET  /v1/agent
# POST /v1/agent/run     (NDJSON stream)
# POST /v1/agent/cancel

# 测链接
python agents/check_link.py --url http://127.0.0.1:8080/v1/agent/run
```

可选鉴权：`AGENT_TOKEN=dev-token python agents/demo/server.py`
