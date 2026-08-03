---
sidebar_position: 1
title: 快速安装
summary: "通过 README 中的安装脚本以最快的方式安装 DB-GPT"
read_when:
  - 您想要通向可用的 DB-GPT Web UI 的最短路径
  - 您更喜欢使用安装脚本而非手动源码设置
---

import CommandCopyCard from "@site/src/components/mdx/CommandCopyCard";

# 快速安装

运行 DB-GPT 最快的方式。安装脚本会准备本地 DB-GPT 工作空间，生成提供商配置文件，并为您提供一个可直接运行的 webserver 命令。

## 推荐：安装脚本

如果您想要从零到可用的 DB-GPT Web UI 的最短路径，请使用安装脚本。

<CommandCopyCard command={`curl -fsSL https://raw.githubusercontent.com/eosphoros-ai/DB-GPT/main/scripts/install/install.sh | bash`} />

## 系统要求

此快速安装流程适用于：

- **macOS** 或 **Linux**
- 可运行 `bash` 的 shell 环境
- 可访问网络以下载依赖
- 如果您计划立即使用托管的模型提供商，则需要一个 API key

:::tip 最佳适用场景
如果您想在不自行管理仓库结构的情况下快速尝试 DB-GPT，请选择此方式。
:::

## 使用提供商配置文件安装

如果您已经知道要使用哪个提供商，可以在安装时直接传入配置文件和 API key。

### OpenAI 兼容配置文件

<CommandCopyCard command={`curl -fsSL https://raw.githubusercontent.com/eosphoros-ai/DB-GPT/main/scripts/install/install.sh \
  | OPENAI_API_KEY=sk-xxx bash -s -- --profile openai`} />

### 通过 Moonshot API 使用 Kimi 2.5

<CommandCopyCard command={`curl -fsSL https://raw.githubusercontent.com/eosphoros-ai/DB-GPT/main/scripts/install/install.sh \
  | MOONSHOT_API_KEY=sk-xxx bash -s -- --profile kimi`} />

### 通过兼容 OpenAI 的 API 使用 MiniMax

<CommandCopyCard command={`curl -fsSL https://raw.githubusercontent.com/eosphoros-ai/DB-GPT/main/scripts/install/install.sh \
  | MINIMAX_API_KEY=sk-xxx bash -s -- --profile minimax`} />

## 重用现有的本地仓库

已经有本地的 DB-GPT 仓库了？可以直接使用它，而非克隆到 `~/.dbgpt/DB-GPT`。

### 使用 OpenAI 重用本地仓库

<CommandCopyCard command={`OPENAI_API_KEY=sk-xxx \
  bash scripts/install/install.sh --profile openai --repo-dir "$(pwd)" --yes`} />

### 使用 Kimi 重用本地仓库

<CommandCopyCard command={`MOONSHOT_API_KEY=sk-xxx \
  bash scripts/install/install.sh --profile kimi --repo-dir "$(pwd)" --yes`} />

### 使用 MiniMax 重用本地仓库

<CommandCopyCard command={`MINIMAX_API_KEY=sk-xxx \
  bash scripts/install/install.sh --profile minimax --repo-dir "$(pwd)" --yes`} />

## 安装脚本准备的内容

安装脚本会为您设置常见的运行时布局：

- DB-GPT 检出目录位于 `~/.dbgpt/DB-GPT`（除非使用了 `--repo-dir`）
- 生成的配置文件位于 `~/.dbgpt/configs/`
- DB-GPT 主目录位于 `~/.dbgpt/`
- 使用生成的配置文件即可运行 webserver 的命令

## 安装后启动 DB-GPT

安装完成后，使用生成的配置文件启动 webserver：

<CommandCopyCard command={`cd ~/.dbgpt/DB-GPT && uv run dbgpt start webserver --profile <profile>`} />

然后打开 [http://localhost:5670](http://localhost:5670)。

## 验证安装

如果满足以下条件，则安装成功：

- webserver 启动时没有配置错误
- Web UI 可在 `http://localhost:5670` 打开
- 您可以在浏览器中开始对话

## 先检查脚本

如果您想在运行前查看安装脚本的内容：

```bash
curl -fsSL https://raw.githubusercontent.com/eosphoros-ai/DB-GPT/main/scripts/install/install.sh -o install.sh
less install.sh
bash install.sh --profile openai
```

## 替代安装方式

如果安装脚本不适合您的环境：

- 使用 [CLI 安装](/docs/getting-started/cli-quickstart) 进行基于 PyPI 的安装，使用 `dbgpt` 命令
- 使用 [源码安装](/docs/getting-started/deploy/source-code) 进行开发、调试和自定义配置

## 故障排除

### 安装脚本与我的 shell 或平台不兼容

请改用 [CLI 安装](/docs/getting-started/cli-quickstart) 或 [源码安装](/docs/getting-started/deploy/source-code)。

### 我希望对依赖和配置有更多控制

请使用 [源码安装](/docs/getting-started/deploy/source-code)。它会暴露完整的仓库布局和 `uv sync` 工作流程。

### 安装已完成，但 DB-GPT 无法正常启动

请检查 `~/.dbgpt/configs/` 下生成的配置，然后参阅 [安装问题](/docs/getting-started/troubleshooting/installation)。
