# VM Testing Scaffold

## 目标

给真实或模拟实机测试提供一个最小脚手架，重点服务：

- `Windows guest` 的 `Vagrant + Hyper-V`
- 共享目录中的仓库执行
- `release-gate --output-dir ...` 证据包导出

## 当前内容

- `Vagrantfile`
  - Windows Hyper-V 主线模板
  - VirtualBox fallback 模板
- `provision-windows.ps1`
  - guest 内安装 Python / Git 的占位脚本
- `collect-evidence.ps1`
  - 在 guest 内导出 release evidence bundle

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

## 注意

- 这个脚手架是 Windows guest PoC，不替代最终企业级编排。
- `macOS guest` 主线建议走 Tart；Tart runbook 见 [SIMULATED_MACHINE_TESTING.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/SIMULATED_MACHINE_TESTING.md)。
- 这里不内置 box 名称，因为不同团队的 Windows box 来源、license 和镜像策略通常不同。
