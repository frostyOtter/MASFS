# MASFS — Agile Milestones for a Multi-Agent System from Scratch (v4)

**Conversation prefix:** `MASFS`
**Inputs:**
- `MASFS-hermes-agent-mas-research-findings.md`
- Hermes concurrency notes (user-provided)
- `MASFS-agile-milestones.md` v1 and v2

**Goal:** Learn by rebuilding Hermes' agent loop and a selected set of its delegation features—including nested orchestrators, steering, output schemas, lifecycle contracts, profiles, and its hybrid concurrency model. Start from a terminal chatbot and grow it in thin, demonstrable slices.

**Track boundary:** M1–M9 are the **core learning track** and form a complete project. M10–M16 are an **optional advanced track** for selected Hermes delegation features, not full framework parity.

**Purpose:** Learning only. Production surface (fallback chains, gateways, plugins, caching) stays out on purpose.

## 0. What changed

| Version | Change | Why |
|---|---|---|
| v2 | M0 merged into M1; tools before persistence; `tasks=[...]` from M4; hardening dissolved into milestones; lifecycle and background split; R5 parity release | Functions-first style, full parity, fewer schema changes |
| **v3** | **The asyncio-everywhere decision is reversed.** The core loop is synchronous, children run on daemon worker threads, and asyncio lives only in host surfaces. | Mirrors Hermes (concurrency notes) |
| **v3** | **New M8: async host surface.** An async API host calls the sync loop through `asyncio.to_thread` and bridges completions from worker threads to the event loop. | Covers the third part of Hermes' hybrid model |
| **v3** | Custom daemon submission in M4 and a bounded daemon pool in M5. | Hermes' `tools/daemon_pool.py` |
| v3 | Cancellation uses `threading.Event` interrupt flags instead of `task.cancel()`. | Python threads cannot be killed from outside. |
| v3 | Milestones renumbered: capstone checkpoint is M9, advanced work is M10–M16. | Makes room for M8 |
| **v4** | M1–M9 declared the complete core track; M10–M16 made optional and renamed from “parity” to selected features. Timeout settlement, executor layering, host cancellation, fallback metadata, and thread budgets are explicit. | Prevents scope inflation and closes thread-lifecycle ambiguities |

## 1. Concurrency architecture (mirrors Hermes)

### 1.1 The three layers

| Layer | Mechanism | Hermes reference |
|---|---|---|
| Agent loop, tool execution, provider calls | **Synchronous** Python; sync `openai.OpenAI(base_url=...)` client | Core `AIAgent` loop |
| Parallel and background child agents | **OS threads**: `DaemonThreadPoolExecutor` plus `concurrent.futures.Future` | `delegate_tool_dispatch.py`, `delegate_tool_child_run.py`, `async_delegation.py`, `subagent_lifecycle.py` |
| Network hosts (API, WebSocket) | **asyncio**, calling the loop via `asyncio.to_thread(...)` | `gateway/run.py`, `web_routers/sessions.py`, `auxiliary_client.py` |

Two naming notes:
- Children are **not** processes and **not** `asyncio.Task`s.
- "Async delegation" in Hermes means *detached from the parent's turn*, not *asyncio*.

### 1.2 Why Hermes is built this way

Rows marked **documented** come from the concurrency notes. Rows marked **inferred** are engineering reasoning you should verify against the Hermes source as you go.

| Decision | Reason | Basis |
|---|---|---|
| Sync core loop | One loop serves every host. A sync function can be called from sync hosts (CLI, batch, one-shot) and from async hosts via `to_thread`. An `async def` loop could not be called from sync code without starting an event loop, a problem known as "function colouring." | Inferred |
| Sync core loop | Tools are often blocking (files, subprocesses, sync SDKs). A sync loop calls them directly with no wrapping. | Inferred |
| Threads for children | A child *is* the sync loop, so running sync code in parallel requires threads. The work is I/O-bound (waiting on the model API), and CPython releases the GIL while blocked on network I/O, so threads overlap well. | Inferred |
| **Daemon** threads | Python's normal executor waits for workers at shutdown, so one wedged child could stop the process from exiting. Daemon workers avoid that. | Documented (`daemon_pool.py`) |
| `contextvars` propagation | Plain `ThreadPoolExecutor` workers do **not** inherit `contextvars`. Anything stored there, such as loguru `contextualize` IDs, would silently vanish in children. | Documented (`daemon_pool.py`); loguru detail inferred |
| Child built on the main thread, run on a worker | Constructing an agent is not thread-safe. | Documented (findings §5.5) |
| One-worker executor around each child run | Makes `future.result(timeout=...)` possible, giving a child timeout without killing a thread. | Documented (`delegate_tool_child_run.py`); purpose inferred |
| Shared process-wide pool for background work | Bounds total detached work across all parent turns. | Documented (`async_delegation.py`) |
| asyncio in hosts | Hosts must hold many idle connections (WebSockets, messaging platforms). Async-native libraries handle that cheaply. | Documented (usage); reason inferred |

### 1.3 Rules that follow from threads

1. **Threads cannot be cancelled from outside.** Cancel, timeout and steering are **cooperative**. Each child has a `threading.Event` interrupt flag. The loop checks it before every model call and before every tool call.
2. **A timeout does not stop the thread.** When `future.result(timeout=...)` fires, mark the child `timed_out`, set its interrupt flag, and **defer cleanup** until the thread actually returns.
3. **Shared mutable state needs locks.** Registry maps are guarded by a `threading.Lock`. Each child writes its own session file, so there is no writer contention.
4. **Pass data across threads through thread-safe channels.** Use `queue.Queue` and `concurrent.futures.Future`, never bare lists.
5. **Copy context on submit.** Use `contextvars.copy_context().run(fn, ...)` inside the pool's `submit`.
6. **Never block the event loop in async hosts.** Every call into the core goes through `asyncio.to_thread`. Results from worker threads reach the loop via `loop.call_soon_threadsafe(...)`.
7. **Avoid nested pool starvation.** An orchestrator that waits on its own children must not borrow workers from a bounded pool its children also need. Foreground delegation therefore gets its own executor per call (M13).
8. **Separate logical termination from physical settlement.** A task can be terminal (`timed_out` or `cancelled`) while its worker is still unwinding. The first terminal result wins, late completion cannot overwrite it, and deferred cleanup runs when the worker settles.
9. **Budget threads as well as tasks.** Foreground child workers, detached workers, lifecycle workers, and total tree nodes have separate configured limits and tests.

## 2. Other locked decisions

- **Python ≥ 3.14**, matching Hermes.
- **One real provider**: a third-party OpenAI-compatible endpoint through the sync `openai.OpenAI(base_url=..., api_key=...)` client, plus a scripted fake model for all tests.
- **Canonical messages use the OpenAI Chat Completions shape.** Requests are sent from a copy, so canonical history is never mutated (findings §3.4).
- **Functions first.** Data is `TypedDict` or `@dataclass(frozen=True)`. The first classes are the daemon pool (M5) and the lifecycle registry (M6).
- **Logging:** `loguru.logger` behind a small project-owned logging adapter, using `logger.contextualize(session_id=..., turn_id=..., task_id=...)`; context is propagated to workers via `contextvars`. Runtime contracts must not depend on Loguru-specific objects.
- **Persistence:** append-only JSONL, one file per session. The header holds `session_id`, `parent_session_id` and `profile`. Through M9, JSONL stores canonical transcripts while lifecycle/background registries remain process-local and in memory; do not add a second persistence system unless the optional track demonstrates a concrete need.
- **Tools:** safe in-process tools only. No shell or filesystem-write tools, so no approval UI.

## 3. Delivery rules and Definition of Done

**Delivery rules**
1. Every milestone produces a runnable demo.
2. The same `run_conversation` loop runs for parents, orchestrators and leaves, in every host.
3. Canonical history is authoritative.
4. The host decides admission, scheduling, roles, capabilities and cancellation.
5. Children return bounded result contracts, never transcripts.
6. Capabilities only narrow down the tree. Roles derive from depth.
7. Every autonomous dimension is bounded.
8. There is no hardening sprint. Failure tests ship with each feature.

**Definition of Done**
- Acceptance criteria pass with the fake model. Live-provider runs are opt-in.
- Unit tests plus one integration test.
- A documented demo command.
- The §5 invariants hold.
- Earlier demos still work.
- Deferrals are written down.

---

## 4. Roadmap

### Core learning track — complete at M9

### R1 — Chat

#### M1 — Sync chatbot walking skeleton

**Outcome:** A multi-turn terminal chat with the real provider. All tests run offline against the fake model.

**Scope**
- Minimal types: `Message`, `Usage`, `ModelResponse(text, tool_calls, finish_reason, usage)`, and `TurnResult(final_response, messages, status, error, usage)`.
- The model as a plain callable: `ModelFn = Callable[[list[Message], list[dict]], ModelResponse]`.
- Two factories: `make_fake_model(script)` and `make_openai_model(base_url, api_key, model)`, the latter using the sync client.
- `run_turn(history, user_text, model) -> TurnResult`:
  1. Append the user message.
  2. Build a request copy.
  3. Call the model.
  4. Append the assistant reply.

  A failed turn is closed with an assistant boundary.
- Sync REPL with `/new` and `/exit`.
- Request timeout, normalized provider errors, and credentials from the environment only.
- **Provider probe script.** Record in `docs/provider.md` whether your endpoint supports:
  - `tool_calls`
  - several tool calls in one response
  - `usage` reporting
  - JSON-schema `response_format`

**Acceptance:** Five turns in order. The request copy never mutates history. A provider error leaves history valid.
**Size:** Small–medium.

### R2 — Agent

#### M2 — Tool-calling loop (in memory)

**Outcome:** The agent calls safe tools and answers from their results.

**Scope**
- `ToolSpec(name, toolset, schema, handler)`, with the registry as a plain `dict[str, ToolSpec]`.
- `tool_definitions(registry, enabled_toolsets)` builds the model-facing schemas, snapshotted once per agent (findings §4.2).
- A bounded loop that alternates model calls and tool rounds until the model returns text or the iteration budget runs out.
- A never-raising executor with **exactly one result per call**. It handles an unknown tool, bad JSON, a disabled tool (rejected at dispatch too), a handler exception, and a call skipped because the budget ran out.
- An `interrupt: threading.Event` parameter, checked before each model call and each tool call. Nothing sets it yet; M4 will.
- Demo tools: `calculator` and `current_time`.
- *Deferred:* per-tool timeouts. The demo tools are instant, and the same timeout mechanism arrives in M4.

**Acceptance:** Every failure kind yields a matched result. A disabled tool is absent from the schemas and rejected at dispatch. Budget exhaustion terminates predictably.
**Size:** Medium–large.

#### M3 — Durable sessions and turn boundaries

**Scope**
- JSONL store with create, append, list, load and delete.
- Turn states: `started`, `completed`, `failed`.
- **Persist the assistant tool-call row before running any handler**, then persist each result as it arrives (findings §4.3).
- **Resume repair:** unanswered calls get a result saying "interrupted, outcome unknown."

**Acceptance:** Kill the process mid-tool, resume, and the transcript is valid. Sessions are isolated from each other.
**Size:** Medium.

### R3 — MAS

#### M4 — Single child on a daemon thread

**Outcome:** The parent delegates one task to an isolated child running on a worker thread, with a real timeout and interrupt.

**Scope**
- A `delegate_task` schema taking `tasks: [{goal, context}]`, capped at one item for now.
- Contracts: `ChildRequest` and `ChildResult(task_index, status, exit_reason, summary, error, usage, duration_s, api_calls)`.
- `build_child(parent, request, depth)` runs **on the calling thread**. It creates:
  - a new session linked by `parent_session_id`
  - a goal-and-context-only system prompt
  - a fresh iteration budget
  - no memory and no clarification ability
  - its own interrupt `Event`
- The child role is derived from depth. With `max_spawn_depth = 1`, the only observable role in this milestone is `leaf`; the orchestrator branch is introduced in M13.
- **Concurrency primitive, function-first:** `submit_daemon(fn, *args) -> Future`. It starts one `threading.Thread(daemon=True)` running under `contextvars.copy_context()` and fills a `concurrent.futures.Future`. This is a per-child future boundary, not yet a reusable batch pool.
- **Timeout:** `future.result(timeout=child_timeout)`. On expiry, atomically publish the one terminal `timed_out` result, set the child's interrupt, and defer cleanup through `future.add_done_callback`. Track worker settlement separately; a late return may settle resources but must never replace the published timeout result.
- Summaries are bounded by a static cap with head-plus-tail truncation. Child usage rolls up to the parent.

**Acceptance:**
- The child's tools are a subset of the parent's.
- No parent history leaks into the child.
- A child exception becomes a `ChildResult`.
- A timed-out child stops at its next checkpoint, and its cleanup runs.
- Log lines emitted on the worker thread carry the parent's `turn_id`, proving context propagation.

**Size:** Large.

#### M5 — Bounded parallel delegation with a daemon pool

**Scope**
- Promote `submit_daemon` to a small project-owned `DaemonThreadPoolExecutor(max_workers)` built from public primitives (`queue.Queue`, `threading.Thread`, and `Future`): daemon workers, context propagation, and `submit(...) -> Future`. Do not depend on CPython's private `concurrent.futures.thread._worker` internals.
- Preserve two distinct layers: the per-delegation **batch executor** bounds children running in parallel, while each child's future/settlement state preserves timeout, first-terminal-result, and deferred-cleanup semantics from M4.
- Build all children first on the parent thread, then submit them, one executor per delegation call. The worker count equals `max_concurrent_children`, whose Hermes default is 10.
- Collect with `concurrent.futures.wait` and sort by `task_index`. Partial success is explicit.
- Each child run is wrapped so all exceptions become terminal child results at the orchestration boundary. Unexpected exceptions are also logged with traceback and may fail tests in an explicit debug mode, but never leave a missing result.
- Parent interrupt sets every child's `Event`, and each child records `cancelled` at its next checkpoint.
- A dynamic summary budget: `min(static_cap, parent_headroom / batch_size)`.
- Add and test separate limits for foreground child workers, detached child workers, lifecycle workers, and total children per parent turn.

**Acceptance:**
- Three fake children with delays overlap, proven by timestamps.
- The number of active workers never exceeds the cap.
- Reversed completion order still aggregates correctly.
- Interrupting mid-batch makes every child terminal.
- The process exits promptly even with a deliberately wedged child.

**Size:** Large.

### R4 — Operable MAS

#### M6 — Child lifecycle registry

**Scope**
- A child record with a state machine: `queued → running → completed | failed | cancelled | timed_out`.
- A registry class guarded by a `threading.Lock`, with `launch`, `status`, `wait(timeout)`, `cancel` and `result`. The registry manages process-local child handles whether or not a caller waits immediately; M7 adds detached completion delivery to parent turns.
- Track logical terminal state separately from internal `worker_settled`/cleanup state. State transitions are first-writer-wins, so late worker completion cannot replace `cancelled` or `timed_out`.
- Opaque UUID handles.
- A heartbeat timestamp written by the child thread and read by the registry, plus stale detection.
- Terminal records retained for about an hour.
- `delegate_task` gains `action=list|stop`. The REPL gains `/agents` and `/stop <id>`.

**Acceptance:**
- Concurrent status reads and writes pass a stress test with no torn records.
- Cancel is idempotent.
- `result` returns `NOT_READY` before the child is terminal.

**Size:** Medium.

#### M7 — Background delegation (detached, still threaded)

**Scope**
- A **process-wide shared** daemon pool for detached work (findings §5.7; `async_delegation.py`).
- Top-level delegation returns a dispatch handle immediately.
- Completions go into a thread-safe `queue.Queue`. The sync REPL drains it **only between turns**, before showing the next prompt, and injects each completion as a new message.
- If there is no delivery channel or the detached pool is full, policy chooses either bounded foreground fallback or explicit rejection. The returned metadata must state which path was selected; fallback obeys the same child/thread limits and, from M8 onward, never runs on the event-loop thread.
- `/new` and `/exit` interrupt the tree.
- The CLI states that background work is process-local.

**Acceptance:** You can chat while a slow child runs. A completion never enters an in-flight request.
**Size:** Large.

#### M8 — Async host surface (asyncio bridge)

**Outcome:** The same core runs behind an async network host, which exercises the third part of Hermes' concurrency model.

**Scope**
- A minimal async API (FastAPI or aiohttp; see open question):
  - `POST /sessions/{id}/messages` calls `await asyncio.to_thread(run_conversation, ...)`.
  - `GET /sessions/{id}`.
  - A WebSocket (or SSE) stream for background completions.
- A per-session `asyncio.Lock`, so at most one turn per session runs at a time.
- Every hosted turn owns a `threading.Event`. HTTP/WebSocket disconnect or coroutine cancellation sets it; cancelling the awaiting `asyncio.Task` is never assumed to stop the thread. The core checks the event at model/tool boundaries, and a late worker return cannot commit to a retired session generation.
- **Thread-to-loop bridge:** worker threads publish completions with `loop.call_soon_threadsafe(async_queue.put_nowait, item)`.
- Graceful shutdown that interrupts active trees and does not wait on wedged daemon workers.
- Optional: an `async_model(...)` wrapper, `await asyncio.to_thread(sync_model, ...)`, mirroring `auxiliary_client.py`.

**Acceptance:**
- Two sessions run turns concurrently while a health endpoint stays responsive, proving the loop never blocks.
- Cancelling or disconnecting an async request sets the core interrupt without pretending the worker thread was killed; late completion cannot mutate a retired session.
- Background completions reach the WebSocket client.
- REPL behaviour is unchanged. One core, two hosts.

**Size:** Medium–large.

#### M9 — Core capstone and baseline

**Scope**
- One workflow, for example three independent reviewers of local documents followed by a synthesis.
- Compare a single agent against the flat MAS on quality (rubric), latency and tokens.
- A retrospective that decides whether to stop with a complete core project or orders the optional advanced track.

**Core completion:** Meeting M9 acceptance criteria is a valid endpoint for MASFS; M10–M16 are not required to claim completion of the learning project.

**Size:** Medium.

### Optional advanced track — selected Hermes delegation features

### R5 — Selected Hermes Delegation Features

#### M10 — Result-delivery parity

**Scope**
- Oversized summaries spill to `~/.masfs/delegation_cache/`, and the parent receives head, tail, path and paging instructions.
- A read-only `read_spill` tool confined to that directory.
- `independent_completions` and `group` fields. Grouping changes delivery units, not dependencies.
- Live transcript paths are returned as an observability side channel only.

**Size:** Medium.

#### M11 — Steering

**Scope**
- `action="steer"` with a per-child `queue.Queue`.
- The child thread drains the queue only at iteration boundaries.
- Steering a terminal child returns a structured rejection.

**Acceptance:** A steer never lands mid-request.
**Size:** Medium.

#### M12 — Output schemas

**Scope**
- A per-task `output_schema`, validated with `jsonschema`.
- Bounded correction retries.
- `ChildResult` gains `schema_valid` and `parsed`.
- Provider structured output only if the M1 probe supports it.

**Size:** Medium.

#### M13 — Nested orchestrators

**Scope**
- A child is an orchestrator if `orchestrator_enabled and child_depth < max_spawn_depth`. Only orchestrators get `delegate_task`.
- Nested children are joined **synchronously** inside the orchestrator's worker thread (findings §5.7).
- **Starvation rule:** nested foreground delegation creates its own executor. It never borrows from a bounded pool that its ancestors are blocking on.
- Interrupts propagate down the tree through linked `Event`s.
- Usage rolls up recursively.
- *Learning addition:* a total-node cap for the whole tree.

**Acceptance:**
- A depth-3 tree completes with no deadlock under a small worker count.
- A leaf told it is an orchestrator still cannot delegate.
- Interrupting the root makes every node terminal.

**Size:** Large.

#### M14 — Lifecycle API contracts

**Scope**
- A plugin-facing service with its own **8-worker** daemon pool (`subagent_lifecycle.py`).
- Frozen contracts:
  - `SubagentLaunchRequest`
  - `SubagentHandle`
  - `SubagentStatus`
  - `SubagentTerminalState`
  - `SubagentCancelResult`
  - `SubagentResult`
  - `SubagentReconnectResult`
- Handles signed with a process-local HMAC key and scoped to the parent session.
- `reconnect` fails cleanly after restart.
- Launch requests are validated so their toolsets are a subset of the parent's.
- The async host can call this service through `to_thread`.

**Size:** Medium.

#### M15 — Profiles (persistent named agents)

**Scope**
- `~/.masfs/profiles/<name>/` holds `config.toml`, `sessions/`, a minimal `memory.md` and optional `skills/`.
- A `--profile` flag for both hosts.
- Children skip memory. The parent's memory receives a delegation-outcome note.

**Acceptance:** Profiles share no state.
**Size:** Medium.

#### M16 — Final capstone and retrospective

**Scope**
- Compare single agent, flat MAS and nested MAS on quality, latency and tokens, via both hosts.
- Check the §7 exit criteria.

**Size:** Medium.

---

## 5. Invariants checked after every run

- Message order is valid, and every tool call has **exactly one** result.
- Canonical history contains no request-local decorations.
- Every child reaches exactly one logical terminal state. A timed-out or cancelled worker may settle later, but settlement cannot overwrite its terminal result and deferred cleanup occurs once.
- Child tools are a subset of the parent's tools minus the blocked set, and the role matches depth.
- `task_index` and `task_id` are unique, and association is stable.
- Configured limits bound foreground workers, detached workers, lifecycle workers, children per turn, and total tree nodes.
- Steering is applied only at iteration boundaries.
- Log records from worker threads carry the parent's correlation IDs.
- The event loop never runs core-loop code directly (M8 onward).
- Handles are unforgeable (M14 onward), and profiles are isolated (M15 onward).

## 6. Hermes features intentionally not reproduced

Multi-provider fallback, prompt-cache layout, multimodal history, credential pools, middleware and plugin discovery, approvals and sandboxing, messaging gateways, worktrees, cron and kanban durable work, and MoA.

**Stretch options:** streaming, context compression, and parallel tool calls within one round.

## 7. Exit criteria

1. One synchronous loop runs the parent, orchestrators and leaves, from both a sync host and an async host.
2. Child parallelism uses daemon worker threads with context propagation, cooperative interrupts and timeouts that never hang process exit.
3. The async host never blocks its event loop, and completions cross the thread-to-loop boundary safely.
4. Canonical state stays valid through failures, interrupts and restarts.
5. Isolation holds, capabilities narrow, and roles derive from depth.
6. Every autonomous dimension is bounded, with no nested-pool deadlock.
7. Background work is observable, steerable and cancellable within its process lifetime.
8. Profiles provide persistent identity.
9. Single, flat and nested runs are compared honestly.

## 8. Open questions

1. Which provider and model? This determines the M1 probe and M12 structured output.
2. FastAPI or aiohttp for M8? FastAPI is quicker to learn; aiohttp stays closer to raw asyncio.
3. How much memory should profiles have in M15?
4. What should the capstone domain be (M9 and M16)?
5. After M9, does an advanced feature demonstrate enough need for SQLite lifecycle/delivery metadata, or should those records remain process-local?