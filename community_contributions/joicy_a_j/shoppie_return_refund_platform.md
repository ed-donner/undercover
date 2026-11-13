# Shoppie: AI-Assisted E-Commerce Return and Refund Support Platform

**Author:** Joicy A J (`https://github.com/joicyjoy/undercover-1/tree/joicy`)

An end-to-end e-commerce customer support platform improvised on top of the course project, focused on order cancellations, returns, replacements, and refund recommendations in Indian Rupees (INR) with IST timestamps and human-in-the-loop sign-off.

## Use Case

Support handlers review incoming customer order issues (`missing_item`, `return_or_refund`, `replacement_or_refund`, `cancellation`, `return`). The platform pairs a deterministic policy-backed backend with multi-agent LangGraph workflows and an interactive Copilot sidebar. The AI agent recommends resolutions, calculates line-by-line payouts, and pauses for human confirmation; it never executes customer payouts autonomously.

## Architecture Overview (Weeks 1-3)

- **Backend (`backend/`):** FastAPI + SQLAlchemy Core (PostgreSQL / SQLite) serving queue management, deterministic refund calculations (`backend/refunds.py`, `backend/money.py`, `backend/records.py`), policy section endpoints, handler roles with single-use HMAC ephemeral tokens (`backend/handlers.py`), quality benchmarks, and run gating.
- **Context Layer (`context/`):** FastMCP server exposing 7 read-only tools (`lookup_term`, `describe_fields`, `get_plan`, `get_claim_rules`, `search_reference_data`, `search_documents`, `read_section`) over streamable HTTP (`:8006`), serving Shoppie's shopping, cancellation, returns policies, and claims manual section by section.
- **Support Agent (`agent/`, `runtime/`):**
  - Queue runner (`agent/queue.py`) that plans capped runs as a to-do list, tracks progress, and recovers interrupted threads via heartbeats.
  - Synchronous LangGraph `StateGraph` (`agent/main.py`) with prompt-injection screening (`REQ-7901`), Gateway/Direct routing, customer memory integration, deterministic Section 14 validation, `interrupt()` pauses before sign-off, and send-back re-evaluation with archived decision history.
- **Shoppie Copilot (`agent/copilot_graph.py`, `agent/copilot_tools.py`, `agent/copilot_memory.py`):**
  - Handler-scoped LangGraph assistant (`:8081`) with 16 backend and MCP context tools, per-handler preference/fact memory, an enforced ₹10,000.00 authority limit for non-lead handlers (`HND-02`), and explicit `interrupt()` confirmation cards before recording any sign-off.
- **Dashboard (`dashboard/`):** React + TypeScript + Vite workspace featuring the live queue, run to-do progress, side-by-side archived send-back decisions, calculation breakdown tables, context-used audit trail, and the collapsible Shoppie Copilot sidebar.
- **Verification (`e2e/`):** Pytest (192 tests), Vitest (23 tests), Ruff, Pyright, ESLint, and Playwright E2E tests covering dashboard workflows, runtime send-back, and Copilot sign-off guards.

## Key Takeaways

1. **Human supervision is structural, not optional:** Separating recommendation generation, deterministic payout validation, and explicit `interrupt()` confirmation keeps AI helpful without granting unchecked financial authority.
2. **Scoped credentials and memory matter:** Copilot runs with short-lived, single-use handler tokens and strips secrets from checkpoints and cross-turn memory stores.
3. **Observability and evals catch edge cases early:** Tracing agent steps, recording exact policy sections read, and testing against isolated ground-truth benchmarks make failures auditable.
