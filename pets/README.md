# Pets（主机角色包）

客户端**不**长期依赖打包内的精灵图：连接 Runtime 后通过 `pets.list` 拿到清单，
按所选 pet 从本目录经 HTTP 下载，并**缓存到客户端本地**，下次直接用缓存。

## 目录

```text
pets/
  catalog.json
  <pet-id>/
    spritesheet.webp   # 8×9 × 192×208 atlas
    pet.json           # 可选元数据
```

## 下发

Runtime 启动时额外开 HTTP（默认 `:8766`）：

- `GET /pets/catalog.json`
- `GET /pets/<pet-id>/spritesheet.webp`

配置见根目录 `config.yaml` → `server.assets_port` / `pets.root` / `network.assets_url`。

## 加角色

1. 新建 `pets/<id>/spritesheet.webp`
2. 在 `pets/catalog.json` 的 `pets` 数组追加条目
3. 重启 Runtime；客户端重连后下拉会出现新角色，选中后自动下载并缓存
