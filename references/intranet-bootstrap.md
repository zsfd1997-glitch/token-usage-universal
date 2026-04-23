# Intranet Bootstrap

面向**宿主没预装 skill 库**的场景：内网自建 opencode 桌面端、企业自研 CLI、私有分发的 Claude 客户端。这些宿主不会自动加载 `SKILL.md`，也不会自动探测仓库，`token-usage-universal` 必须靠人工引导完成首次接入。

## 判断是否需要走本文档

出现以下任一情况，按本流程走：

- 用户说"我这边 opencode / 内网 CLI 不支持 skill 目录"
- 用户说"找不到 SKILL.md 怎么用"
- 用户让跑 `scripts/token_usage.py` 时宿主说 `command not found` / `No such file`
- 用户的第一句是触发词（`token / 用量`），但对话上下文里没任何本工具痕迹

## Step 0：确认仓库已经落本机

先判断仓库是不是已经在本机上。常见落位：

- macOS/Linux: `~/token-usage-universal`、`~/Downloads/token-usage-universal`、`/opt/token-usage-universal`
- Windows: `%USERPROFILE%\token-usage-universal`、`D:\tools\token-usage-universal`

如果不确定，让用户跑：

```bash
# macOS/Linux
find ~ -maxdepth 4 -type d -name "token-usage-universal" 2>/dev/null
# Windows PowerShell
Get-ChildItem -Path $HOME -Recurse -Depth 4 -Directory -Filter "token-usage-universal" -ErrorAction SilentlyContinue
```

如果还没落本机：

1. 优先 clone：`git clone https://github.com/zsfd1997-glitch/token-usage-universal.git`
2. 内网无 GitHub 访问权限时，改用 `dist/` 里的 zip 包：`token-usage-universal-windows.zip`（Windows 桌面端）或让用户从发布渠道拿最新归档
3. Python 要求 3.8+，无额外三方依赖

## Step 1：用绝对路径跑自检

宿主的 PATH / shell alias 可能都不可靠，**所有首次命令都用绝对路径**：

```bash
# macOS/Linux
python3 /abs/path/to/token-usage-universal/scripts/token_usage.py health

# Windows PowerShell
python "C:\abs\path\to\token-usage-universal\scripts\token_usage.py" health
```

自检看三件事：

- 脚本能跑起来（没有 `No module named` / 语法错）
- `health` 输出是 ascii-hifi 面板，不是乱码
- 至少有一条来源标 `ready`（没有也别慌，接 `path-discovery.md` 找真源）

## Step 1.5：冷启动"复制粘贴"提示词（宿主完全不认 skill 库时）

如果宿主既不加载 `SKILL.md` 也不接受自定义 system prompt（纯对话壳），用一条命令自动生成填好绝对路径的冷启动提示词：

```bash
python3 /abs/path/to/token-usage-universal/scripts/token_usage.py bootstrap-prompt
```

把输出整段作为**当轮对话的第一条消息**贴进去，Claude 读到就会按本 skill 的契约工作——**不依赖任何 skill 库**。

如果连这条命令都跑不了（比如用户还没拉到仓库），手动贴下面这段也可以：

```
你现在要扮演 token-usage-universal 这个本地工具的翻译层。
工具入口：python3 <绝对路径>/scripts/token_usage.py
规则：
- 触发词：token / 用量 / 消耗量 / 使用量 / 消耗。用户说这五个词之一，默认跑 `report --today`。
- 按模型/项目/来源拆：加 `--by model|project|source`。
- 趋势：`report --trend 7d` 或 `--trend 30d`。
- 当前会话：`report --current-session`。
- 排障：`diagnose --source <source_id> --today`。
- 来源状态：`sources` 或 `health`。
输出协议：
- CLI 返回的 ascii-hifi 面板必须原样放进 fenced code block，再补 1-3 句高信号结论，末句给可选展开方向。
- 结果为 0 必须解释"为什么是 0"，不允许空白成功。
- 总 token 和去缓存后 token 要分开说，不允许只给裸数字。
终端编码：
- 如果中文渲染成乱码或 `chcp` 返回 936，先让用户 `chcp 65001`（Windows）或 `export LANG=en_US.UTF-8`，或设 `PYTHONIOENCODING=gbk:backslashreplace`；实在不行改跑 `--format json` 再由我自己重绘英文面板。
禁忌：
- 不拆桌面/CLI/插件为多条 source；它们共享同一条 `opencode` source。
- 不在默认路径 not_found 时直接断言"没用量"；先路径探测。
- 不中英混排输出到 GBK 终端。
用户停手（"先这样/够了/不用继续/先停"）立刻收口，不追问。
```

把 `<绝对路径>` 替换成真实仓库位置即可。这段约 450 字，大多数宿主的首条消息长度都容得下。

## Step 2：把 SKILL.md 塞进宿主

宿主接受 skill / 系统提示词注入的程度不一样，按递减优先级试：

1. **宿主有「自定义 instructions / system prompt」字段**（Cursor、Continue、Claude Desktop 的 Custom Instructions）
   - 把 `SKILL.md` 全文贴进去，保存
   - 验证：新开一轮对话，输入 `token` 或 `用量`，模型应该先跑 `health` 再跑 `report --today`

2. **宿主有「skills 目录 / 插件目录」但不自动扫描**
   - 手动把整个 `token-usage-universal/` 目录软链或复制到宿主指定位置（常见：`~/.opencode/skills/`、`~/.<host>/skills/`）
   - 重启宿主
   - 如果还是不认，回到方案 1

3. **宿主完全不支持系统提示词**（纯对话壳，比如某些内网 launcher）
   - 每次新对话时，把 SKILL.md 的「核心提示词」「执行协议」两段作为**用户的第一条消息**贴进去
   - 再发真正的问题（如"token 用量"）
   - 提示词会在该对话内持续生效，但换对话要重贴

4. **完全无法注入**
   - 跳过 skill 层，退化成「人肉调度」：让用户直接说"跑 `report --today`"，skill 侧只负责把命令结果按输出协议贴回去

## Step 3：确认 skill 真正生效

接入完成后，跑一遍冒烟：

- 用户输入：`token`（短触发词）
- 期望表现：模型先 `health`（如果来源状态未知）再 `report --today`，输出是 fenced code block 里的 ascii-hifi 面板，附 1-3 句高信号结论，末尾一句可选展开方向
- 反例：模型回一句"请问您想看什么维度的 token 用量"→ skill 没生效，重做 Step 2

## 常见踩坑

- **Python 版本**：宿主自带 Python 2 会直接报语法错，确认 `python3 --version` ≥ 3.8
- **虚拟机/容器**：skill 文件在宿主机，但 CLI 要在容器里跑 → 把仓库挂进容器，再在容器内走 Step 1
- **Windows 路径有空格**：全部用双引号包裹，不要裸路径
- **权限**：企业机如果 `~/.codex` / `~/.claude` 是只读挂载，`health` 会报 permission error，需要用 `TOKEN_USAGE_*_ROOT` 指向用户可写目录
- **宿主截断**：部分内网宿主对单条系统提示词有长度限制（常见 4k/8k），SKILL.md 超限时优先保留「核心提示词」+「执行协议」+「禁忌」三段，路由/契约/精度可以删
