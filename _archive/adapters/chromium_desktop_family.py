from __future__ import annotations

from adapters.chromium_desktop import ChromiumDesktopAdapter, ChromiumDesktopSourceDefinition
from core.config import (
    TOKEN_USAGE_BAICHUAN_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_CHATGPT_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_GEMINI_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_GROK_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_MISTRAL_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_QIANFAN_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_SENSENOVA_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_SILICONFLOW_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_SPARK_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_STEPFUN_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_YUANBAO_DESKTOP_ROOT_ENV,
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
        source_id="deepseek-desktop",
        display_name="DeepSeek Desktop",
        provider="deepseek",
        env_name=TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT_ENV,
        app_names=("DeepSeek", "DeepSeek App"),
        response_url_keywords=(
            "chat.deepseek.com/api/",
            "api.deepseek.com/",
        ),
        usage_url_keywords=(
            "chat.deepseek.com/api/",
            "api.deepseek.com/",
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
        source_id="qianfan-desktop",
        display_name="Qianfan Desktop",
        provider="baidu",
        env_name=TOKEN_USAGE_QIANFAN_DESKTOP_ROOT_ENV,
        app_names=("Qianfan", "Wenxin", "Wenxiaoyan", "文小言", "文心"),
        response_url_keywords=(
            "qianfan.baidubce.com/v2/",
            "aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/",
            "wenxiaoyan.baidu.com/",
        ),
        usage_url_keywords=(
            "qianfan.baidubce.com/v2/chat/completions",
            "aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/",
            "wenxiaoyan.baidu.com/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="yuanbao-desktop",
        display_name="Yuanbao Desktop",
        provider="tencent",
        env_name=TOKEN_USAGE_YUANBAO_DESKTOP_ROOT_ENV,
        app_names=("Yuanbao", "Tencent Yuanbao", "元宝", "腾讯元宝"),
        response_url_keywords=(
            "yuanbao.tencent.com/api/",
            "hunyuan.tencentcloudapi.com/",
            "open.hunyuan.tencent.com/",
        ),
        usage_url_keywords=(
            "yuanbao.tencent.com/api/",
            "hunyuan.tencentcloudapi.com/",
            "open.hunyuan.tencent.com/",
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
    ChromiumDesktopSourceDefinition(
        source_id="stepfun-desktop",
        display_name="StepFun Desktop",
        provider="stepfun",
        env_name=TOKEN_USAGE_STEPFUN_DESKTOP_ROOT_ENV,
        app_names=("StepFun", "Step", "StepChat", "跃问"),
        response_url_keywords=(
            "api.stepfun.ai/",
            "api.stepfun.com/",
        ),
        usage_url_keywords=(
            "api.stepfun.ai/",
            "api.stepfun.com/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="sensenova-desktop",
        display_name="SenseNova Desktop",
        provider="sensenova",
        env_name=TOKEN_USAGE_SENSENOVA_DESKTOP_ROOT_ENV,
        app_names=("SenseNova", "SenseChat", "日日新"),
        response_url_keywords=(
            "api.sensenova.cn/",
            "sensenova.cn/",
        ),
        usage_url_keywords=(
            "api.sensenova.cn/",
            "sensenova.cn/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="baichuan-desktop",
        display_name="Baichuan Desktop",
        provider="baichuan",
        env_name=TOKEN_USAGE_BAICHUAN_DESKTOP_ROOT_ENV,
        app_names=("Baichuan", "Baichuan AI", "百川"),
        response_url_keywords=(
            "api.baichuan-ai.com/",
        ),
        usage_url_keywords=(
            "api.baichuan-ai.com/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="siliconflow-desktop",
        display_name="SiliconFlow Desktop",
        provider="siliconflow",
        env_name=TOKEN_USAGE_SILICONFLOW_DESKTOP_ROOT_ENV,
        app_names=("SiliconFlow", "SiliconCloud"),
        response_url_keywords=(
            "api.siliconflow.cn/",
            "siliconflow.cn/",
        ),
        usage_url_keywords=(
            "api.siliconflow.cn/",
            "siliconflow.cn/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="spark-desktop",
        display_name="Spark Desktop",
        provider="spark",
        env_name=TOKEN_USAGE_SPARK_DESKTOP_ROOT_ENV,
        app_names=("Spark", "Xinghuo", "星火"),
        response_url_keywords=(
            "spark-api-open.xf-yun.com/",
            "spark-api.xf-yun.com/",
            "sparkcube-api.xf-yun.com/",
            "xf-yun.com/",
        ),
        usage_url_keywords=(
            "spark-api-open.xf-yun.com/",
            "spark-api.xf-yun.com/",
            "sparkcube-api.xf-yun.com/",
            "xf-yun.com/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="chatgpt-desktop",
        display_name="ChatGPT Desktop",
        provider="openai",
        env_name=TOKEN_USAGE_CHATGPT_DESKTOP_ROOT_ENV,
        app_names=("ChatGPT", "OpenAI"),
        response_url_keywords=(
            "api.openai.com/v1/",
            "chatgpt.com/backend-api/",
            "chat.openai.com/backend-api/",
        ),
        usage_url_keywords=(
            "api.openai.com/v1/",
            "chatgpt.com/backend-api/",
            "chat.openai.com/backend-api/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="gemini-desktop",
        display_name="Gemini Desktop",
        provider="google",
        env_name=TOKEN_USAGE_GEMINI_DESKTOP_ROOT_ENV,
        app_names=("Gemini", "Google Gemini"),
        response_url_keywords=(
            "generativelanguage.googleapis.com/",
            "aiplatform.googleapis.com/",
        ),
        usage_url_keywords=(
            "generativelanguage.googleapis.com/",
            "aiplatform.googleapis.com/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="grok-desktop",
        display_name="Grok Desktop",
        provider="xai",
        env_name=TOKEN_USAGE_GROK_DESKTOP_ROOT_ENV,
        app_names=("Grok", "xAI Grok"),
        response_url_keywords=(
            "api.x.ai/",
            "grok.x.ai/api/",
        ),
        usage_url_keywords=(
            "api.x.ai/",
            "grok.x.ai/api/",
        ),
    ),
    ChromiumDesktopSourceDefinition(
        source_id="mistral-desktop",
        display_name="Mistral Desktop",
        provider="mistral",
        env_name=TOKEN_USAGE_MISTRAL_DESKTOP_ROOT_ENV,
        app_names=("Mistral", "Le Chat", "Mistral Le Chat"),
        response_url_keywords=(
            "api.mistral.ai/",
        ),
        usage_url_keywords=(
            "api.mistral.ai/",
        ),
    ),
)


def build_chromium_desktop_family_adapters() -> list[ChromiumDesktopAdapter]:
    return [ChromiumDesktopAdapter(definition) for definition in _DESKTOP_SOURCE_DEFINITIONS]
