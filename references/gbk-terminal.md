<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->

# GBK Terminal

面向**终端只认 GBK、不认 UTF-8** 的场景。内网 Windows cmd / PowerShell 老主机、部分国产 Linux 终端默认 locale 仍是 `zh_CN.GBK`，直接渲染 UTF-8 的 ascii-hifi 面板会出现乱码（常见表现：中文变成 `鍘熷緥` / `鎸変緥` / `?` 这类）。

本文档给三级降级方案。

## Step 0：判断终端编码

让用户先确认，不要凭感觉：

```bash
# Windows cmd / PowerShell：看当前 codepage
chcp
# 936 = GBK，65001 = UTF-8

# Linux / macOS：看 locale
locale
# LANG=zh_CN.UTF-8 → UTF-8；LANG=zh_CN.GBK / zh_CN.GB18030 → GBK/GB18030
```

再看实际显示效果：让用户在终端里跑一次 `python3 scripts/token_usage.py health`，直接观察中文字段（例如"来源 / 模型 / 项目"）是不是人类可读。

## Tier 1：把终端切成 UTF-8（**推荐，成本最低**）

如果用户有权改终端配置，这是最干净的方案，tool 本身无需改。

### Windows

```powershell
# 临时（仅当前会话有效）
chcp 65001
python scripts\token_usage.py report --today

# 永久：改 PowerShell profile
notepad $PROFILE
# 在 profile 里加一行：
# [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# cmd 永久：在系统环境变量里加 PYTHONUTF8=1
```

**注意**：Windows 传统 cmd 下 `chcp 65001` 后，某些老字体（比如默认的「点阵字体」）仍然无法显示 CJK。让用户把字体改成 `Consolas` / `Cascadia Code` / `微软雅黑` / `NSimSun`。

### Linux / macOS

```bash
# 临时
export LANG=en_US.UTF-8   # 或 zh_CN.UTF-8
python3 scripts/token_usage.py report --today

# 永久：写进 ~/.bashrc / ~/.zshrc
echo 'export LANG=en_US.UTF-8' >> ~/.bashrc
```

### 验证

跑 `python3 scripts/token_usage.py health`，看中文字段是不是正常中文。是就停在 Tier 1，不用往下。

## Tier 2：走 JSON 通道，skill 端重绘（**无权改终端时首选**）

如果用户没权限改终端 codepage / locale（常见企业策略），让 CLI 输出 JSON：

```bash
python3 scripts/token_usage.py report --today --format json
python3 scripts/token_usage.py health --format json
python3 scripts/token_usage.py diagnose --source claude-code --today --format json
```

Python 的 `json.dumps` 默认 `ensure_ascii=True`，中文字符全部输出成 `\uXXXX` 转义序列，是**纯 ASCII**，任何终端都能原样显示。

然后 skill 端（模型）**自己把 JSON 重绘成 ascii-hifi 面板**——但这时候面板内容不要放 CJK 字符，全部转英文标签（见 Tier 3 的标签映射）。最终贴给用户的面板是纯 ASCII，GBK 终端完美显示。

这条路的代价：skill 端要多做一次渲染，但稳。

## Tier 3：纯 ASCII + 英文标签（**最后手段**）

当 Tier 1 不能改、Tier 2 的 JSON 在宿主那边被截断或不方便转义时，强制让 CLI 输出图形层纯 ASCII，skill 端把中文标签也换英文：

```bash
python3 scripts/token_usage.py report --today --plain-ascii
```

**注意**：当前 `--plain-ascii` 只替换图表字符（bar / sparkline / heatmap），面板**标题和标签仍包含中文**。这些中文在 GBK 终端下还是乱码。所以 Tier 3 必须配合 skill 端手动替换标签，最终只贴 ASCII。

### 中文 → 英文标签映射

| 中文 | 英文 |
|---|---|
| 总 token | Total tokens |
| 去缓存后 token | Net tokens (cache-excluded) |
| 当前会话 | Current session |
| 按来源 | By source |
| 按模型 | By model |
| 按项目 | By project |
| 按会话 | By session |
| 按天 | By day |
| 最近趋势 | Recent trend |
| 月历热力图 | Monthly heatmap |
| 来源 | Source |
| 模型 | Model |
| 项目 | Project |
| 日期 | Date |
| 估算费用 | Estimated cost |

## 决策树

```
用户终端是 UTF-8?
├── 是 → 直接走默认 ascii-hifi 面板
└── 否（GBK / cp936 / zh_CN.GBK）
    ├── 用户能改终端 codepage / locale?
    │   ├── 是 → Tier 1（chcp 65001 / export LANG=...UTF-8）
    │   └── 否
    │       ├── 用户能改环境变量 (PYTHONIOENCODING)?
    │       │   ├── 是 → Tier 1.5（PYTHONIOENCODING=gbk:backslashreplace）
    │       │   └── 否
    │       │       ├── 宿主能正确透传 JSON?
    │       │       │   ├── 是 → Tier 2（--format json + skill 端英文重绘）
    │       │       │   └── 否 → Tier 3（--plain-ascii + 全英文标签）
```

Tier 1.5 是新增的优先选项：比 Tier 1 权限要求低（改 env 不改系统 codepage），比 Tier 2 不用 skill 端重绘，适合大多数企业桌面场景。

## 崩溃保证（不是乱码的问题，是会不会炸）

CLI 在任何终端编码下都**必须**不崩。当前 [scripts/token_usage.py](../scripts/token_usage.py) 的三层防线：

1. **`errors="backslashreplace"`**：stdout/stderr 的 encoder 出错不 raise，把不能编码的字符退化成 `\uXXXX` 转义。这意味着哪怕跑在残缺 codec 上，`print()` 也不会 `UnicodeEncodeError` 中断面板渲染。
2. **尊重 `PYTHONIOENCODING`**：用户设了 `PYTHONIOENCODING=gbk` 时，CLI 不再强制覆盖回 UTF-8；Python 会按 GBK 编码 stdout。配合 Tier 1.5 用。
3. **stdout JSON 自动 `ensure_ascii=True`**：`--format json` 输出时，如果 stdout 不是 UTF-8，所有 JSON 字符串自动转成 `\uXXXX` 纯 ASCII 字节。这保证 skill / 测试 / 任何下游解析器无论按什么编码读 stdout，都能成功 `json.loads`。

所以在 GBK 终端里，**最坏的情况是乱码，不会是崩溃**。

## 文件侧编码兼容（读不进去也算"乱码很严重"）

输出到终端只是乱码的一半；另一半是**读取第三方客户端写出的数据文件**时遇到的编码问题。

### 真实踩坑：opencode CLI 读不出 token 消耗量

**症状**：内网 Windows 机上 `report --today` 全部 0 token，`health` 却说 opencode ready。

**根因**：老版本的 `_read_json_file` 只认 `encoding="utf-8"`，遇到 `UnicodeDecodeError` 就静默返回 None。如果 OpenCode 在 GBK / cp936 系统默认编码下写文件（某些老版本、或用户手动编辑过 JSON 文件），所有消息文件会被当成"文件不存在"跳过，token 事件归零——而 adapter 既不报错也不诊断，用户完全看不出哪里出了问题。

**已修**：[scripts/core/robust_read.py](../scripts/core/robust_read.py) 提供 `read_text_robust` / `read_json_robust`，按 `utf-8-sig → utf-8 → gbk → gb18030` 顺序尝试解码，全部失败后还会走 `errors="replace"` 兜底，保证 token 数字字段能穿透解码损坏。所有第三方数据读取的 adapter（opencode / claude-code / kimi-cli / gemini-cli）都换用了这个函数。

### 诊断信号

OpenCode adapter 如果靠 fallback 才读通文件，会在 `verification_issues` 里留一条：

> `N OpenCode message file(s) were decoded using a legacy codec (GBK/GB18030) — OpenCode likely wrote under a non-UTF-8 system codepage; set PYTHONIOENCODING=gbk or switch the host locale to UTF-8 to make this stable`

跑 `python3 scripts/token_usage.py diagnose --source opencode --today` 能直接看到。出现这条说明机器现在数字是对的，但源头（OpenCode 自己写文件的方式）不规范，长期应该让用户把系统 locale 切到 UTF-8 或升级 OpenCode。

### 非 GBK 的其他编码（Big5 / Shift-JIS / EUC-KR）

默认 fallback 列表**只含**UTF-8 / GBK / GB18030。原因：GBK / GB18030 的字节范围几乎能吞下任何 2-byte 序列而不报错，如果盲加 Big5 会出现"Big5 文件被当成 GBK 读出垃圾"的误匹配。

确实需要繁中/日韩解码的场景，直接在 adapter 里调：

```python
from core.robust_read import read_json_robust
payload, enc = read_json_robust(path, encodings=("big5",))
```

或把需求提交给维护方扩展默认列表。

## Tier 1.5：设 `PYTHONIOENCODING=gbk`（推荐，改好后一次到位）

由于 CLI 现在尊重这个 env，这条路是成本最低的稳妥方案：

```powershell
# Windows PowerShell
$env:PYTHONIOENCODING = "gbk:backslashreplace"
python .\scripts\token_usage.py report --today
```

```bash
# Linux / macOS 如果真的在 GBK locale 里
export PYTHONIOENCODING=gbk:backslashreplace
python3 scripts/token_usage.py report --today
```

`:backslashreplace` 后缀显式声明错误处理策略——即使 CLI 的防线失效，也由这里兜底。Python 会把中文编码成 GBK 原生字节，GBK 终端渲染正确；非 GBK 罕见字符变成 `\uXXXX` 转义，依旧可读不崩。

## 已知限制 / 后续 CLI TODO

- 当前 `--plain-ascii` 只替换图表字符，面板标签仍是中文；GBK 终端下如果走 Tier 3，仍需 skill 端手动替英文
- 未来可以加的：
  - `--lang=en` 选项：CLI 直接输出英文标签，skill 端不用重绘
  - 乱码自检：`health` 里加一行 "terminal encoding=? , suggested="

## 常见踩坑

- **Windows Terminal / ConEmu / Cmder 默认就是 UTF-8**，只有传统 cmd.exe / PowerShell 5.x 有这个问题，优先让用户换终端
- `chcp 65001` 在某些 .bat 脚本里会把管道打断，如果脚本不是交互运行，优先走 Tier 2 JSON
- SSH 远程到内网机时，**客户端终端**也要是 UTF-8，否则远端 UTF-8 字节过 SSH 管道到本地 GBK 终端一样乱码
- 一旦降到 Tier 3，就**不要**再把 CJK 字符混进最终输出——"中英混排"的面板在 GBK 终端里只有英文部分正常，中文部分仍然乱码，体验比纯英文更差
