---
team: 用户流量策略科
type: skill
name: token-usage-universal
contributor: 郭珂宇
created: 2026-03-25
version: 1.1
status: 已整理
tags: [token使用监控, 本地优先, exact-first, 多来源适配, 跨平台, 中文版, opencode, trae, 内网GBK兼容, opencode-cli对话式装]
usage_count: 0
effect: 把散落在本机各 AI 客户端、CLI 工具和 API 日志中的 token 消耗，自动汇总成可直接决策的本地面板
---

# Token Usage Universal

![CI](./docs/images/ci-badge.svg)

## 简介

一站式本地 token 使用监控工具。把散落在本机各个 AI 客户端、CLI 工具和 API 日志中的 token 消耗记录，自动汇总成清晰、直观的本地面板。不依赖云端账单页，exact-first，没有真源就明确说没有。

## 用途

- 面向人类阅读、复盘对齐与成本评审讨论。
- 适用于"今天 token 用了多少 / 哪个模型最费 / 为什么某个客户端没统计到"等日常查询、趋势复盘和来源排障场景。
- 作为可复用 skill 资产沉淀，便于后续统一维护和接入其他 agent / launcher。

## 使用方法

推荐顺序——**opencode CLI 用户对话式一键装**（最短路径）：

1. 解压 zip 得到 `token-usage-universal/` 目录。
2. 打开 opencode CLI，把下面这段作为**首条对话消息**贴进去：
   > 请帮我把 token-usage-universal 这个 skill 装进 opencode CLI。先用 `find ~ -maxdepth 6 -type d -name token-usage-universal -not -path "*/.*" 2>/dev/null | head -1`（Windows 用 PowerShell 的 `Get-ChildItem -Path $HOME -Recurse -Depth 6 -Directory -Filter token-usage-universal` 等价命令）找仓库路径，然后跑 `python3 <那个路径>/scripts/install_to_opencode.py` 并贴出输出，最后提醒我重启 opencode CLI。
3. AI 会自动完成安装。
4. 重启 opencode CLI。
5. 以后对话里说 `token` / `用量` / `今天 token 用了多少` 即自动触发面板，不用再贴任何指令。

不想走对话、直接命令行装：

```bash
python3 scripts/install_to_opencode.py
```

不装 skill 只用独立 CLI：

```bash
python3 scripts/token_usage.py health                       # 看本机哪些来源 ready
python3 scripts/token_usage.py report --today               # 今日总览
python3 scripts/token_usage.py diagnose --source <id> --today   # 查某来源为何没统计
```

完整对话式提示词可命令行生成（含 Windows 路径检索兜底）：

```bash
python3 scripts/install_to_opencode.py --print-prompt
```

## 适用版本

- 当前版本：`v1.1`（Windows GBK 兼容 + opencode CLI 对话式装 + OpenCode v1.1.13 token schema 适配）
- 核心入口：`scripts/token_usage.py`
- 自然语言触发描述：`SKILL.md`
- 运行环境：Python 3.8+，Windows / macOS / Linux 通用，不依赖外部三方包
- 触发词配置（短触发）：`token / 用量 / 消耗量 / 使用量 / 消耗`
- 补充说明：在日常查询或排障前先跑 `python3 scripts/token_usage.py health` 确认本机哪些来源已 ready。
- 补充说明：不依赖任何 skills 目录或特定 AI 客户端框架，直接运行 Python 脚本即可使用。
- 补充说明：如需接入其他 agent / launcher，直接调用 `scripts/token_usage.py` 即可。

## 效果

- 通过标准化目录、`SKILL.md` 自然语言触发描述和一键安装脚本，降低查找和复用成本。
- 让 token 使用监控从"每次手动查"升级为"有说明、有入口、可维护、可诊断"的工具资产。
- 在内网 Windows GBK 终端、多端 OpenCode 并存、Trae 自定义 base_url 连百炼等真实场景下也能拿到 exact token。

## 使用记录

| 日期 | 使用者 | 场景 | 效果 |
|------|--------|------|------|
|      |        |      |      |

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.1 | 2026-04-23 | opencode CLI 对话式一键装 (`scripts/install_to_opencode.py --print-prompt`)；Windows GBK 终端三级降级 + `_configure_stdio_utf8` 崩溃防线；第三方数据文件多编码兼容（UTF-8 / GBK / GB18030 fallback）；OpenCode v1.1.13 的 `{input, output, reasoning, cache: {read, write}}` 短键 schema 和 `{info, parts}` 嵌套 export 结构适配；`opencode-cli.exe` 与 GUI `opencode.exe` 二进制区分；cwd 乱码绕开。 |
| 1.0 | 2026-03-25 | 初始版本，覆盖 codex / claude-code / claude-desktop / opencode / minimax-agent / qwen-code-cli / kimi-cli / gemini-cli + chromium-desktop-family + provider-api-family + generic-openai-compatible |

## 使用契约

这个工具完全独立运行，不依赖任何特定 AI 客户端的私有配置目录：

- 不依赖 `~/.codex/skills/...` 或任何 skills 目录
- 不依赖某台机器上的全局提示词或临时记忆
- clone 仓库后，直接运行 Python 脚本即可使用

`SKILL.md` 是可选的自然语言接口描述文件，仅供有需要的用户集成到支持系统提示词的 AI 工具中。输出行为约定：

- 短查询（`token / 用量 / 消耗量 / 使用量`）默认先看今天总览
- 默认输出为 `ascii-hifi` 终端面板，附 1 到 3 句高信号结论
- 详细触发映射见 [skill-routing.md](./references/skill-routing.md)，输出协议见 [skill-output-contract.md](./references/skill-output-contract.md)

内网 / 跨平台兼容细则：

- 内网 Windows GBK 终端：[references/gbk-terminal.md](./references/gbk-terminal.md)
- 默认路径不命中时的真源探测：[references/path-discovery.md](./references/path-discovery.md)
- opencode 多端 / Trae 自定义 base_url 归因：[references/multi-endpoint-scenarios.md](./references/multi-endpoint-scenarios.md)
- 宿主不加载 skill 库时的手动 bootstrap：[references/intranet-bootstrap.md](./references/intranet-bootstrap.md)
- 完整环境变量表（自动生成自 `core/config.py`）：[./docs/ENV.md](./docs/ENV.md)
