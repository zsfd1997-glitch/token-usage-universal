from __future__ import annotations

import json
from dataclasses import dataclass

from core.ingress_companion import (
    IngressCompanionConfig,
    build_ingress_companion_config,
    build_ingress_companion_payload,
)


@dataclass(frozen=True)
class IngressBootstrapProfile:
    profile_id: str
    display_name: str
    provider: str
    protocol: str
    upstream_base_url: str | None
    default_model: str
    api_key_env: str
    surfaces: tuple[str, ...] = ("cli", "ide")
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "protocol": self.protocol,
            "upstream_base_url": self.upstream_base_url,
            "default_model": self.default_model,
            "api_key_env": self.api_key_env,
            "surfaces": list(self.surfaces),
            "notes": self.notes,
        }


EDITOR_CONFIG = {
    "vscode": {
        "display_name": "VS Code",
        "continue_config_path": "~/.continue/config.yaml",
        "open_hint": "Open Continue with Cmd/Ctrl+L after saving the config.",
    },
    "jetbrains": {
        "display_name": "JetBrains",
        "continue_config_path": "~/.continue/config.yaml",
        "open_hint": "Open Continue with Cmd/Ctrl+J after saving the config.",
    },
}


BOOTSTRAP_PROFILES: tuple[IngressBootstrapProfile, ...] = (
    IngressBootstrapProfile(
        profile_id="openai",
        display_name="OpenAI",
        provider="openai",
        protocol="openai",
        upstream_base_url="https://api.openai.com/v1",
        default_model="gpt-4.1",
        api_key_env="OPENAI_API_KEY",
        notes="Official OpenAI API profile for IDE or CLI clients that only need the local ingress base_url swapped.",
    ),
    IngressBootstrapProfile(
        profile_id="anthropic",
        display_name="Anthropic",
        provider="anthropic",
        protocol="anthropic",
        upstream_base_url="https://api.anthropic.com",
        default_model="claude-sonnet-4-20250514",
        api_key_env="ANTHROPIC_API_KEY",
        notes="Official Anthropic Messages API profile for IDE or CLI clients that only need the local ingress base_url swapped.",
    ),
    IngressBootstrapProfile(
        profile_id="openai-compatible",
        display_name="OpenAI-Compatible Generic",
        provider="openai-compatible",
        protocol="openai",
        upstream_base_url=None,
        default_model="your-model-id",
        api_key_env="OPENAI_API_KEY",
        notes="Use this when your upstream is OpenAI-compatible but the exact base URL varies by environment.",
    ),
    IngressBootstrapProfile(
        profile_id="anthropic-compatible",
        display_name="Anthropic-Compatible Generic",
        provider="anthropic-compatible",
        protocol="anthropic",
        upstream_base_url=None,
        default_model="your-model-id",
        api_key_env="ANTHROPIC_API_KEY",
        notes="Use this when your upstream is Anthropic-compatible but the exact base URL varies by environment.",
    ),
    IngressBootstrapProfile(
        profile_id="deepseek",
        display_name="DeepSeek",
        provider="deepseek",
        protocol="openai",
        upstream_base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
    ),
    IngressBootstrapProfile(
        profile_id="qianfan",
        display_name="Baidu Qianfan / Wenxin",
        provider="baidu",
        protocol="openai",
        upstream_base_url="https://qianfan.baidubce.com/v2",
        default_model="ernie-4.5-turbo-32k",
        api_key_env="QIANFAN_API_KEY",
        notes="Qianfan currently uses the v2 chat completions path in this bootstrap.",
    ),
    IngressBootstrapProfile(
        profile_id="hunyuan",
        display_name="Tencent Hunyuan / Yuanbao",
        provider="tencent",
        protocol="openai",
        upstream_base_url="https://api.lkeap.cloud.tencent.com/v3",
        default_model="hunyuan-2.0-instruct",
        api_key_env="HUNYUAN_API_KEY",
    ),
    IngressBootstrapProfile(
        profile_id="sensenova",
        display_name="SenseNova",
        provider="sensenova",
        protocol="openai",
        upstream_base_url="https://api.sensenova.cn/compatible-mode/v1",
        default_model="SenseChat-5",
        api_key_env="SENSENOVA_API_KEY",
    ),
    IngressBootstrapProfile(
        profile_id="baichuan",
        display_name="Baichuan",
        provider="baichuan",
        protocol="openai",
        upstream_base_url=None,
        default_model="Baichuan4-Turbo",
        api_key_env="BAICHUAN_API_KEY",
        notes="Public docs do not expose one stable crawler-readable API base URL; pass --upstream-base-url from your console or contract.",
    ),
    IngressBootstrapProfile(
        profile_id="siliconflow",
        display_name="SiliconFlow",
        provider="siliconflow",
        protocol="openai",
        upstream_base_url="https://api.siliconflow.cn/v1",
        default_model="Qwen/Qwen3-Coder-30B-A3B-Instruct",
        api_key_env="SILICONFLOW_API_KEY",
    ),
    IngressBootstrapProfile(
        profile_id="spark",
        display_name="Spark",
        provider="spark",
        protocol="openai",
        upstream_base_url="https://spark-api-open.xf-yun.com/v2",
        default_model="spark-x",
        api_key_env="SPARK_API_PASSWORD",
    ),
)


def list_ingress_bootstrap_profiles() -> tuple[IngressBootstrapProfile, ...]:
    return BOOTSTRAP_PROFILES


def get_ingress_bootstrap_profile(profile_id: str) -> IngressBootstrapProfile:
    normalized = profile_id.strip().lower()
    for profile in BOOTSTRAP_PROFILES:
        if profile.profile_id == normalized:
            return profile
    raise KeyError(profile_id)


def _continue_snippet(
    *,
    display_name: str,
    protocol: str,
    model: str,
    api_key_env: str,
    local_base_url: str,
) -> str:
    provider_name = "anthropic" if protocol == "anthropic" else "openai"
    secret_ref = "${{ secrets." + api_key_env + " }}"
    return "\n".join(
        [
            "name: Token Usage Universal Ingress",
            "version: 1.0.0",
            "schema: v1",
            "models:",
            f"  - name: {display_name} via Ingress",
            f"    provider: {provider_name}",
            f"    model: {model}",
            f"    apiKey: {secret_ref}",
            f"    apiBase: {local_base_url}",
            "    roles:",
            "      - chat",
            "      - edit",
            "      - apply",
        ]
    )


def _shell_exports(profile: IngressBootstrapProfile, config_payload: dict[str, object]) -> dict[str, str]:
    local_base_url = str(config_payload["local_base_url"])
    if profile.protocol == "anthropic":
        return {
            "ANTHROPIC_BASE_URL": local_base_url,
            "ANTHROPIC_API_KEY": f"${profile.api_key_env}",
        }
    return {
        "OPENAI_BASE_URL": local_base_url,
        "OPENAI_API_KEY": f"${profile.api_key_env}",
    }


def build_ingress_bootstrap_payload(
    *,
    profile_id: str,
    editor: str,
    upstream_base_url: str | None = None,
    model: str | None = None,
    listen_host: str = "127.0.0.1",
    listen_port: int = 8787,
    local_base_path: str | None = None,
    log_root: str | None = None,
    project_path: str | None = None,
) -> dict[str, object]:
    profile = get_ingress_bootstrap_profile(profile_id)
    editor_key = editor.strip().lower()
    if editor_key not in EDITOR_CONFIG:
        raise ValueError(f"unsupported editor: {editor}")

    resolved_upstream = upstream_base_url or profile.upstream_base_url
    if not resolved_upstream:
        raise ValueError(
            f"profile {profile.profile_id} requires --upstream-base-url because no default official base URL is embedded"
        )

    config: IngressCompanionConfig = build_ingress_companion_config(
        provider=profile.provider,
        upstream_base_url=resolved_upstream,
        protocol=profile.protocol,
        listen_host=listen_host,
        listen_port=listen_port,
        local_base_path=local_base_path,
        log_root=log_root,
        project_path=project_path,
    )
    companion = build_ingress_companion_payload(config)
    resolved_model = model or profile.default_model
    editor_meta = EDITOR_CONFIG[editor_key]
    continue_snippet = _continue_snippet(
        display_name=profile.display_name,
        protocol=profile.protocol,
        model=resolved_model,
        api_key_env=profile.api_key_env,
        local_base_url=str(companion["local_base_url"]),
    )
    cli_exports = _shell_exports(profile, companion)

    return {
        "profile": profile.as_dict(),
        "editor": {
            "id": editor_key,
            "display_name": editor_meta["display_name"],
            "continue_config_path": editor_meta["continue_config_path"],
            "open_hint": editor_meta["open_hint"],
        },
        "companion": companion,
        "continue": {
            "config_path": editor_meta["continue_config_path"],
            "snippet": continue_snippet,
            "notes": [
                "Continue works in both VS Code and JetBrains.",
                "Keep the provider key secret as-is; only point apiBase to the local ingress companion.",
            ],
        },
        "cli": {
            "shell_exports": cli_exports,
            "example": " ".join(f'{key}=\"{value}\"' for key, value in cli_exports.items()) + " your-cli-command",
            "notes": [
                "For OpenAI-compatible or Anthropic-compatible CLIs, keep the original key and redirect only the base URL.",
            ],
        },
    }


def build_ingress_profiles_payload() -> dict[str, object]:
    profiles = [profile.as_dict() for profile in list_ingress_bootstrap_profiles()]
    protocol_counts: dict[str, int] = {}
    for profile in profiles:
        protocol = str(profile["protocol"])
        protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
    return {
        "summary": {
            "profiles": len(profiles),
            "protocols": protocol_counts,
        },
        "profiles": profiles,
    }


def render_ingress_profiles_payload(payload: dict[str, object]) -> str:
    lines = ["Ingress Profiles"]
    summary = payload["summary"]
    lines.append(f"Profiles: {summary['profiles']}")
    protocol_text = ", ".join(f"{key}={value}" for key, value in summary["protocols"].items())
    lines.append(f"Protocols: {protocol_text}")
    lines.append("")
    for profile in payload["profiles"]:
        upstream = profile["upstream_base_url"] or "(manual --upstream-base-url required)"
        lines.append(
            f"- {profile['profile_id']}: {profile['display_name']} | {profile['protocol']} | {upstream}"
        )
    return "\n".join(lines)


def render_ingress_bootstrap_payload(payload: dict[str, object]) -> str:
    profile = payload["profile"]
    editor = payload["editor"]
    companion = payload["companion"]
    continue_section = payload["continue"]
    cli_section = payload["cli"]
    lines = [
        "Ingress Bootstrap",
        f"Profile: {profile['profile_id']} ({profile['display_name']})",
        f"Editor: {editor['display_name']}",
        f"Protocol: {profile['protocol']}",
        f"Upstream: {companion['upstream_base_url']}",
        f"Local Base URL: {companion['local_base_url']}",
        f"Log Root: {companion['log_root']}",
        "",
        "Continue Config Path:",
        f"  {continue_section['config_path']}",
        "Continue Snippet:",
    ]
    for line in str(continue_section["snippet"]).splitlines():
        lines.append(f"  {line}")
    lines.extend(
        [
            "",
            "CLI Exports:",
        ]
    )
    for key, value in cli_section["shell_exports"].items():
        lines.append(f"  export {key}=\"{value}\"")
    lines.extend(
        [
            "",
            "Start Companion:",
            "  python3 scripts/token_usage.py ingress serve "
            f"--provider {companion['provider']} --protocol {companion['protocol']} "
            f"--upstream-base-url {companion['upstream_base_url']} --listen-host {companion['listen_host']} "
            f"--listen-port {companion['listen_port']}",
        ]
    )
    return "\n".join(lines)


def payload_to_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = [
    "build_ingress_bootstrap_payload",
    "build_ingress_profiles_payload",
    "get_ingress_bootstrap_profile",
    "list_ingress_bootstrap_profiles",
    "payload_to_json",
    "render_ingress_bootstrap_payload",
    "render_ingress_profiles_payload",
]
