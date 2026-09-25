# MASFS Document Index

**Conversation:** MASFS — Multi-Agent System from Scratch  
**Purpose:** Track documents produced for this conversation.  
**Naming convention:** Conversation documents use the `MASFS-` filename prefix.

## Document register

| Document | Status | Purpose | Depends on |
|---|---|---|---|
| [`MASFS-hermes-agent-mas-research-findings.md`](MASFS-hermes-agent-mas-research-findings.md) | Complete | Research findings from the Hermes Agent framework, including chatbot, tool, delegation, lifecycle, state, and safety mechanics. | — |
| [`MASFS-milestones-feedback.md`](MASFS-milestones-feedback.md) | Incorporated | v3 roadmap proposal and review input used to revise the active milestones. Retained for decision history. | Hermes research findings and concurrency review |
| [`MASFS-agile-milestones.md`](MASFS-agile-milestones.md) | Active — v4 | Adopted Agile roadmap. M1–M9 form the complete core track; M10–M16 are optional selected Hermes delegation features. | Hermes research findings and milestones feedback |
| [`MASFS-milestone-1-proposal.md`](MASFS-milestone-1-proposal.md) | Proposal | Proposed M1 source-package structure, module responsibilities, contracts, and dependency boundaries. | Active Agile roadmap |
| [`MASFS-index.md`](MASFS-index.md) | Active | Index and status register for all documents associated with the MASFS conversation. | Documents above |

## Recommended reading order

1. [`MASFS-hermes-agent-mas-research-findings.md`](MASFS-hermes-agent-mas-research-findings.md)
2. [`MASFS-agile-milestones.md`](MASFS-agile-milestones.md) — active roadmap
3. [`MASFS-milestone-1-proposal.md`](MASFS-milestone-1-proposal.md) — proposed M1 source design
4. [`MASFS-agile-milestones-feedback.md`](MASFS-agile-milestones-feedback.md) — optional decision history
5. Use this index to locate future MASFS documents.

## Maintenance rule

Whenever another document is created for this conversation:

1. Prefix its filename with `MASFS-`.
2. Add it to the document register.
3. Record its status, purpose, and dependencies.
4. Update the recommended reading order when appropriate.
