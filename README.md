# MAS Kraken

A from-scratch learning project that starts with a synchronous terminal chatbot and grows toward a multi-agent system. The core idea is one reusable conversation loop: model requests use a copy of canonical history, while failures close the turn cleanly. A scripted fake model supports offline development; a synchronous OpenAI-compatible adapter supports live chat. Tools and delegation are planned for later milestones, not part of M1.

## Start the app

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/). Create a `.env` in the project directory (or export the variables):

```dotenv
MASFS_BASE_URL=https://your-openai-compatible-endpoint/v1
MASFS_API_KEY=your-api-key
MASFS_MODEL=your-model
# MASFS_REQUEST_TIMEOUT=30
# MASFS_LOG_LEVEL=INFO
```

Then run:

```sh
uv sync
uv run python -m mas_kraken
```

Type messages to chat. `/new` starts a fresh conversation; `/exit` quits. The app loads `.env` from the current working directory, overriding variables already set in the environment.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the Milestone 1 release log and verification status.

### 0.1.0 — Milestone 1: synchronous chatbot (current)

**Supported:** Multi-turn terminal chat with one OpenAI-compatible provider; `/new` and `/exit`; environment-based configuration and request timeout; normalized provider errors and closed failed turns; a scripted fake model for offline checks. Canonical history is kept in memory and provider requests use a copy.

**Not yet supported:** Tool execution (including returned tool calls), session persistence or resume, child agents and delegation, background work, and an async/API host. These belong to later milestones.
