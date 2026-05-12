"""
Model provider selection.

STRANDS_PROVIDER=anthropic (default) → AnthropicModel using ANTHROPIC_API_KEY
STRANDS_PROVIDER=bedrock              → BedrockModel using AWS creds (slice 5)

The Anthropic path is the daily-dev path. Bedrock is wired in slice 5 when
we cut the AWS console screenshots for the homework submission.

Memoization: build_model() is `@lru_cache`d. Each unique max_tokens value
produces exactly one model instance for the lifetime of the process. This
prevents httpx.AsyncClient proliferation across many Agent instances
(empirically: the eval used to create 12+ clients per run, racing asyncio
shutdown and spewing "Event loop is closed" tracebacks).
"""
import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv()


_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
_DEFAULT_BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"


@lru_cache(maxsize=None)
def _cached_anthropic_model(max_tokens: int, api_key: str, model_id: str) -> Any:
    from strands.models.anthropic import AnthropicModel
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id=model_id,
        max_tokens=max_tokens,
    )


def build_model(*, max_tokens: int = 1024) -> Any:
    """
    Returns a Strands model instance for the active provider.

    Same `(provider, max_tokens, model_id)` returns the same instance every
    time — see module docstring for why memoization matters.
    """
    provider = os.getenv("STRANDS_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to .env or export it."
            )
        return _cached_anthropic_model(
            max_tokens,
            api_key,
            os.getenv("ANTHROPIC_MODEL_ID", _DEFAULT_ANTHROPIC_MODEL),
        )

    if provider == "bedrock":
        # Slice 5: enable for AWS console screenshots.
        raise NotImplementedError(
            "Bedrock provider is deferred to slice 5. "
            "Set STRANDS_PROVIDER=anthropic for now."
        )

    raise ValueError(
        f"Unknown STRANDS_PROVIDER={provider!r}. Use 'anthropic' or 'bedrock'."
    )
