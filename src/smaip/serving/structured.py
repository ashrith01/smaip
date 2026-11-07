"""Small HF token-filter adapter for lm-format-enforcer 0.11.3.

Use the library's public core API: its released Transformers integration
imports a tokenizer class from a path removed in Transformers 5. This adapter
does not import or patch Transformers internals. Tokenizer preprocessing
follows the upstream integration and is cached once per engine/tokenizer.
"""
import hashlib
import json


def schema_fingerprint(schema):
    return hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def tokenizer_data(tokenizer):
    from importlib.metadata import version
    if version('lm-format-enforcer') != '0.11.3':
        raise ValueError('structured decoding requires lm-format-enforcer 0.11.3')
    from lmformatenforcer import TokenEnforcerTokenizerData
    zero = tokenizer.encode('0', add_special_tokens=False)[-1]
    special_ids = set(tokenizer.all_special_ids)
    regular = []
    for token_id in range(len(tokenizer)):
        if token_id in special_ids:
            continue
        after_zero = tokenizer.decode([zero, token_id], clean_up_tokenization_spaces=False)[1:]
        standalone = tokenizer.decode([token_id], clean_up_tokenization_spaces=False)
        regular.append((token_id, after_zero, len(after_zero) > len(standalone)))

    def decode(ids):
        return tokenizer.decode(ids, clean_up_tokenization_spaces=False).rstrip('\ufffd')

    return TokenEnforcerTokenizerData(regular, decode, tokenizer.eos_token_id, False, len(tokenizer))


def prefix_filter(data, schema, prompt_width):
    from lmformatenforcer import JsonSchemaParser, TokenEnforcer
    # A fresh parser/enforcer for each completion prevents prior conversation
    # and prior role state from leaking into the constrained output state.
    enforcer = TokenEnforcer(data, JsonSchemaParser(schema))
    enforcer.get_allowed_tokens([])

    def allowed(batch_id, token_ids):
        if batch_id != 0:
            raise ValueError('structured agent generation supports batch size one')
        generated = token_ids.tolist()[prompt_width:]
        tokens = enforcer.get_allowed_tokens(generated).allowed_tokens
        if not tokens:
            raise ValueError('response schema has no valid next token')
        return tokens

    return allowed
