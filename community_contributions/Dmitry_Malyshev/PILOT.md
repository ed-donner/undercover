# Setup

I used Haiku 5.5 via Claude console API (no subscriptions) in VS.

The agent run for about 12 minutes and had about $1 of API costs.

Adjustments:

1. In the original implementation, all processed claims were marked as "decided", I've asked to put a more descriptive result by adding the following line in the SPEC.md (under "## What the team needs to see"):
Correction: instead of "decided" use more descriptive result of inspection: "approved", "declined", or "docs missing" (if additional documents are needed to process the claim).

2. Some of the claims were not processed due to "rate per minute limit error":
Error code: 429 - {'error': {'message': 'Rate limit exceeded: new-account-rpm/openai/gpt-6-luna-20260922. Rate limit reached: new accounts are limited to 20 requests per minute for this model. Please retry shortly.', 

I've asked the agent to add a delay if the error arrises.
The agent now tries 5 times with a delay of 5 seconds after each error: "The agent now waits 5 seconds and retries a model call when OpenRouter returns the rate-limit error, up to 5 times. Then it gives up on that call. Because the retry happens inside each model call, the claim keeps its place in the run and the step log doesn't repeat."
The "run queue" worked fine after that.

These two corrections costed about 50 cents in API on Haiku 5.5.


The fork is:
https://github.com/dima137/undercover
branch 
my_pilot_dima
