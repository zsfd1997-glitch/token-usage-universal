# Changelog

## 0.2.0 - 2026-03-30

- 默认 `report --today` 已升级成终端控制面，默认包含总览、当前会话、按模型、按项目、最近趋势和月历热力图
- 默认主口径切到 `去缓存后 token`，明确区分 `总 token / 去缓存后 token`，默认费用也按去缓存后 token 估算
- `explore` 交互入口已收敛成更直白的短选项：`今天总览 / 最近一周 / 最近一个月 / 按模型 / 按项目 / 当前会话 / 关闭`
- 新增本地价格库与 `estimated cost` 输出，并把最近趋势 / 本月分布右侧摘要统一成 `合计 + 估算费用 / 均值 / 最高`
- 新增文件级增量缓存、按天预聚合索引、Codex 按日期目录扫描与价格库单例复用，`today / 7d / 30d / 月历` 常见视图显著加快
- `claude-code` 已升级成多版本 exact JSON 识别，并能区分 transcript-only、新版 session-config 布局和真正缺失 token-bearing JSON 的情况
- 已补上 Windows 路径兼容与环境变量占位展开，Claude macOS / Windows 默认真源路径和诊断矩阵已同步
- 测试扩展到 `66` 个，覆盖聚合、价格库、图形 renderer、CLI 集成、缓存 / 快路径、Windows 兼容和 Claude 多布局诊断

## 0.1.0 - 2026-03-26

- 发布 `token-usage-universal` 公开 skill 首版
- 提供 `report / sources / diagnose / health` 四个主入口
- 支持 `codex` exact、`claude-code` total-only exact、`generic-openai-compatible` exact when configured
- 增加统一 env override、自检命令、GitHub-ready 发布骨架与导出脚本
