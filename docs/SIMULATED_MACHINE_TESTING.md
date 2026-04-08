# Simulated Machine Testing

## 目标

给 `token-usage-universal` 建一条“模拟实机测试”路线，用来补齐当前还缺的：

- `Windows + macOS` 双平台真机证据
- `claude-desktop / minimax-agent` 等桌面来源的真实 app-data 命中
- 大样本重复计数率实测

前提是：我们已经有了 `release-gate --output-dir ...`，现在缺的是“在哪些虚机/模拟实机工具里跑、怎么跑最划算”。

## 项目场景与关键假设

- 核心验证对象不是浏览器页面，而是 `Desktop + CLI + IDE` 的本地真源目录、日志、缓存和 session artifacts。
- 需要模拟“真实 OS 用户环境”，包括：
  - app-data 目录
  - Electron / Chromium 缓存
  - 本地 CLI runtime 根目录
  - 共享文件夹与证据包导出
- 需要同时覆盖：
  - `macOS guest` 验证链路
  - `Windows guest` 验证链路
  - 尽量自动化，但允许手动调试工具作为辅助手段

## Awesome 检索摘要

- Awesome 列表：
  - `awesome-virtualization`
  - https://github.com/Wenzel/awesome-virtualization
- 检索范围：
  - Apple Silicon 上的 macOS VM 自动化
  - Windows/macOS 本地 VM 管理
  - provider/provisioning 工具
  - CI/automation 友好型 VM 方案
- 官方资料范围：
  - Tart / Cirrus Labs
  - Vagrant / HashiCorp
  - UTM
  - Orka / MacStadium
  - VirtualBox / Oracle

## 参考清单

| 类型 | 名称/链接 | 为什么相关 | 主要风险 | 结论 |
|---|---|---|---|---|
| Awesome 列表 | `awesome-virtualization` https://github.com/Wenzel/awesome-virtualization | 作为 virtualization 领域的 curated list，覆盖主流 hypervisor 文档与研究入口 | 更偏底层与广谱，不是专门为桌面验收设计 | 继续跟进 |
| 候选工具 | Tart https://github.com/cirruslabs/tart | 明确面向 Apple Silicon 上的 `macOS / Linux VM`，强调 `CI and other automations`，适合 macOS 证据链自动化 | 只能跑在 Apple Silicon + macOS 13+ 主机上，不能替代 Windows host 路线 | 推荐 |
| 候选工具 | Vagrant https://developer.hashicorp.com/vagrant/docs/providers/hyperv | 适合作为“provisioning 与环境定义层”，官方支持 Hyper-V provider，适合 Windows guest 的可复现环境 | 不自带 hypervisor，本身只是编排层；不同 provider 的体验差异大 | 推荐 |
| 候选工具 | UTM https://docs.getutm.app/ | Mac 上很好用的 GUI VM/模拟器，支持 Windows/Linux/macOS，适合本地手动调试和复盘 | 更偏手工调试，不是最强的 CI 自动化主线 | 备选 |
| 候选工具 | Orka https://docs.macstadium.com/ | 明确面向 Apple Silicon 上的 macOS virtualization，可做集群和 CI/CD | 商业化、成本高，更适合企业级 Mac 集群 | 需二次评估 |
| 候选工具 | VirtualBox https://docs.oracle.com/en/virtualization/virtualbox/ | 跨平台覆盖广，适合 Vagrant 的低门槛 fallback provider | 对 Apple Silicon / 新版 macOS 主线并不占优，桌面端细节和性能通常不如原生方案 | 备选 |

## 对比结论

### 1. macOS 主线

优先选 `Tart`。

原因：

- 它就是为 Apple Silicon 上的 `macOS / Linux VM` 自动化场景做的。
- 官方 README 直接强调：
  - `macOS and Linux VMs on Apple Silicon`
  - `use in CI and other automations`
  - 支持 OCI registry 推/拉 VM 镜像
  - 支持 Packer plugin 自动制镜像
- 对我们最重要的是：后续可以直接把 `release-gate --output-dir ...` 放进 VM 启动后脚本，稳定地产出证据包。

不优先选 `UTM / VirtualBox` 的原因：

- `UTM` 更适合手动调试和临时复盘，不是最优的自动化主线。
- `VirtualBox` 的跨平台价值高，但在 Apple Silicon 上做 macOS 主线不如 Tart 贴题。

### 2. Windows 主线

优先选 `Vagrant + Hyper-V`。

原因：

- Vagrant 官方文档明确支持 Hyper-V provider，且说明适用于 Windows 8.1+。
- 对我们来说，Vagrant 的价值不是 hypervisor，而是：
  - 把虚机规格、共享目录、启动脚本、证据导出过程写成配置
  - 让 Windows 验收步骤能被反复复现
- Hyper-V 是 Windows 原生 hypervisor，和“模拟真实 Windows 用户环境”的目标更一致。

不把 `Vagrant` 单独当最终方案的原因：

- 它只是编排层，不是虚拟化本体。
- 真正的技术组合应该写成：`Vagrant + Hyper-V` 主线，`Vagrant + VirtualBox` 作为 fallback。

### 3. 手动复盘 / 调试

优先选 `UTM`。

原因：

- UTM 文档明确支持 macOS 上跑 Windows/Linux/macOS guest。
- 对排查 `app-data` 目录、共享文件夹、磁盘快照、手工 GUI 操作很友好。
- 当我们需要“看一下桌面客户端到底把缓存落哪儿了”时，UTM 的成本比搭完整 CI 更低。

### 4. 企业级扩展

企业化路线优先看 `Orka`。

原因：

- 文档明确写了 `macOS virtualization on Apple Silicon` 和 `integrate with your CI/CD pipeline`。
- 如果后面需要把 macOS 验收扩到团队规模、并发跑多台 Mac VM，这类工具更合适。

不立刻上主线的原因：

- 现在仓库的瓶颈不是“缺企业级调度器”，而是“缺第一条稳定、可复现、成本可控的真机模拟链路”。

## 推荐决策

推荐主方案：

- `无 host`: `GitHub-hosted runners`
- `macOS`: `Tart`
- `Windows`: `Vagrant + Hyper-V`
- `手动调试`: `UTM`

备选方案：

- `Windows fallback`: `Vagrant + VirtualBox`
- `企业级 macOS 扩容`: `Orka`

不推荐现在直接做的事：

- 不要试图用一个工具同时优雅覆盖 `macOS guest 自动化 + Windows guest 自动化 + CI 大规模并发`
- 不要把 `UTM` 当成主自动化引擎
- 不要在没有证据包导出链路的前提下先堆 VM 编排

## 与当前仓库的结合方式

当前仓库已经具备关键落点：

```bash
python3 scripts/token_usage.py release-gate \
  --format json \
  --output-dir /tmp/token-usage-universal-evidence
```

因此 VM 工具只需要完成三件事：

1. 启动 guest OS
2. 把待测客户端或 fixture 放进去
3. 执行上面的命令并把 `/tmp/token-usage-universal-evidence` 导出回 host

也就是说，工具选型要优先考虑：

- 共享目录能力
- 快照/回滚
- 启动后脚本
- 对 Apple Silicon / Windows 原生 hypervisor 的适配

## 建议落地动作

### 1. 一周内 PoC 顺序

1. `Tart` 跑通一个最小 macOS VM，执行 `release-gate --output-dir ...`
2. `Vagrant + Hyper-V` 跑通一个最小 Windows VM，执行同一条命令
3. 用 `UTM` 手工复盘一条桌面端 app-data 命中链路

### 2. 本仓库下一步建议

- 新增 `docs/VM_RUNBOOK.md`：
  - host 侧准备
  - guest 侧执行
  - 证据包导出
- 再新增 `examples/vm-testing/`：
  - `Vagrantfile`
  - guest 启动脚本
  - evidence 拉取脚本

当前仓库已先落了最小脚手架：

- [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)
- [run-hostless-evidence.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/run-hostless-evidence.sh)
- [examples/vm-testing/README.md](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/README.md)
- [examples/vm-testing/Vagrantfile](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/Vagrantfile)
- [examples/vm-testing/provision-windows.ps1](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/provision-windows.ps1)
- [examples/vm-testing/collect-evidence.ps1](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/collect-evidence.ps1)
- [examples/vm-testing/tart-run-macos.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/tart-run-macos.sh)
- [examples/vm-testing/collect-evidence-macos.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/collect-evidence-macos.sh)
- [VM_RUNBOOK.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/VM_RUNBOOK.md)

### 3. 退出条件

只有满足下面三点，才算“模拟实机测试链路完成”：

- macOS VM 能稳定导出证据包
- Windows VM 能稳定导出证据包
- 至少一条桌面来源在 VM 中拿到真实 `app-data` 命中证据

## 官方来源

- Awesome Virtualization
  - https://github.com/Wenzel/awesome-virtualization
- Tart
  - https://github.com/cirruslabs/tart
- Vagrant Hyper-V Provider
  - https://developer.hashicorp.com/vagrant/docs/providers/hyperv
- UTM
  - https://docs.getutm.app/
- Orka / MacStadium
  - https://docs.macstadium.com/
- Oracle VirtualBox
  - https://docs.oracle.com/en/virtualization/virtualbox/
