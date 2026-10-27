## Challenges

# Knowledge base swap

I swapped Qdrant's semantic search for a simple word-search tool over knowledge.json. The word search was right on 92% of the 25 claims, against 100% with Qdrant and 60% with no memory, at about the same cost. Both misses were cautious referrals, not wrong payouts. It worked because the claims and facts share distinctive names like "Lisbon" and "Aerie Adventures". It would presumably struggle more with different wording or a much larger knowledge base, but it seemed to work great in this case.

# Customer notes

I gave the knowledge base agent a Markdown file of notes for each customer, named by customer_id, with tools to read and add notes. I seeded 6 customers, one of them with a misleading note. In one run it scored 24/25, with every decision right, against 23/25 without notes. Its one miss was a payout copying slip on CLM-1308, not caused by a note. It ignored the misleading note on CLM-1309 and followed the policy wording. The agent was given license to add further notes if it saw fit.

The two claims that improved, CLM-1306 and CLM-1318, also had seed notes that pointed towards the handler's decision. Part of the gain comes from what we wrote in the notes, not from the memory itself. A fair conclusion is that with relevant notes, the agent made fewer cautious referrals and wasn't thrown off by a misleading note.

One caveat was that the agent wrote a wrong note. On CLM-1304 it approved $300 correctly, then added a note saying the Meridian strike was announced on August 5, "before" the policy was bought on July 28. August 5 is after July 28. The note tells the next handler to consider an exclusion that doesn't apply, which could lead to a wrongful decline.

Possible fixes to this would be to use code to write the record_decision outcome to the notes and not ask the LLM to summarise the decision, LLM judge the notes, or add notes to evals to quality check.

Customer notes must live in `data/evals/even_harder` to be seeded.
