"""One action-generation result shape for both model-driven agent protocols.

HF and vLLM engines own backend decoding. This seam selects their structured
action method, preserves measured metadata, and adapts legacy scripted engines
without claiming token counts that were not measured.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Completion:
    """Backend completion with measured usage and decoding provenance."""
    text: str
    engine: str
    model_id: str
    revision: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    response_format: str = 'text'
    schema_sha256: str | None = None

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ActionGenerationResult:
    text: str
    usage: dict


def generate_action(engine, messages, schema):
    """Generate one action with the schema when the engine supports it."""
    if hasattr(engine, 'complete_action_result'):
        completion = engine.complete_action_result(messages, schema)
    elif hasattr(engine, 'complete_result'):
        completion = engine.complete_result(messages)
    else:
        text = engine.complete(messages)
        if not isinstance(text, str):
            raise TypeError('action completion must contain text')
        return ActionGenerationResult(text, {'engine': engine.name,
                                             'input_tokens': None, 'output_tokens': None})
    if not isinstance(completion.text, str):
        raise TypeError('action completion must contain text')
    metadata = completion.as_dict()
    if not isinstance(metadata, dict):
        raise TypeError('action completion metadata must be a mapping')
    usage = dict(metadata)
    usage.pop('text', None)
    return ActionGenerationResult(completion.text, usage)
