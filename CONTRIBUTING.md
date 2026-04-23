<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->

# Contributing

欢迎补充新来源、修正路径兼容性，或改进输出与文档。

## 贡献原则

- 保持 `local-first`
- 保持 `exact-first`
- 保持 `source-first`
- 不要引入默认联网统计
- 不要引入 transcript / tokenizer 猜数作为默认结果

## 开发流程

1. 在本地修改代码或文档
2. 运行基础验证：

```bash
python3 -m unittest discover -s scripts -t . -p 'test_*.py'
python3 scripts/token_usage.py --help
python3 scripts/token_usage.py health --format json
```

3. 如果新增来源：

- 在 `scripts/adapters/` 下新增 adapter
- 保持 `SourceDetection` / `UsageEvent` 契约一致
- 为缺失真源场景提供明确诊断
- 增加对应测试

## 提交建议

- 文档改动与代码改动尽量分开提交
- 如果影响用户入口，请同步更新 `README.md` 与 `SKILL.md`
- 如果影响 GitHub 分发体验，请同步检查 `CODE_OF_CONDUCT.md / SECURITY.md / SUPPORT.md / .github/*template*`
- 如果影响公开发布目录，请重新运行：

```bash
python3 scripts/build_release.py --output-dir /tmp/token-usage-universal --force
```
