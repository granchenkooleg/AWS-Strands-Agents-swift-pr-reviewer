"""
OpenTelemetry tracing setup for the Bedrock demo run.

Gated by `OTEL_EXPORTER_OTLP_ENDPOINT`. When unset, `setup_tracing()` no-ops
so the local Anthropic dev path stays free of tracing noise.

When set (typically pointing at a local ADOT collector on `localhost:4318`),
this initializes a TracerProvider with an OTLP HTTP exporter. The ADOT
collector forwards spans to CloudWatch X-Ray. Strands Agents emits OTel
spans natively; nothing else needs to opt in.

This is intentionally minimal — production observability is the ADOT
collector's job. We only stand up the SDK so spans have somewhere to go.
"""
from __future__ import annotations

import os
from typing import Final

_INITIALIZED: bool = False


def setup_tracing(service_name: str | None = None) -> bool:
    """
    Initialize the OTel SDK once per process. Returns True if tracing was
    activated, False if it was skipped (no OTLP endpoint configured).
    """
    global _INITIALIZED
    if _INITIALIZED:
        return True

    endpoint: Final[str | None] = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return False

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({
        "service.name": service_name
            or os.getenv("OTEL_SERVICE_NAME", "swift-pr-reviewer"),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

    _INITIALIZED = True
    return True
