# Top20 Surface Matrix

说明：

- `exact-ready`：已有 exact 解析实现和代码路径
- `detect-ready`：已有 source/root/detect 骨架，但 exact 还需要更多真实 fixture 或 provider-specific 强化
- `planned`：已冻结目标，但尚未实现

| Ecosystem | Priority | Provider Lane | Desktop | CLI | IDE |
|---|---|---|---|---|---|
| Qwen / DashScope / Qwen Code | China | `qwen-api` `exact-ready` | `qwen-desktop` `detect-ready` `native-client` | `qwen-code-cli` `exact-ready` `native-client` | `qwen-ide-proxy` `planned` `ingress-capture` |
| Kimi / Moonshot / Kimi CLI | China | `moonshot-kimi-api` `exact-ready` | `kimi-desktop` `detect-ready` `native-client` | `kimi-cli` `exact-ready` `native-client` | `kimi-ide-proxy` `planned` `ingress-capture` |
| GLM / BigModel / Z.ai | China | `zhipu-glm-api` `exact-ready` | `glm-desktop` `detect-ready` `native-client` | `glm-cli` `planned` `native-client` | `glm-ide-proxy` `planned` `ingress-capture` |
| MiniMax / MiniMax Agent | China | `minimax-api` `exact-ready` | `minimax-agent` `exact-ready` `native-client` | `minimax-cli-proxy` `planned` `ingress-capture` | `minimax-ide-proxy` `planned` `ingress-capture` |
| DeepSeek | China | `deepseek-api` `exact-ready` | `deepseek-desktop` `planned` `native-client` | `deepseek-cli-proxy` `planned` `ingress-capture` | `deepseek-ide-proxy` `planned` `ingress-capture` |
| Doubao / Volcengine Ark | China | `doubao-api` `exact-ready` | `doubao-desktop` `detect-ready` `native-client` | `doubao-cli-proxy` `planned` `ingress-capture` | `doubao-ide-proxy` `planned` `ingress-capture` |
| Baidu Qianfan / Wenxin | China | `baidu-qianfan-api` `exact-ready` | `qianfan-desktop` `planned` `native-client` | `qianfan-cli-proxy` `planned` `ingress-capture` | `qianfan-ide-proxy` `planned` `ingress-capture` |
| Tencent Hunyuan / Yuanbao | China | `tencent-hunyuan-api` `exact-ready` | `yuanbao-desktop` `planned` `native-client` | `hunyuan-cli-proxy` `planned` `ingress-capture` | `hunyuan-ide-proxy` `planned` `ingress-capture` |
| StepFun | China | `stepfun-api` `exact-ready` | `stepfun-desktop` `planned` `native-client` | `stepfun-cli-proxy` `planned` `ingress-capture` | `stepfun-ide-proxy` `planned` `ingress-capture` |
| SenseNova | China | `sensenova-api` `exact-ready` | `sensenova-desktop` `planned` `native-client` | `sensenova-cli-proxy` `planned` `ingress-capture` | `sensenova-ide-proxy` `planned` `ingress-capture` |
| Baichuan | China | `baichuan-api` `exact-ready` | `baichuan-desktop` `planned` `native-client` | `baichuan-cli-proxy` `planned` `ingress-capture` | `baichuan-ide-proxy` `planned` `ingress-capture` |
| SiliconFlow | China | `siliconflow-api` `exact-ready` | `siliconflow-desktop` `planned` `native-client` | `siliconflow-cli-proxy` `planned` `ingress-capture` | `siliconflow-ide-proxy` `planned` `ingress-capture` |
| 讯飞星火 / Spark | China | `spark-api` `exact-ready` | `spark-desktop` `planned` `native-client` | `spark-cli-proxy` `planned` `ingress-capture` | `spark-ide-proxy` `planned` `ingress-capture` |
| OpenAI / Codex / ChatGPT Desktop | Global | `openai-api` `exact-ready` | `chatgpt-desktop` `planned` `native-client` | `codex` `exact-ready` `native-client` | `openai-ide-proxy` `planned` `ingress-capture` |
| Anthropic / Claude Code / Claude Desktop | Global | `anthropic-api` `exact-ready` | `claude-desktop` `exact-ready` `native-client` | `claude-code` `exact-ready` `native-client` | `anthropic-ide-proxy` `planned` `ingress-capture` |
| Google Gemini / Gemini CLI | Global | `google-gemini-api` `exact-ready` | `gemini-desktop` `planned` `native-client` | `gemini-cli` `planned` `native-client` | `gemini-ide-proxy` `planned` `ingress-capture` |
| OpenRouter | Global | `openrouter-api` `exact-ready` | `openrouter-desktop-proxy` `planned` `ingress-capture` | `openrouter-cli-proxy` `planned` `ingress-capture` | `openrouter-ide-proxy` `planned` `ingress-capture` |
| Perplexity | Global | `perplexity-api` `exact-ready` | `perplexity-desktop` `detect-ready` `native-client` | `perplexity-cli-proxy` `planned` `ingress-capture` | `perplexity-ide-proxy` `planned` `ingress-capture` |
| xAI / Grok | Global | `xai-grok-api` `exact-ready` | `grok-desktop` `planned` `native-client` | `grok-cli-proxy` `planned` `ingress-capture` | `grok-ide-proxy` `planned` `ingress-capture` |
| Mistral | Global | `mistral-api` `exact-ready` | `mistral-desktop` `planned` `native-client` | `mistral-cli-proxy` `planned` `ingress-capture` | `mistral-ide-proxy` `planned` `ingress-capture` |

## Current Reading Rule

- `Desktop`: 优先 `native-client`
- `CLI`: 优先 `official export/logs`，拿不到再走 `ingress-capture`
- `IDE`: 默认 `ingress-capture`
