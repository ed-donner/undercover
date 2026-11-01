# Think of it this way: Week 1

Everyday analogies for the ideas in the Week 1 labs, to read alongside the notebooks. Each one names the lab and the cell it goes with. An analogy is a simplification, so where it breaks down, the lab is right.

## Week 1 Day 2: Introducing UnderCover

### Reminder: the Chat Completions API

The system prompt is the brief you give an actor before the show: "you're a pirate, stay in character". The user prompt is the question from the audience. The actor answers the audience, but in the way the brief told them to.

### The handler's decision on each claim

The handlers' decisions are the answer key the teacher keeps in a drawer. The model sits the exam without seeing it, and we mark its answers against the key afterwards.

### Claims by difficulty

Think of an open-book exam. The routine and hard questions can be answered from the book, which is the policy wording. The manual questions are about things only covered in the staff handbook or the customer's file, which the model doesn't have yet. Getting those wrong today is expected, not a failure of the model.

### Reminder: Structured Outputs

Asking for free text is handing someone a blank sheet of paper. Structured Outputs is handing them a form with three printed boxes: rationale, decision and payout. The decision box only has three tick boxes, so nobody can write "maybe".

### The rationale comes before the decision

It's the maths teacher who says "show your working, then write the answer". A model writes its reply in order, so if the answer box came first it would commit to an answer and then invent the working to fit. Putting `rationale` first makes it work through the claim before it decides.

### Reasoning effort: `low` and `medium`

It's the difference between blitz chess and a game with a long clock. With more time to think the player makes fewer blunders, but the game takes longer, and with a model every thinking token is paid for.

### `is_right`: within a dollar

A teacher marking a sum doesn't fail you for writing $1,249.99 when the answer is $1,250. The dollar of slack means a rounding difference doesn't count as a wrong payout.

### Commercial implications: the kind of mistake

Picture a shop assistant at the returns desk. Refunding someone with no receipt loses the shop money: a wrong approval. Turning away a customer with a genuine receipt loses the shop a customer: a wrong decline. Calling the manager over for every return wastes the manager's time: a wrong referral. All three are mistakes, but they don't cost the same.

### Jev and its confidence

Jev is like the triage nurse in an emergency department. It can't write you a report, but it can say in a moment where each patient should go and how sure it is. The clear cases get handled straight away and the unsure ones go to the doctor, the stronger and slower model. That's the split at a confidence of 0.9.

### Part 4: an agent with tools

In Part 2 the model is handed the whole file: the policy record and the claim on one sheet. The agent is a new employee given only the claim and two things they can do: phone the records office for the policy (`get_policy`) and stamp the decision into the system (`record_decision`). That's why each claim takes three model calls: one to ask for the policy, one to stamp the decision and one to say "done".

## Week 1 Day 3: The pilot build

### Plan first, then implement

An architect draws the plans and the client signs them off before the builders arrive. "Please plan" is the drawings: you can still move a wall for the price of an eraser. "Please implement" is the building work, where moving a wall costs a lot more.

### Success criteria as checkboxes

They're the building inspector's checklist, agreed before the work starts. Each phase is finished when every box can be ticked by checking something real, like a test passing or a page loading, not when the builder says it looks fine.

### The pre-commit hook

It's the bouncer at the door. Every commit has to get past the format, lint, type and test checks, and `--no-verify` would be sneaking in round the back, which the process rules out.

## Week 1 Day 4: Open-Source, Local, Token Cost

### 12 of the 20 are approvals

Imagine a multiple-choice test where 12 of the 20 answers are "A". A student who marks "A" for every question without reading them scores 60%. So a model at 60% isn't doing well; it's level with the lazy guess. It only shows it read the claims when it does better than that.

### A smaller prompt

If a friend asks how to change a tyre, you don't hand them the 300-page car manual. You open it at the chapter on tyres. They read less and finish sooner. The risk is that something they needed was in the chapter on safety, which you didn't show them.

### Reminder: tokens

Tokens are the Lego bricks of text. A short common word like "cat" is one brick, while a long or rare word takes several bricks clicked together. Languages other than English often take more bricks for the same text.

The pricing is like a taxi with two rates per kilometre: the ride out (the tokens you send) is cheap, and the ride back (the tokens the model writes) costs several times more. Reasoning is the driver circling the block while working out the route, and the meter runs at the ride-back rate.

### Open-weight models on OpenRouter

An open-weight model is a cake recipe published online. Any bakery with an oven can bake it, so on OpenRouter several bakeries (the providers) sell the same cake, each at its own price and speed. Precision is whether the bakery uses the butter in the recipe or swaps in margarine to cut costs: the cake comes out much the same, but not always identical.

`require_parameters` is telling the delivery app "only show me bakeries that can handle every part of my order", which for us includes the reply in the exact shape Structured Outputs asks for.

### The Wafer provider and `ignore`

You ask the waiter for a quick coffee and they come back forty minutes later with a pour-over and the history of the farm. It's a fine coffee, but you waited and paid for all of it. Thinking tokens are billed as written tokens, the expensive kind, so next time you ask not to be served by that waiter: that's `ignore`.

### Ollama

Calling a model through an API is buying coffee at a café: you pay for every cup, but their machine is excellent. Running it with Ollama is having a coffee machine at home: once you have it, every cup is free and nobody sees what you're drinking, but the quality and speed depend on your machine. For a customer whose data can't leave the building, like a hospital or a bank, the machine at home may be the only option.

### Four bits and QAT

Running at 4 bits is like saving a photo as a JPEG in place of the raw file. Each number in the model is stored with less detail, so the file is much smaller and fits in your laptop's memory. You lose a little sharpness, but from across the room the photo looks the same. QAT, quantization-aware training, means the model was trained knowing it would become a JPEG, so it loses less in the squeeze.

### `num_ctx`

The context window is the model's desk. Ollama's default desk holds 4,096 tokens, and if the prompt is bigger, the earliest pages slide off the edge without any warning. The model then decides the claim without having read part of the rules. With 8,192 everything fits on the desk.

### `format` in Ollama

It's the same printed form as Structured Outputs on Day 2, and it matters more here. A small model is like a distracted student: on a blank sheet it might wander off, but with the boxes printed it fills in the boxes.

### A tenth model direct on Cerebras

OpenRouter is a delivery app that lists several restaurants serving the same dish and passes your order on. Going direct to Cerebras is ordering at the restaurant's own counter: you need an account there, but you're dealing with the kitchen itself. And 1,850 tokens a second is a few pages of a book in the blink of an eye.

### Working out the cost on Cerebras

A worked example. A claim with 2,000 input tokens and 300 output tokens costs:

- input: 2,000 × $0.99 / 1,000,000 = $0.00198
- output: 300 × $1.49 / 1,000,000 = $0.00045

That's about $0.0024, a quarter of a cent, so a dollar decides around 400 claims. The 300 output tokens are 13% of the tokens but nearly a fifth of the cost: writing costs more than reading.

### Accuracy against cost

It's choosing a restaurant on an app that plots rating against price. Everyone wants the corner that's good and cheap. Remember the 60% line from Part 1 too: a model below it is losing to the student who marked "A" for everything.

## Week 1 Day 5 Lab 1: the Claude Agent SDK

### A harness

The model is the engine and the harness is the rest of the car: the steering, the brakes, the dashboard and the satnav. The Claude Agent SDK is a ready-made car with Claude Code's engine already fitted. You give it a destination, not a set of parts.

### The claims desk

The agent is a temp on their first day, sitting at a desk with an in-tray of claims, a filing cabinet of policies and customers, and the rulebooks. The answer key stays locked in the manager's drawer, which is `data/evals`, so the temp can't peek.

### The task list

It's the sticky note on the monitor with one line per claim, crossed off as each is done. With five claims it stops the agent from forgetting claim number four. With fifty it's what keeps the agent on track at all.

### The subagent

The temp hands each claim to a colleague with a clear desk. The colleague reads only that claim, decides it, files the decision and comes back with one line. The temp's own desk never fills up with the papers from every claim, so their head stays clear for running the queue.

### Picking the tools

`tools` is the set of keys you give the temp. They get the key to the filing cabinet (reading, searching and writing files) but not to the server room or the front door (the shell and the web).

### `max_budget_usd`

It's a prepaid card with a dollar on it. If the agent gets stuck in a loop, the card runs out and the run stops, so you can't wake up to a surprise bill.

### `setting_sources=[]` and turning off auto memory

Every run starts like the temp's first day, with an empty desk drawer. None of your own Claude Code settings come along, and no notes are kept from the last run, so each run is a fair test.

### The handover note

It's the note the night shift leaves for the morning shift: what got done, and anything that needs a human's eye.

### Build or buy

It's renting a furnished flat compared with furnishing an empty one. You can move in on day one, but the landlord chose the sofa: here, that means Claude models only.

## Week 1 Day 5 Lab 2: Deep Agents

### Middleware

Middleware is a set of checkpoints that every step of the agent passes through on its way to and from the model. Each checkpoint can add something or change what passes through: one hands the agent its file tools, one keeps the to-do list, and one swaps a very long conversation for a summary, like giving someone who joins a long meeting the minutes in place of the full recording.

### `FilesystemBackend` with `virtual_mode=True`

It's a playpen. The agent sees the inside of the playpen as the whole world, `/`, and it can't climb out to the rest of your computer.

### `recursion_limit`

It's a board game that ends after 200 turns, however it's going. An agent that gets confused can't keep going round in circles forever.

### Build or buy

Deep Agents is a recipe printed in full: you can read every step and cook it with any ingredients, which here means any model. The Claude Agent SDK is a restaurant's house dish, tuned for its own kitchen.
