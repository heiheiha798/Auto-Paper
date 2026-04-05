# AI Infra Paper Filter Plan

This document is the reading policy, not the workflow spec.

## Prioritize

- LLM serving
- edge and on-device deployment
- runtime and compiler systems
- scheduling, batching, memory, and kernel optimization
- distributed inference
- quantization and low-latency inference

This is a soft reading preference, not a hard gate.
If a paper has a genuinely novel idea or a paper-worthy direction, it can still enter full reading even when it is not primarily about acceleration.

## Retrieval Rule

- Fetch only the approved `cs` categories at retrieval time and treat the allowlist as a hard fence.
- Do not hardcode infra-only filters beyond the category hard fence.
- Let Codex decide whether an algorithmic paper is infra-relevant, including cases like speculative decoding or other inference-speedup work.

## Triage Rule

- Use a 6-point scale.
- Make the strongest reasonable baseline the main scoring reference.
- Give extra credit when a paper has a genuinely novel idea or a paper-worthy new direction, but keep novelty tied to technical substance and evidence.
- Boost explicit systems claims and production evidence.
- Penalize vague framework papers, benchmark-only work, or pure algorithm papers with no deployment angle.
- `skip` only when a paper is clearly off-scope, thin, or malformed.
- If uncertain, default to `skim`.
- The final daily digest should be Chinese-first. Preserve English technical terms in English, especially `token`, `MoE`, `KV cache`, and `speculative decoding`.
- Include score-4 and score-5 papers in the final digest.

## Summary Fields

Use concise, source-grounded summaries with:

- `one_sentence_summary`
- `why_it_matters_for_infra`
- `main_idea`
- `key_mechanism`
- `evaluation_setup`
- `limitations`
- `quote_or_evidence`

## Router Rule

- Use a manifest plus LLM routing for custom TeX trees.
- Keep deterministic filters only for obvious binaries and build artifacts.
- Prefer skipping over guessing when routing confidence is low.
