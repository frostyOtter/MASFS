# Release log

## 0.1.0 — Milestone 1: synchronous chatbot

The first runnable MAS Kraken milestone: an in-memory, multi-turn terminal chatbot backed by one OpenAI-compatible provider.

### Delivered

- Synchronous conversation turn with canonical OpenAI-style messages, deep-copied provider requests, usage reporting, and an assistant boundary on failure.
- Scripted offline fake model and synchronous OpenAI-compatible adapter with normalized responses and safe provider errors.
- REPL with `/new`, `/exit`, `Assistant:` replies, and a separator after each reply.
- Environment and `.env` startup configuration, request timeout, and explicit logging configuration.

### Verification

- Offline suite: **27 passed** (`python -m pytest -q`).
- Pyright: **0 errors** for `src/mas_kraken` with Python 3.14.
- Live provider behavior has not been verified here; the endpoint capability probe (tool calls, multiple calls, usage, and JSON-schema response format) remains outstanding.

### Boundaries and next steps

No tool execution, durable sessions, delegation, background work, or async host yet. Tool execution and the bounded model/tool loop are planned for M2. Model-returned tool calls are rejected by the M1 turn loop rather than silently ignored.
