# The open-source contribution reviewer

From the maintainers of an open-source software project.

## How contributions work today

Our maintainers work through a queue of pull requests by hand. For each contribution, a maintainer reads the pull request description, changed files, test results, contributor history and project guidelines. Then they accept it, request changes or refer it for maintainer review. A contribution is referred when it needs architectural judgment, has a security or licensing concern, or needs more information from the contributor.

## The contribution reviewer pilot

We want an AI agent, the Contribution Reviewer, to work the queue the way a maintainer does. For each pull request it should:

- read the pull request, the repository's contribution guidelines, the relevant source files, test results and contributor history
- accept, request changes or refer the pull request
- identify the checks that passed or failed
- explain the decision in two or three sentences, along with the relevant section of the contribution guidelines
- list specific changes the contributor should make when requesting changes

Our goal is to handle routine contributions straight through, as accurately and consistently as our maintainers do.

## What the maintainers need to see

- The queue, with where each pull request stands: waiting, in progress, waiting for sign-off or decided.
- Each pull request in full, with the agent's decision, findings and reasons.
- What the agent is doing on a pull request while it works, step by step.
- The agent's instructions, read only.

## Rules

- A pull request that changes authentication, authorization, security-sensitive code, dependency manifests or release configuration needs a maintainer's sign-off. The agent can recommend acceptance, but the merge must wait until a maintainer signs off. The system must block the merge until then, even if the agent tries to merge it.
- Decisions follow the contribution guidelines and repository policies.
- The maintainers' decisions on these pull requests are in `data/evals/`. We use them to check the agent's work. The agent must never see them.
- The agent must not approve a pull request when required tests fail, required files are missing, or a security or licensing concern is unresolved.

## Our records

Everything is in `data/`, described in `data/README.md`: the pull request queue, repository metadata, contribution guidelines, maintainer profiles, changed files, test results, contributor history and project policies. The held-out pull requests in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- Automatic code changes. The pilot only reviews contributions and reports findings.
- No sign-in. Everyone who uses the screens sees everything.
- No real GitHub integration or repository merges.
- No messages to contributors. A maintainer can copy the agent's requested changes into a review.


Here is the link to the repo https://github.com/aparnamantha91/PRReviewerAgent 