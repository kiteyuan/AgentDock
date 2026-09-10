# Raspberry Pi voice terminal

```bash
cd clients/pi
pip install -r requirements.txt
python -m device
```

配置：`config.yaml` → `runtime_url`、按键、OLED 等。

交互与 Web 一致：**第一次按键/Enter 开始录音，第二次结束并发送**。
