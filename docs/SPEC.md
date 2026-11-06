# Shoppie - ecommerce platform

Shoppie is an ecommerce support platform for agents who process customer cancellation, return and refund requests.

## How support works today

Customers contact support about orders they want to cancel, items they want to return, or payments they want refunded. Support agents review each request, check the order and its history against Shoppie's policies, and decide whether to approve it, decline it or ask for more information.

## The pilot

We want an AI agent, the Shoppie Agent, to help agents work through the support queue. For each request it should:

- read the customer's request, order details and relevant history
- check the request against the applicable cancellation, return or refund policy
- recommend whether to approve, decline or ask for more information
- explain the recommendation and cite the relevant policy

The agent supports the support team; agents remain responsible for processing requests and confirming decisions.

## What the team needs to see

- The queue, with where each request stands: waiting, in progress, waiting for agent review or decided.
- Each request in full, with the agent's recommendation and its reasons.
- What the agent is doing on a request while it works, step by step.
- The agent's instructions, read only.

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
