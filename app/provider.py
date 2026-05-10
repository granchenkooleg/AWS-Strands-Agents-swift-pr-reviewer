"""
Model provider selection.

STRANDS_PROVIDER=anthropic (default) → AnthropicModel using ANTHROPIC_API_KEY
STRANDS_PROVIDER=bedrock              → BedrockModel using AWS creds (deferred)

Slice 1 implements the Anthropic path only. Bedrock is wired in slice 4 when
we cut the AWS demo screenshots.
"""
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
_DEFAULT_BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def build_model(*, max_tokens: int = 1024) -> Any:
    """
    Returns a Strands model instance configured for the active provider.
    Imported lazily so missing optional deps don't break the unused branch.
    """
    provider = os.getenv("STRANDS_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to .env or export it."
            )
        return AnthropicModel(
            client_args={"api_key": api_key},
            model_id=os.getenv("ANTHROPIC_MODEL_ID", _DEFAULT_ANTHROPIC_MODEL),
            max_tokens=max_tokens,
        )

    if provider == "bedrock":
        # Slice 4: enable for AWS console screenshots.
        # Verify the model is enabled in your region's Bedrock console first.
        raise NotImplementedError(
            "Bedrock provider is deferred to slice 4. "
            "Set STRANDS_PROVIDER=anthropic for now."
        )

    raise ValueError(
        f"Unknown STRANDS_PROVIDER={provider!r}. Use 'anthropic' or 'bedrock'."
    )
