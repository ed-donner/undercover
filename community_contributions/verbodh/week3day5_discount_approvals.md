# Week 3 Day 5 assignment: a discount agent on AgentCore Runtime

Code: https://github.com/verbodh-pte-ltd/undercover-fork/tree/verbodh-discount-agent-code/community_contributions/verbodh/week3day5_discount_approvals

Northwind Software's sales reps ask for discounts on quotes. A LangGraph agent decides each one
against the pricing policy: it approves up to 15% on its own, and a sales director signs off above
that.

- **Decisions with limits:** a `check` node in code, not the model, declines customers on hold, caps
  at the product's floor and sends anything over 15% to `sign_off`, which pauses with `interrupt()`.
  Only a director can resume it.
- **Durable state:** `PostgresSaver` checkpoints on Postgres, so the director's answer resumes the
  request from a different Runtime session.
- **Context layer:** the policy, customers, products and people, read through three tools.
- **AgentCore Memory:** a user-preference strategy with a namespace per rep, `/reps/{actorId}/preferences/`.
- **AgentCore Runtime:** deployed with boto3 from a code zip, with its OpenRouter key and database URL
  in AgentCore Identity.

On Runtime, five requests: 10% approved by the agent; 22% countered at 20% and held; a rep's sign-off
refused; the director's sign-off resumed it from another session; and Memory turned one rep's "percent
first, then a one-line reason" into a note that shaped their next answer, while another rep's
namespace stayed empty.

One gotcha: with SigV4 calls, pass `runtimeUserId` to `invoke_agent_runtime`. Without it Runtime gives
the agent no workload access token, and `requires_api_key` tries to create a workload identity of its
own, which the execution role can't.
