# Shoppie - ecommerce platform

Shoppie is an ecommerce support platform for agents who process customer cancellation, return and refund requests.

## How support works today

Customers contact support about orders they want to cancel, items they want to return, or payments they want refunded. Support agents review each request, check the order and its history against Shoppie's policies, and decide whether to approve it, decline it or ask for more information.

## The pilot

We want an AI agent, the Shoppie Agent, to help agents work through the support queue. For each request it should:

- read the customer's request, order details and relevant history
- look up the sections of the shopping, cancellation and returns policies the request needs, rather than reading whole policies
- recommend whether to approve, decline or ask for more information
- explain the recommendation and cite the policy sections it relied on

## Working the queue

One run works the whole queue. A support agent starts the agent once, with a cap on how many requests the run may work, and the agent plans the run as a to-do list, chooses the order, works each waiting request up to the cap, and finishes with a short summary. Each request is worked by a fresh helper from a clean start. One named request can also be worked on its own.

A long run will meet timeouts and errors. One bad request never stops the run or stays stuck in progress: a request that fails before it has a recommendation goes back in the queue and is tried again, and one that fails twice is left for a support agent. No request gets two recommendations or two reviews. Before it finishes, the agent checks it has not missed a waiting request within its cap.

The agent supports the support team; agents remain responsible for processing requests and confirming decisions.

## What the team needs to see

- The queue, with where each request stands: waiting, in progress, waiting for agent review or decided, and which requests were left for a support agent.
- The current run's to-do list, with each item to do, in progress, done or left for a support agent, and the run's summary when it ends.
- Each request in full, with the agent's recommendation and its reasons.
- What the agent is doing on a request while it works, step by step, including the policy sections it read.
- The agent's instructions for running the queue and for working a request, read only.

## Rules

- Recommendations follow Shoppie's cancellation, return and refund policies.
- The agent must not claim that an action has been completed unless the system confirms it.
- Requests that need judgment or information should be held for an agent to review.
- Customer and order data must be limited to what is needed to process the request.

## Our records

The platform uses order, customer, request and policy records provided for the pilot. These records support the queue and the agent's recommendations.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real cancellations, returns or refunds.
- No messages to customers.
