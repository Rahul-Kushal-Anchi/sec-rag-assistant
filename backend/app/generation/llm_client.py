"""Unified async LLM client wrapping Anthropic (default) and OpenAI (fallback)."""

# TODO: implement provider-agnostic chat() and stream() with tenacity retries,
# structured-output coercion to the Answer Pydantic schema.
