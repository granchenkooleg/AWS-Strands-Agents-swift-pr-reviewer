"""
Model provider selection.

STRANDS_PROVIDER=anthropic (default) → AnthropicModel using ANTHROPIC_API_KEY
STRANDS_PROVIDER=bedrock              → BedrockModel using AWS creds + region

Memoization: build_model() is `@lru_cache`d. Each unique (provider, max_tokens,
model_id) combination produces exactly one model instance for the lifetime of
the process. This prevents httpx.AsyncClient proliferation across many Agent
instances (empirically: the eval used to create 12+ clients per run, racing
asyncio shutdown and spewing "Event loop is closed" tracebacks).
"""
import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv()


_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
_DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


@lru_cache(maxsize=None)
def _cached_anthropic_model(max_tokens: int, api_key: str, model_id: str) -> Any:
    from strands.models.anthropic import AnthropicModel
    return AnthropicModel(
        client_args={"api_key": api_key},
        model_id=model_id,
        max_tokens=max_tokens,
    )


@lru_cache(maxsize=None)
def _cached_bedrock_model(max_tokens: int, region: str, model_id: str) -> Any:
    from strands.models import BedrockModel
    return BedrockModel(
        model_id=model_id,
        region_name=region,
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
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise RuntimeError(
                "AWS_REGION not set. Add AWS_REGION=us-east-1 to .env "
                "(or export AWS_DEFAULT_REGION)."
            )
        if not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
            raise RuntimeError(
                "No AWS credentials found. Set AWS_ACCESS_KEY_ID + "
                "AWS_SECRET_ACCESS_KEY, or AWS_PROFILE, in .env."
            )
        return _cached_bedrock_model(
            max_tokens,
            region,
            os.getenv("BEDROCK_MODEL_ID", _DEFAULT_BEDROCK_MODEL),
        )

    raise ValueError(
        f"Unknown STRANDS_PROVIDER={provider!r}. Use 'anthropic' or 'bedrock'."
    )
