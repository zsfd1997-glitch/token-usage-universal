# VM Testing Scaffold

## 目标

给真实或模拟实机测试提供一个最小脚手架，重点服务：

- `Windows guest` 的 `Vagrant + Hyper-V`
- `macOS guest` 的 `Tart`
- 共享目录或 guest copy 中的仓库执行
- `release-gate --output-dir ...` 证据包导出

## 当前内容

- `Vagrantfile`
  - Windows Hyper-V 主线模板
  - VirtualBox fallback 模板
- `provision-windows.ps1`
  - guest 内安装 Python / Git 的占位脚本
- `collect-evidence.ps1`
  - 在 guest 内导出 release evidence bundle
- `tart-run-macos.sh`
  - 启动 Tart macOS VM、复制仓库、执行证据导出并回收
- `collect-evidence-macos.sh`
  - 在 macOS guest 内导出 release evidence bundle
- `run-hostless-evidence.sh`
  - 触发 GitHub-hosted runners，等待 workflow 完成并下载 artifact

## 使用方式

### 1. host 侧

```bash
cd examples/vm-testing
vagrant up --provider=hyperv
```

### 2. guest 侧

仓库会被挂到：

- `C:\workspace\token-usage-universal`

进入 guest 后执行：

```powershell
powershell -ExecutionPolicy Bypass -File C:\workspace\token-usage-universal\examples\vm-testing\collect-evidence.ps1
```

### 3. host 取证据

证据会落到：

- `examples/vm-testing/output/windows-evidence`

其中核心产物包括：

- `release_gate.json`
- `health.json`
- `sources.json`
- `targets.json`
- `report_today.json`
- `report_recent_30d.json`
- `diagnose\*.json`
- `SUMMARY.md`

## macOS / Tart

### 1. host 侧

```bash
cd examples/vm-testing
export TOKEN_USAGE_TART_VM="your-macos-tart-image"
./tart-run-macos.sh
```

### 2. host 取证据

证据会落到：

- `examples/vm-testing/output/macos-evidence`

## 无 host / GitHub-hosted runners

### 1. 前提

- 当前分支已经 push 到 GitHub
- `gh auth status` 已登录
- 仓库里已经包含 [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)

### 2. 执行

```bash
cd examples/vm-testing
./run-hostless-evidence.sh --platform all
```

只跑单个平台时：

```bash
./run-hostless-evidence.sh --platform ubuntu
./run-hostless-evidence.sh --platform macos
./run-hostless-evidence.sh --platform windows
```

可选环境变量：

```bash
export TOKEN_USAGE_ARTIFACT_PREFIX="hosted-evidence"
export TOKEN_USAGE_HOSTLESS_OUTPUT_DIR="$PWD/output/github-hosted"
export TOKEN_USAGE_HOSTLESS_BRANCH="main"
export TOKEN_USAGE_HOSTLESS_PLATFORM="ubuntu"
```

### 3. 下载结果

artifact 默认会落到：

- `examples/vm-testing/output/github-hosted`

## 注意

- 这套脚手架是 PoC，不替代最终企业级编排。
- 统一 runbook 见 [VM_RUNBOOK.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/VM_RUNBOOK.md)。
- 模拟实机方案总览见 [SIMULATED_MACHINE_TESTING.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/SIMULATED_MACHINE_TESTING.md)。
- 这里不内置 box 名称，因为不同团队的 Windows box 来源、license 和镜像策略通常不同。
- 这里也不内置 Tart 镜像名，因为不同团队的 macOS guest 来源和镜像策略通常不同。
- `run-hostless-evidence.sh` 不会替您自动 push 分支；这是故意的，避免替您做外发动作。
