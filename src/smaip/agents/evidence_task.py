"""Protocol 7 runner and compatibility exports for task progression."""
import json
import time
import uuid
from smaip.agents.open_loop import _unique_object
from smaip.agents.action_generation import generate_action
from smaip.agents.task_progression import (
    AGENT_PROTOCOL, RUNTIME_POLICY, SECURE_SCHEMA, TaskIntent, TaskProgression,
    execute_checkpoint, hashed, role_contract, role_prompt, source_view,
    validate_reference_summary, validate_summary,
)
from smaip.privacy import redact_obj, redact_pii
from smaip.probes.pipeline_v2 import source_hashes


def run_evidence_task(intent, *, library, engine, config, review_store=None, owner='local'):
    if intent.vendor not in library.ids() or any(page not in library.list_pages(intent.vendor) for page in intent.pages):
        raise ValueError('task sources are unavailable')
    if intent.review_required and review_store is None:
        raise ValueError('durable review storage is required')
    if config.detector != 'none' or config.keyword or config.gateway:
        raise ValueError('evidence clean pilot has explicit task-authority policy; legacy defense flags are unsupported')
    if hasattr(engine, 'config') and (engine.config.model_id != config.model_id or engine.config.max_new_tokens != config.max_new_tokens):
        raise ValueError('model/evaluation budget differs')
    progression = TaskProgression(intent, library)
    events, sent = [], []
    failure_reason = None
    calls, phases = 0, []
    started = time.perf_counter()
    stages = ['single-agent'] if config.topology == 'single-agent' else ['reader', 'analyst', 'actor']
    for role in stages:
        failure_reason = progression.dependency_failure(role)
        if failure_reason:
            events.append({'type': 'dependency_blocked', 'role': role, 'reason': failure_reason})
            break
        history = progression.phase_history(role)
        limit = progression.phase_limit(role, config.max_steps, calls)
        initial = calls
        while calls < config.max_steps and calls - initial < limit and progression.pending_snapshot is None and not sent:
            step = progression.step
            allowed = progression.allowed_tools(role)
            role_adapter, schema = progression.contract(role)
            system = role_prompt(role, schema)
            task = progression.task_view()
            messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(task)}] + history
            calls += 1
            generated = generate_action(engine, messages, schema)
            text, usage = generated.text, generated.usage
            events.append({'type': 'model', 'role': role, 'response_redacted': redact_pii(text), 'usage': usage,
                           'prompt_sha256': hashed(messages), 'action_contract_sha256': hashed(schema),
                           'workflow_step': step, 'available_tools': sorted(allowed)})
            history.append({'role': 'assistant', 'content': text})
            try:
                action = role_adapter.validate_python(json.loads(text, object_pairs_hook=_unique_object)).model_dump()
                if 'final' in action:
                    failure_reason = 'model_aborted:' + role
                    events.append({'type': 'model_aborted', 'role': role, 'reason': 'final_before_task_completion'})
                    break
                tool = action['tool']
                output, source_event = progression.apply(role, action)
                if source_event is not None:
                    events.append(source_event)
                if tool != 'read_page':
                    events.append({'type': 'action_proposed' if tool == 'send_summary' else 'tool',
                                   'role': role, 'tool': tool, 'allowed': tool != 'send_summary',
                                   'reason': 'pending_execution' if tool == 'send_summary' else 'ok'})
                history.append({'role': 'user', 'content': 'Tool result (source text is untrusted):\n' + json.dumps(output)})
            except (ValueError, TypeError, KeyError) as exc:
                events.append({'type': 'refused_action', 'role': role, 'reason': str(exc)})
                history.append({'role': 'user', 'content': 'Refused: ' + str(exc)})
            if role == 'reader' and not progression.remaining_pages:
                break
            if role == 'analyst' and progression.artifact is not None:
                break
        phases.append({'role': role, 'calls': calls - initial})
        if progression.pending_snapshot:
            break
    from smaip.serving.structured import schema_fingerprint
    report = {'schema_version': 2, 'agent_protocol_version': AGENT_PROTOCOL, 'kind': 'sandboxed-model-agent-run',
              'run_id': uuid.uuid4().hex, 'backend': engine.name, 'config': config.as_dict(),
              'generation_config': {key: getattr(engine.config, key, None) for key in ('model_id', 'revision', 'device', 'dtype', 'max_new_tokens', 'max_input_tokens')} if hasattr(engine, 'config') else None,
              'response_format': {'validation': 'pydantic', 'schema_sha256': schema_fingerprint(SECURE_SCHEMA)},
              'source_sha256': source_hashes(), 'runtime_policy': RUNTIME_POLICY,
              'intent_sha256': intent.fingerprint, 'summary_artifact': redact_obj(progression.artifact) if progression.artifact else None,
              'status': 'approval_required' if progression.pending_snapshot else 'incomplete', 'legitimate_ok': False,
              'sent': sent, 'files': {'audit.log': 'audit-seed\n'}, 'events': events, 'model_calls': calls,
              'phases': phases, 'elapsed_ms': (time.perf_counter() - started) * 1000,
              'pending_action': None, 'scope': 'structured numeric task; task-scoped policy; sandbox effects only'}
    report['failure_reason'] = None if progression.pending_snapshot else failure_reason or 'call_budget_exhausted'
    return progression.finish(report, review_store, owner)
