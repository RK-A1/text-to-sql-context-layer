"""One LiteLLM call. Returns (assistant_message, meta).

The assistant message is OpenAI-shaped and goes straight back into the history. Cost is
OpenRouter's billed figure (usage.cost) when present, otherwise LiteLLM's estimate.
"""

import time

import litellm

from .config import MAX_TOKENS

litellm.suppress_debug_info = True


def call(model, messages, tools):
    extra_body = {"usage": {"include": True}} if model.startswith("openrouter/") else None
    start = time.perf_counter()
    resp = litellm.completion(model=model, messages=messages, tools=tools, max_tokens=MAX_TOKENS,
                              extra_body=extra_body, num_retries=2, timeout=300)
    latency = time.perf_counter() - start

    msg, usage = resp.choices[0].message, resp.usage
    litellm_cost = resp._hidden_params.get("response_cost")
    provider_cost = getattr(usage, "cost", None)
    cost = float(provider_cost) if provider_cost is not None else litellm_cost

    assistant = {"role": "assistant", "content": msg.content or None}
    if msg.tool_calls:
        assistant["tool_calls"] = [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls]
    reasoning = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None)
    meta = {
        "served_model": resp.model,
        "finish_reason": resp.choices[0].finish_reason,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": reasoning,
        "cost_usd": round(cost, 6) if cost is not None else None,
        "cost_source": "provider" if provider_cost is not None else ("litellm" if cost is not None else "unknown"),
        "latency_s": round(latency, 2),
    }
    return assistant, meta
