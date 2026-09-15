# 自定义角色与音色

不同用户可换自己的角色精灵 / TTS 音色，无需改业务逻辑代码。

## 角色（Pet）

**权威资源在主机** `pets/`，不靠客户端长期打包。

流程：

1. 主机安装 / 放置 pet 包（`pets/<id>/spritesheet.webp` + `pets/catalog.json`）
2. 客户端连接后发 `pets.list`，下拉选择角色
3. **首次**选中（或首次需要渲染）时从 `http://<主机>:8766/pets/...` 下载
4. 写入客户端本地缓存；之后直接用缓存

客户端内的 `clients/web/sprites/`、`clients/mobile/assets/sprites/` 仅作**离线兜底**（未连上 Runtime 时首屏）。

### 加一个角色（主机）

1. 放入精灵图（与现有相同 8×9 × 192×208 atlas）：

```text
pets/<id>/spritesheet.webp
```

2. 在 `pets/catalog.json` 的 `pets` 数组追加：

```json
{
  "id": "my-pet",
  "label": "我的角色",
  "sheet": "my-pet/spritesheet.webp",
  "url": ""
}
```

3. 确认 `config.yaml`：

```yaml
server:
  assets_port: 8766
pets:
  root: "pets"
# 可选：Tailscale 等
# network.assets_url: "http://100.x.y.z:8766/pets"
```

4. 重启 Runtime。Web / Mobile 重连后下拉出现新角色；选中后自动下载并缓存。

客户端按 `pets.list` 动态生成下拉，**不用改** `pixel-bot.js` / `pixel_bot.dart`。

## 音色（TTS）

音色包只在**主机**，客户端只选 ID：

1. 新建 `voices/<Name>/`（参考 `voices/Haibara/`，含 `voice.yaml` + 参考音频 / 权重）
2. 在根目录 `config.yaml` → `tts.providers` 注册，例如：

```yaml
tts:
  default: "haibara"
  providers:
    haibara:
      type: "gpt-sovits"
      voice_dir: "voices/Haibara"
      url: "http://127.0.0.1:9880"
    myvoice:
      type: "gpt-sovits"
      name: "My Voice"
      voice_dir: "voices/MyVoice"
      url: "http://127.0.0.1:9880"
```

GPT-SoVITS 音色需先起 `api_v2.py`（`.\scripts\start.ps1` 默认会起 `:9880`）。

3. 重启 Runtime。Web / Mobile 连接后会发 `tts.list`，设置里下拉自动出现新音色。

客户端**不打包**音色模型；换用户音色 = 换主机 `voices/` + config。
