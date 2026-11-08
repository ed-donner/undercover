# Getting ready for harder support requests

From Shoppie's head of customer support, with our IT team.

## Where we're heading

Our support requests are going to get harder to decide. Customers write about partial cancellations, perishable items, failed deliveries, damaged goods and refunds to cash-on-delivery orders, and each of those turns on a different part of our shopping, cancellation and returns policies. Over the coming months we expect requests with more evidence, more rules to weigh and more to look up. We want the Shoppie Agent to grow into that work: taking on longer jobs, working through them on its own, and dealing with problems without someone stepping in.

In the pilot (`docs/STATUS.md`), our code does much of the organizing. It feeds the agent one request at a time and gives it the whole policy for the request's type every time, and a request that fails partway is left for a support agent with no second try. We want the agent to organize its own work instead.

## What we want

1. **One run works the whole queue.** We start the agent once and it works every waiting request, choosing the order itself, then finishes with a short summary for the support team. For trials we need a way to start a run capped at a number of requests, with the rest left waiting, so a trial on five requests costs little. We still need to be able to run it on one named request.

2. **A to-do list we can watch.** The agent plans its work as a to-do list and keeps it up to date as it goes, with each item to do, in progress, done or left for a support agent. The queue page of the dashboard shows the list for the current run, so the team can see what the agent means to do and how far it has got.

3. **A fresh helper for each request.** The agent running the queue hands each request to a subagent that works that one request from a clean start and reports back in a line: the recommendation, or what went wrong. This keeps each request's work focused and stops each step getting more expensive as the run goes on. Every step on a request is still recorded on that request.

4. **Our policies, looked up the way a support agent would.** Our shopping, cancellation and returns policies (`docs/shopping-policy.md`, `docs/cancellation-policy.md` and `docs/returns-policy.md`) cover things a request's type alone does not point to: a cancellation refund on a cash-on-delivery order, a failed delivery of perishable goods, or a promotion recalculated after a partial cancellation. For each request the agent should find and read the sections of the policies it needs, rather than being handed whole documents, and the request page should show what it read.

5. **Problems are put right automatically.** A long run will meet timeouts, errors from the model provider and steps that fail. One bad request must never stop the run or leave a request stuck in progress. A request that fails before it has a recommendation goes back in the queue to be tried again, and a request that fails twice is left for a support agent. No request ever gets two recommendations or two reviews. Before it finishes, the agent checks that it has not missed a waiting request within its cap.

6. **The model.** Our trials found DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash` on OpenRouter, with low reasoning effort) the best balance of accuracy, speed and cost, so it becomes the default. `MODEL_NAME` still overrides it.

7. **Instructions we can read.** The instructions page shows the agent's instructions for running the queue and for working a request. Write them from our policies, never from the reference decisions in `data/evals/`.

## What stays the same

- The rules in `docs/SPEC.md`: recommendations follow our policies, a support agent confirms every decision, and the agent never claims an action happened unless the system confirms it. There are still no real cancellations, returns, replacements or refunds, and no messages to customers.
- Our tech stack. Build these pieces into our own agent rather than adding another agent framework.
- Tests never call a model, and the code stays simple, as `docs/CODE_STANDARDS.md` asks.

## What done looks like

- `npm run check` is green, with tests on a stub model for each new behavior: the to-do list stored and shown, the cap on a run, a failed request that does not stop the run, a failed request going back in the queue and being tried again, a request that fails twice left for a support agent, and the check for missed requests.
- After reseeding, a run capped at five requests on the default model works five requests on its own. The dashboard shows the to-do list filling in and being ticked off, and each request's steps, including the policy sections the agent read. The other requests stay waiting.
- `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_HARNESS.md` and tick it off there. `docs/PLAN.md` is the pilot's finished plan and stays as it is. For any live run with the real model, reseed first and cap the run at five requests.
