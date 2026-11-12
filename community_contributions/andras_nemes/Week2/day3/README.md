# Week 2 Day 3: payout rejection

Andras Nemes. First challenge from `labs/week2day3.ipynb`.

[The notebook](week2day3_rejection.ipynb) extends the LangGraph approval flow so a handler can reject a proposed payout with a note. The note returns to the agent as a message for reconsideration. Revised payouts over $1,000 require a fresh sign-off before payment.