from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceTarget:
    surface_type: str
    display_name: str
    primary_lane: str
    maturity: str
    implemented_source_ids: tuple[str, ...] = ()
    planned_source_ids: tuple[str, ...] = ()
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "surface_type": self.surface_type,
            "display_name": self.display_name,
            "primary_lane": self.primary_lane,
            "maturity": self.maturity,
            "implemented_source_ids": list(self.implemented_source_ids),
            "planned_source_ids": list(self.planned_source_ids),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class EcosystemTarget:
    ecosystem_id: str
    display_name: str
    priority_group: str
    provider_lane_maturity: str
    provider_source_ids: tuple[str, ...]
    surfaces: tuple[SurfaceTarget, ...]
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "ecosystem_id": self.ecosystem_id,
            "display_name": self.display_name,
            "priority_group": self.priority_group,
            "provider_lane_maturity": self.provider_lane_maturity,
            "provider_source_ids": list(self.provider_source_ids),
            "surfaces": [surface.as_dict() for surface in self.surfaces],
            "notes": self.notes,
        }


def _surface(
    surface_type: str,
    display_name: str,
    *,
    primary_lane: str,
    maturity: str,
    implemented: tuple[str, ...] = (),
    planned: tuple[str, ...] = (),
    notes: str = "",
) -> SurfaceTarget:
    return SurfaceTarget(
        surface_type=surface_type,
        display_name=display_name,
        primary_lane=primary_lane,
        maturity=maturity,
        implemented_source_ids=implemented,
        planned_source_ids=planned,
        notes=notes,
    )


TOP20_ECOSYSTEM_TARGETS: tuple[EcosystemTarget, ...] = (
    EcosystemTarget(
        ecosystem_id="qwen",
        display_name="Qwen / DashScope / Qwen Code",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("qwen-api",),
        surfaces=(
            _surface("desktop", "Qwen Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("qwen-desktop",), notes="Unified Chromium/Electron parser now supports Cache_Data, IndexedDB, and Local Storage exact extraction."),
            _surface("cli", "Qwen Code CLI", primary_lane="native-client", maturity="exact-ready", implemented=("qwen-code-cli",), notes="Official project-scoped session JSONL files now provide exact usageMetadata."),
            _surface("ide", "Qwen IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("qwen-ide-proxy",), notes="Shared ingress bootstrap now provides an official DashScope OpenAI-compatible profile; Coding Plan users can override the upstream base URL if they use the dedicated coding endpoint."),
        ),
        notes="China-first priority because it spans provider API, desktop shells, and coding CLI surfaces.",
    ),
    EcosystemTarget(
        ecosystem_id="kimi",
        display_name="Kimi / Moonshot / Kimi CLI",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("moonshot-kimi-api",),
        surfaces=(
            _surface("desktop", "Kimi Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("kimi-desktop",), notes="Unified Chromium/Electron parser now supports Cache_Data, IndexedDB, and Local Storage exact extraction."),
            _surface("cli", "Kimi CLI", primary_lane="native-client", maturity="exact-ready", implemented=("kimi-cli",), notes="Official ~/.kimi/sessions wire.jsonl now provides exact StatusUpdate token_usage."),
            _surface("ide", "Kimi IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("kimi-ide-proxy",), notes="Shared ingress bootstrap now provides an official Moonshot OpenAI-compatible profile for Continue and CLI-style tooling."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="glm",
        display_name="GLM / BigModel / Z.ai",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("zhipu-glm-api",),
        surfaces=(
            _surface("desktop", "GLM Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("glm-desktop",), notes="Desktop root discovery now includes Z Code / ZCODE and exact parsing supports Cache_Data, IndexedDB, and Local Storage."),
            _surface("cli", "GLM CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("glm-cli-proxy",), notes="Shared ingress bootstrap now provides the official BigModel coding endpoint profile for GLM-compatible coding tools."),
            _surface("ide", "GLM IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("glm-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for the official BigModel coding endpoint."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="minimax",
        display_name="MiniMax / MiniMax Agent",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("minimax-api",),
        surfaces=(
            _surface("desktop", "MiniMax Agent", primary_lane="native-client", maturity="exact-ready", implemented=("minimax-agent",)),
            _surface("cli", "MiniMax CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("minimax-cli-proxy",), notes="Shared ingress bootstrap now provides an official MiniMax OpenAI-compatible CLI capture path."),
            _surface("ide", "MiniMax IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("minimax-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="deepseek",
        display_name="DeepSeek",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("deepseek-api",),
        surfaces=(
            _surface("desktop", "DeepSeek Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("deepseek-desktop",), notes="Desktop parser now supports Cache_Data, IndexedDB, and Local Storage exact extraction."),
            _surface("cli", "DeepSeek CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("deepseek-cli-proxy",), notes="Shared ingress bootstrap now provides an OpenAI-compatible CLI capture path via token_usage.py ingress bootstrap --profile deepseek."),
            _surface("ide", "DeepSeek IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("deepseek-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="doubao",
        display_name="Doubao / Volcengine Ark",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("doubao-api",),
        surfaces=(
            _surface("desktop", "Doubao Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("doubao-desktop",), notes="Desktop parser now supports Cache_Data, IndexedDB, and Local Storage exact extraction."),
            _surface("cli", "Doubao CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("doubao-cli-proxy",), notes="Shared ingress bootstrap now provides the official Volcengine Ark OpenAI-compatible CLI capture path."),
            _surface("ide", "Doubao IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("doubao-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for the official Volcengine Ark endpoint."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="qianfan",
        display_name="Baidu Qianfan / Wenxin",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("baidu-qianfan-api",),
        surfaces=(
            _surface("desktop", "Qianfan Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("qianfan-desktop",), notes="Desktop parser now supports Cache_Data, IndexedDB, and Local Storage exact extraction."),
            _surface("cli", "Qianfan CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("qianfan-cli-proxy",), notes="Shared ingress bootstrap now provides an OpenAI-compatible Qianfan CLI capture path via token_usage.py ingress bootstrap --profile qianfan."),
            _surface("ide", "Qianfan IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("qianfan-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="hunyuan",
        display_name="Tencent Hunyuan / Yuanbao",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("tencent-hunyuan-api",),
        surfaces=(
            _surface("desktop", "Yuanbao Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("yuanbao-desktop",), notes="Desktop parser now supports Cache_Data, IndexedDB, and Local Storage exact extraction."),
            _surface("cli", "Hunyuan CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("hunyuan-cli-proxy",), notes="Shared ingress bootstrap now provides an OpenAI-compatible Hunyuan CLI capture path via token_usage.py ingress bootstrap --profile hunyuan."),
            _surface("ide", "Hunyuan IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("hunyuan-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="stepfun",
        display_name="StepFun",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("stepfun-api",),
        surfaces=(
            _surface("desktop", "StepFun Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("stepfun-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium Cache_Data."),
            _surface("cli", "StepFun CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("stepfun-cli-proxy",), notes="Shared ingress bootstrap now provides an official StepFun OpenAI-compatible CLI capture path."),
            _surface("ide", "StepFun IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("stepfun-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="sensenova",
        display_name="SenseNova",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("sensenova-api",),
        surfaces=(
            _surface("desktop", "SenseNova Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("sensenova-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium Cache_Data."),
            _surface("cli", "SenseNova CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("sensenova-cli-proxy",), notes="Shared ingress bootstrap now provides an OpenAI-compatible SenseNova CLI capture path."),
            _surface("ide", "SenseNova IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("sensenova-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
        notes="Provider exact pack is live; CLI / IDE share ingress bootstrap and desktop is now fixture-backed exact-ready.",
    ),
    EcosystemTarget(
        ecosystem_id="baichuan",
        display_name="Baichuan",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("baichuan-api",),
        surfaces=(
            _surface("desktop", "Baichuan Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("baichuan-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium IndexedDB."),
            _surface("cli", "Baichuan CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("baichuan-cli-proxy",), notes="Shared ingress bootstrap now provides a manual-upstream OpenAI-compatible CLI capture path."),
            _surface("ide", "Baichuan IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("baichuan-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets; public docs still require manual upstream base_url input."),
        ),
        notes="Provider exact pack is live; CLI / IDE share ingress bootstrap and desktop is now fixture-backed exact-ready.",
    ),
    EcosystemTarget(
        ecosystem_id="siliconflow",
        display_name="SiliconFlow",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("siliconflow-api",),
        surfaces=(
            _surface("desktop", "SiliconFlow Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("siliconflow-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium Local Storage."),
            _surface("cli", "SiliconFlow CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("siliconflow-cli-proxy",), notes="Shared ingress bootstrap now provides an OpenAI-compatible SiliconFlow CLI capture path."),
            _surface("ide", "SiliconFlow IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("siliconflow-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
        notes="Provider exact pack can match provider fields or request endpoint hints; CLI / IDE share ingress bootstrap and desktop is now fixture-backed exact-ready.",
    ),
    EcosystemTarget(
        ecosystem_id="spark",
        display_name="讯飞星火 / Spark",
        priority_group="china-priority",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("spark-api",),
        surfaces=(
            _surface("desktop", "Spark Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("spark-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium Cache_Data."),
            _surface("cli", "Spark CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("spark-cli-proxy",), notes="Shared ingress bootstrap now provides an OpenAI-compatible Spark CLI capture path."),
            _surface("ide", "Spark IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("spark-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
        notes="Provider exact pack is live and recognizes Spark API endpoints; CLI / IDE share ingress bootstrap and desktop is now fixture-backed exact-ready.",
    ),
    EcosystemTarget(
        ecosystem_id="openai",
        display_name="OpenAI / Codex / ChatGPT Desktop",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("openai-api",),
        surfaces=(
            _surface("desktop", "ChatGPT Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("chatgpt-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium IndexedDB."),
            _surface("cli", "Codex CLI", primary_lane="native-client", maturity="exact-ready", implemented=("codex",)),
            _surface("ide", "OpenAI IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("openai-ide-proxy",), notes="Shared ingress bootstrap now provides an official OpenAI profile with embedded api.openai.com/v1 upstream and Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="anthropic",
        display_name="Anthropic / Claude Code / Claude Desktop",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("anthropic-api",),
        surfaces=(
            _surface("desktop", "Claude Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("claude-desktop",)),
            _surface("cli", "Claude Code", primary_lane="native-client", maturity="exact-ready", implemented=("claude-code",)),
            _surface("ide", "Claude IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("anthropic-ide-proxy",), notes="Shared ingress bootstrap now provides an official Anthropic profile with embedded api.anthropic.com upstream and Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="gemini",
        display_name="Google Gemini / Gemini CLI",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("google-gemini-api",),
        surfaces=(
            _surface("desktop", "Gemini Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("gemini-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium Local Storage."),
            _surface("cli", "Gemini CLI", primary_lane="native-client", maturity="exact-ready", implemented=("gemini-cli",), notes="Official ~/.gemini/tmp/*/chats/session-*.json files now provide exact Gemini message token records."),
            _surface("ide", "Gemini IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("gemini-ide-proxy",), notes="Shared ingress bootstrap now provides an official Gemini OpenAI-compatibility profile and Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="openrouter",
        display_name="OpenRouter",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("openrouter-api",),
        surfaces=(
            _surface("desktop", "OpenRouter Desktop Shell", primary_lane="ingress-capture", maturity="exact-ready", implemented=("openrouter-desktop-proxy",), notes="Provider-first family; desktop support is now captured through the shared OpenRouter ingress bootstrap rather than native app parsing."),
            _surface("cli", "OpenRouter CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("openrouter-cli-proxy",), notes="Shared ingress bootstrap now provides an official OpenRouter CLI capture path."),
            _surface("ide", "OpenRouter IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("openrouter-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="perplexity",
        display_name="Perplexity",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("perplexity-api",),
        surfaces=(
            _surface("desktop", "Perplexity Desktop", primary_lane="native-client", maturity="exact-ready", implemented=("perplexity-desktop",), notes="Desktop root discovery now includes Comet and exact parsing supports Cache_Data, IndexedDB, and Local Storage."),
            _surface("cli", "Perplexity CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("perplexity-cli-proxy",), notes="Shared ingress bootstrap now provides a Perplexity Sonar-compatible CLI capture path on the root base URL."),
            _surface("ide", "Perplexity IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("perplexity-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains on the root base URL."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="xai",
        display_name="xAI / Grok",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("xai-grok-api",),
        surfaces=(
            _surface("desktop", "Grok Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("grok-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium IndexedDB."),
            _surface("cli", "Grok CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("grok-cli-proxy",), notes="Shared ingress bootstrap now provides an official xAI CLI capture path."),
            _surface("ide", "Grok IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("grok-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
    EcosystemTarget(
        ecosystem_id="mistral",
        display_name="Mistral",
        priority_group="global",
        provider_lane_maturity="exact-ready",
        provider_source_ids=("mistral-api",),
        surfaces=(
            _surface("desktop", "Mistral Desktop Shell", primary_lane="native-client", maturity="exact-ready", implemented=("mistral-desktop",), notes="Desktop parser now has fixture-backed exact extraction from Chromium Cache_Data."),
            _surface("cli", "Mistral CLI", primary_lane="ingress-capture", maturity="exact-ready", implemented=("mistral-cli-proxy",), notes="Shared ingress bootstrap now provides an official Mistral CLI capture path."),
            _surface("ide", "Mistral IDE", primary_lane="ingress-capture", maturity="exact-ready", implemented=("mistral-ide-proxy",), notes="Shared ingress bootstrap now provides Continue snippets for VS Code and JetBrains."),
        ),
    ),
)


def list_top20_ecosystem_targets() -> tuple[EcosystemTarget, ...]:
    return TOP20_ECOSYSTEM_TARGETS


def build_top20_registry_summary() -> dict[str, object]:
    ecosystems = list_top20_ecosystem_targets()
    surfaces = [surface for ecosystem in ecosystems for surface in ecosystem.surfaces]
    maturity_counts: dict[str, int] = {}
    lane_counts: dict[str, int] = {}
    for surface in surfaces:
        maturity_counts[surface.maturity] = maturity_counts.get(surface.maturity, 0) + 1
        lane_counts[surface.primary_lane] = lane_counts.get(surface.primary_lane, 0) + 1

    provider_counts: dict[str, int] = {}
    for ecosystem in ecosystems:
        provider_counts[ecosystem.provider_lane_maturity] = provider_counts.get(ecosystem.provider_lane_maturity, 0) + 1

    return {
        "total_ecosystems": len(ecosystems),
        "china_priority_ecosystems": sum(1 for item in ecosystems if item.priority_group == "china-priority"),
        "global_ecosystems": sum(1 for item in ecosystems if item.priority_group == "global"),
        "total_surfaces": len(surfaces),
        "provider_lane_maturity": provider_counts,
        "surface_maturity": maturity_counts,
        "surface_primary_lanes": lane_counts,
    }


def build_top20_registry_payload() -> dict[str, object]:
    return {
        "scope": {
            "frozen_by": "ecosystem/client-family",
            "surfaces": ["desktop", "cli", "ide"],
            "capture_lanes": ["native-client", "provider-exact", "ingress-capture"],
        },
        "summary": build_top20_registry_summary(),
        "ecosystems": [item.as_dict() for item in list_top20_ecosystem_targets()],
    }
