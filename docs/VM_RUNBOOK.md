# VM Runbook

## 目标

把 `token-usage-universal` 的“模拟实机测试”变成可执行 runbook，覆盖：

- `Windows guest`
- `macOS guest`
- 证据包导出
- host 回收与归档

核心统一命令：

```bash
python3 scripts/token_usage.py release-gate \
  --format json \
  --output-dir <evidence-dir>
```

## 成功标准

- guest 内能执行 `release-gate`
- evidence bundle 能落盘
- host 侧能回收到：
  - `release_gate.json`
  - `health.json`
  - `sources.json`
  - `targets.json`
  - `report_today.json`
  - `report_recent_30d.json`
  - `diagnose/*.json`
  - `SUMMARY.md`

## 方案总览

### 无 host 环境

- 主线：`GitHub-hosted runners`
- workflow：
  - [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)
  - [run-hostless-evidence.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/run-hostless-evidence.sh)
- 适合场景：
  - 本地没有 `Windows/macOS` host
  - 先拿平台级 `health / targets / release-gate / diagnose` 证据
  - 先验证 workflow、artifact 和双平台 runner 路径

### Windows guest

- 主线：`Vagrant + Hyper-V`
- fallback：`Vagrant + VirtualBox`
- 仓库脚手架：
  - [examples/vm-testing/Vagrantfile](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/Vagrantfile)
  - [examples/vm-testing/provision-windows.ps1](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/provision-windows.ps1)
  - [examples/vm-testing/collect-evidence.ps1](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/collect-evidence.ps1)

### macOS guest

- 主线：`Tart`
- 仓库脚手架：
  - [examples/vm-testing/tart-run-macos.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/tart-run-macos.sh)
  - [examples/vm-testing/collect-evidence-macos.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/collect-evidence-macos.sh)

## Windows Runbook

### 1. host 准备

```bash
cd examples/vm-testing
vagrant up --provider=hyperv
```

可选环境变量：

```bash
export TOKEN_USAGE_VAGRANT_BOX="your-windows-box"
export TOKEN_USAGE_VAGRANT_PROVIDER="hyperv"
```

### 2. guest 执行

仓库默认挂载到：

- `C:\workspace\token-usage-universal`

证据输出目录默认挂到：

- `C:\workspace-output`

执行：

```powershell
powershell -ExecutionPolicy Bypass -File C:\workspace\token-usage-universal\examples\vm-testing\collect-evidence.ps1
```

### 3. host 回收

host 侧证据目录：

- `examples/vm-testing/output/windows-evidence`

### 4. 故障排查

- `python` 不存在：
  - 先在 guest 安装 Python 3.11+
- `Repo root not found`：
  - 检查共享目录是否挂到 `C:\workspace\token-usage-universal`
- `release-gate` 成功但来源都是 `not-found`：
  - 这是“当前 guest 没真实客户端或真实 fixture”的信号，不是脚手架失败

## GitHub-hosted Runner Runbook

### 1. 适用前提

- 没有本地 `Windows/macOS` host
- 仓库在 GitHub 上
- 可以使用 GitHub Actions 托管 runner

### 2. 触发方式

在 GitHub Actions 页面手动触发：

- workflow: `hostless-evidence`
- 可选输入：
  - `artifact-prefix`

或者直接在本地仓库运行：

```bash
cd examples/vm-testing
./run-hostless-evidence.sh
```

### 3. workflow 行为

workflow 会在：

- `windows-latest`
- `macos-latest`

上执行：

1. checkout 仓库
2. setup Python 3.11
3. 跑全量单测
4. 执行：

```bash
python scripts/token_usage.py release-gate --format json --output-dir <runner temp>
```

5. 上传 artifact

### 4. 预期产物

每个平台会产出一个 artifact：

- `<artifact-prefix>-windows`
- `<artifact-prefix>-macos`

artifact 内包含：

- `release_gate.json`
- `health.json`
- `sources.json`
- `targets.json`
- `report_today.json`
- `report_recent_30d.json`
- `diagnose/*.json`
- `SUMMARY.md`

本地脚本默认把 artifact 下载到：

- `examples/vm-testing/output/github-hosted`

### 5. 适用边界

- 这条路线能解决“没有 host 环境”的问题
- 它现在已经有一条可执行脚本入口，而不只是文档说明
- 但它仍然更适合：
  - 平台级 smoke / evidence 采集
  - runner 默认目录与默认环境验证
- 它不等于：
  - 已安装真实桌面客户端
  - 已拿到真实用户级 app-data 命中

## macOS Runbook

### 1. host 前提

- Apple Silicon
- 已安装 `tart`
- 已有可启动的 macOS VM 镜像

建议通过环境变量传入镜像名：

```bash
export TOKEN_USAGE_TART_VM="ghcr.io/cirruslabs/macos-sonoma-base:latest"
```

### 2. host 执行

```bash
cd examples/vm-testing
./tart-run-macos.sh
```

默认行为：

- 克隆/运行 Tart VM
- 把仓库路径传给 guest
- 在 guest 内执行 `collect-evidence-macos.sh`

### 3. guest 执行逻辑

guest 内脚本会在仓库根目录执行：

```bash
python3 scripts/token_usage.py release-gate \
  --format json \
  --output-dir /tmp/token-usage-universal-evidence
```

### 4. host 回收

默认 host 侧回收目录：

- `examples/vm-testing/output/macos-evidence`

### 5. 故障排查

- `tart` 不存在：
  - 先在 host 安装 Tart
- VM 名称无效：
  - 检查 `TOKEN_USAGE_TART_VM`
- guest 内找不到仓库：
  - 检查共享目录/复制步骤是否完成

## 证据归档建议

建议每次运行后按平台和日期归档：

```text
evidence/
  windows/
    2026-04-07/
  macos/
    2026-04-07/
```

至少保留：

- `SUMMARY.md`
- `release_gate.json`
- 关键 `diagnose/*.json`

## 回滚

- Windows:
  - `vagrant halt`
  - `vagrant destroy -f`
- macOS:
  - 关闭 Tart VM
  - 删除临时 clone

## 下一步

runbook 就绪后，下一步只剩两类真实动作：

1. 在 `Windows guest` 里放入真实桌面客户端或 fixture
2. 在 `macOS guest` 里放入真实桌面客户端或 fixture

只要任一侧拿到真实 `app-data` 命中证据，这条模拟实机路线就从“脚手架阶段”进入“验收阶段”。
