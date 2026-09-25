# Hermes Agent MAS Research Findings

**Source inspected:** `hermes-agent/` only  
**Repository state:** `main` at `ff8c8f023b12db0694a6c42abf68f1bf6167836a` (`fix(desktop): rebuild a packaged app whose node-pty has no native binary`)  
**Framework version:** `0.21.4`  
**Python requirement:** `>=3.11,<3.14`  
**Research term:** multi-agent system (MAS), starting from a chatbot  
**Scope of this document:** findings and execution mechanics only. Agile milestones are intentionally not defined yet.

## 1. Executive findings

Hermes is organized around one reusable, stateful `AIAgent` rather than separate agent implementations for each user interface. CLI, TUI, desktop, gateway/messaging, API-server, ACP, one-shot, and batch paths construct the same core object and call the same turn method.

The smallest usable chatbot abstraction is:

```python
from run_agent import AIAgent

agent = AIAgent(
    provider="...",
    model="...",
    base_url="...",
    api_key="...",
    enabled_toolsets=[],
)
reply = agent.chat("Hello")
```

`chat()` is only a convenience wrapper. The actual application boundary is `run_conversation(...)`, whose result includes the final answer, updated message history, completion/error state, usage information, and turn-boundary metadata.

Hermes' MAS implementation is not a shared-memory swarm. Delegation creates isolated child `AIAgent` instances. The parent sends each child a self-contained goal and context. A child returns a bounded final summary/result; its private reasoning and intermediate tool traffic do not enter the parent's prompt. Parallelism is explicit, bounded, and mediated by a host-owned lifecycle.

The architecture therefore separates into five mechanical layers:

1. **Agent construction** — resolve provider, model, callbacks, tools, session state, memory, and context policy.
2. **Turn loop** — assemble a request, call the model, normalize the response, execute tools, and repeat until text completion or a terminal condition.
3. **Tool runtime** — expose JSON schemas to the model, validate calls, dispatch handlers, and append normalized results to the transcript.
4. **Delegation runtime** — construct isolated child agents, run them synchronously or in background workers, aggregate bounded results, and re-enter them into the parent session.
5. **Host surfaces** — CLI, gateway, API, and other adapters provide transport, persistence, callbacks, and delivery semantics without replacing the core loop.

## 2. File-to-role map

### Core chatbot and turn execution

| File | Role |
|---|---|
| `hermes-agent/run_agent.py` | Public facade. Defines `AIAgent`, forwards initialization to `agent.agent_init.init_agent`, and exposes mixin-backed runtime methods. |
| `hermes-agent/agent/agent_init.py` | Ordered construction pipeline: routing, callbacks, client, tools, session, memory, compression, and context engine. |
| `hermes-agent/agent/turn_facade.py` | Public turn facade. `chat(message)` returns `run_conversation(...)["final_response"]`. |
| `hermes-agent/agent/conversation_loop.py` | Main synchronous turn state machine and retry-loop coordinator. |
| `hermes-agent/agent/turn_context.py` | Creates per-turn state, user-message boundaries, API-visible context, and exported turn metadata. |
| `hermes-agent/agent/turn_iteration_prep.py` | Starts and prepares each model/tool iteration. |
| `hermes-agent/agent/turn_request_assembly.py` | Builds the provider request copy, applies context selection and sanitization, canonicalizes cacheable content, and measures context pressure. |
| `hermes-agent/agent/turn_preflight_gate.py` | Applies pre-call context/compression gates. |
| `hermes-agent/agent/turn_api_request.py` | Builds provider-specific request arguments. |
| `hermes-agent/agent/turn_api_call.py` | Executes streaming or non-streaming provider calls through middleware and interrupt handling. |
| `hermes-agent/agent/turn_api_error.py` | Classifies and recovers from provider failures, including fallback behavior. |
| `hermes-agent/agent/turn_response_intake.py` | Normalizes provider responses into the loop's assistant-message representation. |
| `hermes-agent/agent/turn_tool_round.py` | Validates, persists, executes, and records one model-emitted tool-call round. |
| `hermes-agent/agent/turn_final_response.py` | Handles a response that contains final assistant text instead of tool calls. |
| `hermes-agent/agent/turn_finalizer.py` | Closes and persists the turn, assembles the result envelope, records usage, and runs end-of-turn hooks/review. |

### Tool runtime

| File | Role |
|---|---|
| `hermes-agent/tools/registry.py` | Process-global tool registry with profile-scoped plugin overlays, schema/check metadata, normalized dispatch, and toolset availability. |
| `hermes-agent/model_tools.py` | Converts registry entries into model-facing function definitions and routes calls through hooks, middleware, guards, and registry dispatch. |
| `hermes-agent/agent/tool_executor.py` | Executes model-emitted calls, including agent-inline tools, delegation, context-engine tools, memory tools, and ordinary registry tools. Commits results back into transcript order. |
| `hermes-agent/toolsets.py` | Groups concrete tools into selectable capability bundles. |
| `hermes-agent/tools/AGENTS.md` | Tool-authoring and extension constraints. |

### Delegation and MAS runtime

| File | Role |
|---|---|
| `hermes-agent/tools/delegate_tool.py` | `delegate_task` schema and entry point; validates spawn/control requests, resolves credentials, builds child batches, and selects foreground/background execution. |
| `hermes-agent/tools/delegate_tool_config.py` | Delegation limits, timeout policy, recursion depth, concurrency, provider/model inheritance, and child approval behavior. |
| `hermes-agent/tools/delegate_tool_toolsets.py` | Derives child capabilities from parent capabilities and role; strips forbidden tools. |
| `hermes-agent/tools/delegate_tool_tasks.py` | Task normalization and child-task input shaping. |
| `hermes-agent/tools/delegate_tool_dispatch.py` | Batch execution, async admission, grouping, background dispatch, and synchronous fallback. |
| `hermes-agent/tools/delegate_tool_child_run.py` | Child-run state, heartbeat, timeout/staleness, workspace, steering, and cleanup mechanics. |
| `hermes-agent/tools/delegate_tool_registry.py` | Live child registry used by list/steer/stop controls and monitoring surfaces. |
| `hermes-agent/tools/delegate_tool_progress.py` | Child progress events and parent activity propagation. |
| `hermes-agent/tools/delegate_tool_results.py` | Child-result shaping, summary limits/spill files, lifecycle hooks, memory notification, and cost rollup. |
| `hermes-agent/tools/async_delegation.py` | Process-local background delegation registry and completion delivery. |
| `hermes-agent/agent/subagent_lifecycle.py` | Stable plugin-facing launch/status/wait/cancel/result/reconnect API using immutable contracts rather than exposing `AIAgent`. |
| `hermes-agent/website/docs/developer-guide/subagent-lifecycle-api.md` | Public lifecycle contract and plugin integration documentation. |
| `hermes-agent/website/docs/user-guide/bot-mode.md` | Persistent named-agent model based on isolated Hermes profiles. |

### Architectural documentation

| File | Role |
|---|---|
| `hermes-agent/website/docs/developer-guide/architecture.md` | System boundaries and shared-core architecture. |
| `hermes-agent/website/docs/developer-guide/agent-loop.md` | Turn-loop behavior and invariants. |
| `hermes-agent/website/docs/developer-guide/tools-runtime.md` | Tool discovery, schema exposure, and dispatch path. |
| `hermes-agent/website/docs/developer-guide/prompt-assembly.md` | Stable/context/volatile/ephemeral prompt layers and cache behavior. |
| `hermes-agent/skills/autonomous-ai-agents/hermes-agent/SKILL.md` | Operational guidance for autonomous agent behavior. |
| `hermes-agent/skills/autonomous-ai-agents/hermes-agent/references/background-systems.md` | Distinguishes process-local background delegation from durable background work. |

## 3. Mechanical chatbot execution flow

### 3.1 Construction

`AIAgent(...)` in `run_agent.py` forwards its arguments to `init_agent(...)` in `agent/agent_init.py`.

`init_agent(...)` executes an order-sensitive pipeline:

1. Stores constructor parameters and callbacks on the agent.
2. Creates or accepts an `IterationBudget`.
3. Resolves provider identity, base URL, requested provider, API mode, and route capabilities.
4. Initializes prompt-cache and per-turn control state.
5. Builds the provider client and fallback chain.
6. Calls `_load_tools(...)`.
7. Initializes session identity, persistence, reasoning, token limits, and checkpoints.
8. Loads read-only configuration.
9. Configures display, memory, and the `agent` config section.
10. Resolves context length and builds the compression/context engine.
11. Injects any context-engine tools.
12. Initializes usage accounting and snapshots the primary runtime.

Tool loading is a snapshot operation. `_load_tools(...)` discovers plugins, records the registry generation, asks `model_tools.get_tool_definitions(...)` for the selected toolsets, applies one-shot and side-agent pruning, then stores:

- `agent.tools`: model-facing function schemas.
- `agent.valid_tool_names`: the exact call names accepted for that session.

### 3.2 Public call boundary

`AIAgent.chat(message, stream_callback=None)` performs:

```text
chat
  -> run_conversation
      -> final result dictionary
  -> result["final_response"]
```

A host that needs persistence, retries, usage, updated history, errors, or turn IDs should use `run_conversation(...)` directly rather than `chat(...)`.

### 3.3 One complete turn

`conversation_loop._run_conversation_turn(...)` performs:

```text
user input
  -> decode optional inline MoA configuration
  -> refresh mutable credentials
  -> build_turn_context
       - restore/build system prompt
       - prepare durable and API-visible user content
       - establish turn/session/task identity
       - initialize transcript and turn-local values
  -> choose special Codex app-server path, or generic loop
  -> repeat while iteration budget remains
       -> begin_iteration
       -> prepare_iteration
       -> assemble_api_request
       -> run_preflight_gate
       -> announce_api_call
       -> API retry loop
            -> provider rate guard
            -> build_api_request
            -> perform_api_call
            -> check_api_response
            -> classify/recover on errors
       -> apply retry/fallback/redirect restart state
       -> normalize_model_response
       -> if tool calls: run_tool_round
       -> else: finish_text_response
  -> finalize_turn
  -> export turn boundary
  -> close failed durable turn when required
  -> return result dictionary
```

The same loop supports a plain chat response and an arbitrarily long model/tool alternation. The model controls whether the next step is final text or one or more function calls; the host controls budgets, validation, persistence, permissions, and failure policy.

### 3.4 Request assembly and prompt stability

`turn_request_assembly.assemble_api_request(...)` creates a request copy rather than rewriting canonical history. Its order is mechanically significant:

1. Build API messages from system prompt plus selected transcript.
2. Add optional MoA reference context.
3. Insert ephemeral prefill messages into the request copy.
4. Let the context engine select or replace request-local context.
5. Sanitize malformed message sequences and stale images.
6. Remove incompatible thinking-only or cross-protocol state from the request copy.
7. Normalize whitespace and tool-call JSON.
8. Remove invalid surrogate characters.
9. Build prompt-cache markers only after all preceding mutations.
10. Measure context pressure and trigger the preflight policy if needed.

Canonical messages and canonical tool schemas remain undecorated. Cache markers and provider-specific transformations are request-local.

## 4. Mechanical tool execution flow

### 4.1 Registration

A built-in tool module registers an entry through `tools.registry.registry.register(...)` with:

- unique name;
- toolset name;
- JSON schema;
- handler callable;
- optional availability check;
- optional async flag;
- optional dynamic schema override;
- optional result-size limit and display metadata.

The registry stores built-ins globally and plugin tools in profile-scoped overlays. Plugin replacement of a built-in requires explicit override authorization.

### 4.2 Exposure to the model

`model_tools.get_tool_definitions(...)`:

1. Selects enabled toolsets.
2. Subtracts disabled toolsets last.
3. Filters unavailable entries using requirement checks.
4. applies per-tool dynamic schema overrides and cross-tool rewrites;
5. optionally collapses a large catalog behind Tool Search;
6. returns OpenAI-style `{"type": "function", "function": ...}` definitions.

The result is captured during agent construction. This keeps the tool surface stable through a conversation unless the host deliberately reconstructs or refreshes the agent.

### 4.3 Model call to handler

When a provider response contains tool calls, `turn_tool_round.run_tool_round(...)`:

1. Validates tool names, arguments, truncation state, and call limits.
2. Deduplicates and caps delegation calls.
3. Appends the assistant tool-call message.
4. Creates error results for invalid calls in a mixed batch.
5. **Persists the assistant tool-call row before executing side effects.**
6. Calls `agent._execute_tool_calls(...)`.
7. Stops if incremental persistence failed or a guardrail requested a halt.
8. Compresses after tool results if required.
9. Continues to the next model iteration.

The persist-before-execute order is a durability invariant: after a restart, a recorded destructive action must not appear to have happened without its initiating tool-call row.

`agent/tool_executor.py` chooses dispatch in this precedence order:

1. agent-inline tools requiring live `AIAgent` state;
2. `delegate_task`;
3. context-engine-owned tools;
4. memory-provider-owned tools;
5. ordinary registry tools through `model_tools.handle_function_call(...)`.

For an ordinary registry tool, the path is:

```text
model tool call
  -> tool executor parses arguments
  -> request middleware and guardrails
  -> model_tools.handle_function_call
  -> execution middleware
  -> ToolRegistry.dispatch
  -> handler(args, accepted_context_kwargs...)
  -> normalized string or multimodal result
  -> post-tool hooks / optional result transform
  -> transcript tool-result row
  -> incremental persistence
  -> next model request
```

Handlers normally return a JSON string. Unsupported result types are converted into a structured tool-contract error. Exceptions are caught and returned as sanitized tool errors rather than escaping into the model loop.

## 5. Mechanical MAS delegation flow

### 5.1 Parent request

The model-facing `delegate_task` tool supports:

- `tasks=[...]` for one or more children;
- optional per-task context, output schema, images, and result-delivery group;
- `action=list|steer|stop` for live control;
- legacy single-goal input for compatibility, though the advertised schema favors `tasks`.

Each task must be self-contained because a child does not receive the parent's transcript. The child gets the explicit goal, explicit context, a generated child system prompt, selected capabilities, and route credentials.

### 5.2 Admission and limits

`delegate_task(...)` mechanically checks:

1. A parent agent exists.
2. A control action can be served immediately, or spawning is allowed.
3. The operator pause switch permits new children.
4. Current depth is below `delegation.max_spawn_depth`.
5. Delegation credentials/provider route resolve successfully.
6. Task list, schemas, and images are valid.
7. Batch size does not exceed `delegation.max_concurrent_children`.
8. A finite one-shot session has not exceeded `delegation.oneshot_max_children`.

Defaults observed in the implementation:

- maximum concurrent children: `10`;
- maximum spawn depth: `1` (flat parent-to-leaf delegation);
- one-shot total child allowance: `2`;
- child inactivity timeout: disabled unless configured;
- orchestrator capability switch: enabled, but only relevant when depth is greater than one;
- independent completion delivery: disabled by default.

### 5.3 Child construction

`_build_child_agent(...)` creates a new `AIAgent` per task.

The child receives:

- a distinct session ID and subagent ID;
- `parent_session_id` linkage;
- an isolated prompt containing its goal and context;
- its own iteration budget;
- its own terminal/task session;
- optional delegated provider/model overrides;
- a dedicated session database handle when persistence is available;
- progress callbacks and lifecycle identity;
- `platform="subagent"`, `side_agent=True`;
- `skip_context_files=True`, `skip_memory=True`;
- no clarification callback.

The child does **not** receive:

- the parent's complete conversation history;
- direct user clarification ability;
- shared memory writes;
- unrestricted messaging/scheduling capabilities;
- parent internal reasoning.

### 5.4 Child role and capabilities

Role is derived from depth, not trusted from model input:

```text
child_depth = parent_depth + 1
if orchestrator_enabled and child_depth < max_spawn_depth:
    role = orchestrator
else:
    role = leaf
```

A leaf cannot delegate. An orchestrator receives delegation capability only while depth remains.

`delegate_tool_toolsets._resolve_child_toolsets(...)` ensures a child does not broaden the parent's permissions. It derives child toolsets from the parent's loaded capabilities, inherits explicit parent denials, strips blocked tools, and only re-adds delegation for a depth-authorized orchestrator.

Always-blocked child capabilities include user clarification, shared memory writes, direct cross-platform messaging, cron scheduling, and kanban ownership. `delegate_task` itself is blocked for leaves and permitted only for orchestrators.

### 5.5 Child execution

Children are built on the parent/main thread because construction is not thread-safe. Their runs are then submitted to worker execution.

A child run:

1. leases credentials if a credential pool is active;
2. starts a heartbeat that propagates activity to the parent;
3. registers the live child for monitoring/control;
4. seeds workspace state;
5. calls the child's own `run_conversation(...)` loop;
6. accepts queued steering at controlled boundaries;
7. validates an optional output schema, with bounded correction behavior;
8. classifies completion as completed, interrupted, or failed;
9. records duration, API calls, tool trace, and cost metadata;
10. cleans up registry, credentials, processes, worktree, session handle, and child agent.

Each child is therefore a normal Hermes agent running the same loop, with a narrower prompt, separate session state, and constrained tools.

### 5.6 Parallel batch execution

A multi-task call creates all children first, then executes independent children concurrently up to the configured cap. Results preserve `task_index` so completion order does not alter task/result association.

With `delegation.independent_completions` disabled, one delegation call is one completion unit: the parent receives one consolidated result after all children finish.

With it enabled, tasks can re-enter individually or by a shared `group`. Grouping changes delivery units, not dependency order. A task that depends on another task's output must be dispatched after that result is available.

### 5.7 Foreground versus background

Direct Python callers default to synchronous joining. Model-facing top-level delegations normally run in the background when the host session has a later-result delivery channel. Nested orchestrator children join their own workers synchronously because they need those worker results inside their active turn.

Background dispatch:

1. verifies the host can receive a detached completion;
2. checks async capacity;
3. detaches accepted children from direct parent cancellation ownership;
4. stores a process-local delegation record and runner;
5. immediately returns a dispatch handle and transcript paths;
6. runs children in worker threads;
7. injects the completed aggregate as a new message between parent turns.

If delivery is unsupported or the async pool is full, Hermes falls back to synchronous execution rather than silently dropping the work.

Background subagents are process-local. `/stop`, `/new`, process exit, or loss of the host process ends the tree. Work that must survive process exit uses cron or another durable background mechanism instead.

### 5.8 Result boundary

The parent receives result entries, not child transcripts. A result can include:

- task index;
- status and exit reason;
- final summary;
- schema-validity metadata;
- duration and API-call count;
- bounded tool-trace metadata;
- interruption/error information;
- live transcript or spilled-summary paths when applicable.

`delegate_tool_results.py` protects the parent context with two summary limits:

1. a static character ceiling (`24000` by default);
2. a dynamic per-summary allowance based on remaining parent context headroom and batch size.

An oversized summary is reduced to head plus tail. The full text is written under the Hermes delegation cache when possible, and the parent receives a path plus paging instructions.

After result shaping, the host:

- informs the parent's memory manager of the delegation outcome;
- emits `subagent_stop` hooks with sanitized metadata-only tool history;
- rolls child cost into parent session accounting.

Child claims are treated as self-reports. External side effects require a verifiable handle that the parent can check before reporting success.

## 6. Public subagent lifecycle API

`agent/subagent_lifecycle.py` provides a separate plugin-safe interface. It avoids exposing mutable `AIAgent` objects and private delegation internals.

Public contracts include:

- `SubagentLaunchRequest`;
- `SubagentHandle`;
- `SubagentStatus`;
- `SubagentTerminalState`;
- `SubagentCancelResult`;
- `SubagentResult`;
- `SubagentReconnectResult`.

Service operations are:

```text
launch(request) -> handle
status(handle) -> status
wait(handle, timeout_seconds=...) -> terminal/wait state
cancel(handle, reason=...) -> cancellation result
result(handle) -> bounded result or NOT_READY
reconnect(handle) -> process-local reconnect status
```

Handles are capability-protected with a process-local HMAC and scoped to the active parent session. Serialized handles cannot reconnect after process restart. Terminal records are retained for a bounded period, currently one hour.

Request validation prevents permission broadening and rejects unsupported per-launch working directories, blocked-tool lists, and timeouts. Requested toolsets must be known and must be a subset of the parent's enabled toolsets.

## 7. Persistent named agents versus delegated agents

Hermes represents persistent named agents through Bot Mode profiles, not through long-lived delegated child objects.

A profile isolates:

- configuration;
- provider/model route;
- memory;
- skills;
- credentials;
- chat history;
- plugin/tool scope.

A delegated child is a bounded unit of work inside a parent-owned execution tree. A profile is a persistent identity and configuration boundary. These are separate mechanisms even though both ultimately construct `AIAgent` instances.

## 8. State and isolation findings

Hermes separates several kinds of state that a smaller implementation might otherwise conflate:

| State | Ownership |
|---|---|
| Canonical conversation transcript | Session/agent; persisted incrementally when a session DB exists. |
| Provider request copy | One API call; may be sanitized, compressed, or cache-decorated without mutating canonical history. |
| System prompt | Session-stable assembled layers plus request-local additions. |
| Tool catalog | Agent-construction snapshot filtered by toolsets and availability. |
| Tool process/session state | Isolated by task ID and child session where supported. |
| Iteration budget | Agent/child local; children receive fresh budgets. |
| Provider credentials | Inherited or explicitly overridden; credential pools can be shared only when route identity matches. |
| Memory | Parent-owned by default; delegated children skip shared-memory loading/writes. |
| Child live registry | Process-local host state for status/steer/stop. |
| Child result | Bounded summary and metadata returned to parent. |
| Named-agent identity | Profile-scoped persistent state. |

## 9. Reliability and control invariants observed

### Transcript and persistence

- Persist a tool-call turn before performing its side effects.
- Persist tool results incrementally so progress survives interruption.
- Ensure every assistant tool call has a matching tool-result row, including invalid, skipped, cancelled, or interrupted calls.
- Close a failed durable user turn with an assistant boundary when safe, preventing the next user message from being merged into an unanswered prior turn.
- Keep durable canonical history separate from provider-specific request transformations.

### Prompt and cache behavior

- Keep prior prompt bytes stable across turns.
- Do not mutate canonical messages merely to satisfy one provider.
- Build cache markers after all request sanitization and normalization.
- Keep the tool surface stable during a conversation.
- Treat context compression as the intentional exception that rewrites history.

### Tool safety

- Validate tool names and arguments before dispatch.
- Apply enabled and disabled capability sets at schema exposure and dispatch boundaries.
- Use middleware and guardrails around tool execution.
- Normalize all handler results into a bounded, model-consumable form.
- Make unattended child approval default-deny; automatic dangerous-command approval is an explicit configuration switch.

### Delegation safety

- Derive child role from runtime depth rather than trusting model-supplied role labels.
- Never allow a child to gain capabilities absent from its parent.
- Bound fan-out and recursion independently.
- Track and propagate cancellation through the child tree.
- Keep child reasoning/transcripts out of the parent prompt.
- Bound summaries according to parent context headroom.
- Treat child completion claims as unverified until the parent checks an artifact or external identifier.

### Liveness and observability

- Use activity heartbeats while children are running.
- Expose list/steer/stop independently of the model's normal spawn path.
- Keep live transcript files as an observability side channel, not as prompt content.
- Distinguish process-local background work from durable scheduled work.
- Roll child usage/cost into parent accounting while preserving child-level lifecycle events.

## 10. Minimal conceptual decomposition for learning

The source supports a clean separation of concepts that can be implemented independently without copying Hermes' full production surface:

### Chat model adapter

Input: system prompt, messages, optional tools.  
Output: assistant text or structured tool calls, finish reason, and usage.

Hermes supports several wire protocols, but the loop consumes one normalized response shape.

### Conversation state

A sequence of user, assistant, and tool messages plus a stable session identity. Request-local provider fixes should not mutate this canonical sequence.

### Agent loop

A bounded state machine:

```text
append user message
while budget remains:
    response = model(messages, tool_schemas)
    if response has no tool calls:
        append assistant text
        return
    append assistant tool-call row
    for each call:
        execute and append matching result
raise/return budget exhaustion
```

Hermes adds persistence, retries, streaming, compression, interrupts, middleware, fallback providers, and protocol repair around this core.

### Tool registry

A mapping of tool name to schema, handler, capability group, and optional availability check. The model sees schemas; the runtime invokes handlers and converts results to transcript messages.

### Child-agent factory

A function that creates another instance of the same agent loop with:

- a self-contained task prompt;
- isolated history;
- separate identity and budget;
- a capability subset;
- a final-result contract.

### Orchestrator

A parent-side mechanism that validates child requests, schedules children under depth/concurrency limits, collects results by stable task identity, and feeds bounded summaries back to the parent.

### Lifecycle registry

A host-owned registry that makes background work observable and controllable without giving callers direct access to mutable child objects.

These are findings about separable runtime responsibilities, not an implementation sequence or milestone plan.

## 11. Hermes complexity that is outside a minimal MAS kernel

The inspected framework includes production concerns that are mechanically adjacent to, but not required for, a first chatbot or basic parent/child MAS:

- multiple provider wire protocols and fallback chains;
- prompt-cache layout differences;
- streaming recovery and partial-response repair;
- multimodal history and image eviction;
- persistent sessions and restart recovery;
- context compression and external context engines;
- credential pools and route-aware inheritance;
- tool and LLM middleware;
- plugin lifecycle hooks;
- approval systems and guardrails;
- gateway delivery and messaging identities;
- MoA reference-model aggregation;
- worktree isolation;
- live TUI monitoring and steering;
- durable cron/kanban workers;
- profile-scoped plugins, memory, and named bots.

The framework keeps these concerns around a shared agent loop rather than embedding separate agent logic in each host surface.

## 12. Directly reusable interface shapes

Without copying implementation details, the following interface shapes summarize the boundaries present in Hermes:

```python
class ModelAdapter:
    def complete(self, messages, tools=None, *, stream=False): ...

class ToolRegistry:
    def register(self, name, schema, handler, capability): ...
    def definitions(self, enabled_capabilities): ...
    def dispatch(self, name, args, context): ...

class Agent:
    def run_turn(self, user_message) -> dict: ...
    def chat(self, user_message) -> str: ...

class ChildRequest:
    goal: str
    context: str | None
    output_schema: dict | None

class ChildResult:
    task_id: str
    status: str
    summary: str
    error: str | None
    usage: dict

class Orchestrator:
    def spawn(self, requests) -> list[ChildHandle]: ...
    def status(self, handle) -> ChildStatus: ...
    def cancel(self, handle, reason) -> CancelResult: ...
    def collect(self, handles) -> list[ChildResult]: ...
```

The critical boundary is that `Orchestrator.collect(...)` returns result contracts, not child `Agent` objects or complete private transcripts.

## 13. Research boundary

No Agile milestone consolidation has been performed. The repository findings above establish:

- the chatbot execution kernel;
- the tool-calling extension point;
- the child-agent isolation model;
- parent/child capability and lifecycle controls;
- foreground/background result-delivery mechanics;
- persistent-profile versus ephemeral-delegation boundaries;
- reliability invariants relevant to a from-scratch implementation.

Milestone sequencing, acceptance criteria, estimates, and implementation tasks remain intentionally unspecified pending the user's explicit signal.
