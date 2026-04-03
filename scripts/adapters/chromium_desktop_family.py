from __future__ import annotations

from adapters.chromium_desktop import ChromiumDesktopAdapter, ChromiumDesktopSourceDefinition
from core.config import (
    TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV,
)


_DESKTOP_SOURCE_DEFINITIONS: tuple[ChromiumDesktopSourceDefinition, ...] = (
    ChromiumDesktopSourceDefinition(
        source_id="kimi-desktop",
        display_name="Kimi Desktop",
        provider="moonshotai",
        env_name=TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV,
        app_names=("Kimi", "Moonshot", "Moonshot AI"),
        response_url_keywords=(
            "kimi.moonshot.cn/api/",
            "platform.moonshot.cn/api/",
            "api.moonshot.cn/",
        ),
        usage_url_keywords=(
            "kimi.moonshot.cn/api/chat/",
            "platform.moonshot.cn/api/",
            "api.moonshot.cn/v1/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="glm-desktop",
        display_name="GLM Desktop",
        provider="z-ai",
        env_name=TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV,
        app_names=("GLM", "Z.ai", "Zhipu AI", "BigModel", "Z Code", "ZCODE"),
        response_url_keywords=(
            "chatglm.cn/api/",
            "open.bigmodel.cn/api/",
            "chat.z.ai/api/",
            "z.ai/api/",
        ),
        usage_url_keywords=(
            "open.bigmodel.cn/api/",
            "chatglm.cn/api/",
            "chat.z.ai/api/",
            "z.ai/api/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="qwen-desktop",
        display_name="Qwen Desktop",
        provider="qwen",
        env_name=TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV,
        app_names=("Qwen", "DashScope", "Tongyi"),
        response_url_keywords=(
            "chat.qwen.ai/api/",
            "dashscope.aliyuncs.com/api/",
            "dashscope.aliyun.com/api/",
        ),
        usage_url_keywords=(
            "chat.qwen.ai/api/",
            "dashscope.aliyuncs.com/api/",
            "dashscope.aliyun.com/api/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="doubao-desktop",
        display_name="Doubao Desktop",
        provider="bytedance",
        env_name=TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV,
        app_names=("Doubao", "豆包"),
        response_url_keywords=(
            "www.doubao.com/api/",
            "doubao.com/api/",
            "ark.cn-beijing.volces.com/api/",
        ),
        usage_url_keywords=(
            "www.doubao.com/api/",
            "doubao.com/api/",
            "ark.cn-beijing.volces.com/api/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="perplexity-desktop",
        display_name="Perplexity Desktop",
        provider="perplexity",
        env_name=TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV,
        app_names=("Perplexity", "Perplexity Desktop", "Comet"),
        response_url_keywords=(
            "www.perplexity.ai/api/",
            "www.perplexity.ai/rest/",
            "api.perplexity.ai/",
        ),
        usage_url_keywords=(
            "www.perplexity.ai/api/",
            "www.perplexity.ai/rest/",
            "api.perplexity.ai/",
        ),
    ),
)


def build_chromium_desktop_family_adapters() -> list[ChromiumDesktopAdapter]:
    return [ChromiumDesktopAdapter(definition) for definition in _DESKTOP_SOURCE_DEFINITIONS]
