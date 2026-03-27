# 安装说明

## 1. 前置条件

- `Python 3.11+`
- 一个可用的 Codex skills 目录，默认是 `~/.codex/skills`

## 2. 通过 GitHub 安装

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills"
git clone https://github.com/zsfd1997-glitch/token-usage-universal.git \
  "$CODEX_HOME/skills/token-usage-universal"
```

## 3. 首次自检

```bash
export TOKEN_USAGE_SKILL="$CODEX_HOME/skills/token-usage-universal"
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" health
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" sources
```

推荐判断方法：

- `ready`
  - 说明该来源已具备可用真源
- `not-found`
  - 说明来源逻辑支持，但当前路径或真源还没命中
- `detected-no-parser`
  - 说明有痕迹但当前 skill 还没实现解析器
- `not-configured`
  - 说明需要先做显式配置

## 4. 常见配置

### Codex 不在默认路径

```bash
export TOKEN_USAGE_CODEX_ROOT="$HOME/path/to/codex/sessions"
```

### Claude transcript 或 local-agent 路径不同

```bash
export TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT="$HOME/path/to/claude/transcripts"
export TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="$HOME/path/to/local-agent-mode-sessions"
```

### Generic exact logs

```bash
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/logs/*.jsonl,$HOME/logs/*.json"
```

## 5. 验证主命令

```bash
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" diagnose --source codex --today
```
