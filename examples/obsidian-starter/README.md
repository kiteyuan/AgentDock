# Obsidian 参考知识库（Starter）

给新用户的**最小可用** Obsidian 库模板。Agent 默认工作区是仓库根目录的 `workspace/`（已 gitignore，放你自己的知识库）。

## 第一次使用

若 `workspace/` 还不存在或不想从零搭库，可复制本目录作为起点：

```powershell
# Windows PowerShell（不会覆盖已有同名文件时可先备份）
New-Item -ItemType Directory -Force workspace | Out-Null
Copy-Item -Recurse -Force examples/obsidian-starter/* workspace/
```

```bash
mkdir -p workspace && cp -R examples/obsidian-starter/. workspace/
```

然后用 Obsidian「打开文件夹」选 `workspace/`。

已有个人库（如本仓库作者的 Graph View）时：**不要覆盖**，直接把 Obsidian 根目录指到 `workspace/` 即可。

## 目录说明

| 路径 | 作用 |
|------|------|
| `Knowledge/` | 示例笔记（双链、沉淀口令、AgentDock 约定） |
| `.obsidian/` | 最小库配置（无社区插件） |

Agent（Pi 等）的默认 `cwd` 是 `workspace/`，读写笔记、跑命令都在那里。
