# Andras Nemes: Week 1 contributions

## 1. Week 1 Day 2: cheapest model for the claims agent

[`week1day2_cheap_agent_models.ipynb`](week1day2_cheap_agent_models.ipynb): three candidate models run against the lab's own agent over the 25-claim queue, compared on accuracy, cost and time. Findings also at the end of my copy of `labs/week1day2.ipynb`.

## 2. Week 1 Day 5 Lab 1 assignment: a different model and a changed instruction

[`week1day5_lab1_subagent_model_test.ipynb`](week1day5_lab1_subagent_model_test.ipynb): a self-contained rerun of the lab's claims desk with `claude-haiku-4-5` in place of `claude-sonnet-5-5`, plus an added instruction aimed at the baseline's one miss. The solution cell at the end explains a result that looks worse than it is: the added instruction left the model's actual decisions unchanged but made it less reliable about where and how it wrote its output.

## 3. Week 1 Day 5 Lab 2 assignment: where the harness is used, and a model comparison

[`week1day5_lab2_subagent_model_test.ipynb`](week1day5_lab2_subagent_model_test.ipynb): a self-contained run of `anthropic/claude-sonnet-5.5` through Deep Agents, compared with the lab's own DeepSeek run and with Lab 1's Sonnet 5.5 run through the Claude Agent SDK. Same model, same claims, same correct result, but Deep Agents cost more than twice as much as the Claude Agent SDK, because it reads whole documents instead of one section at a time.
