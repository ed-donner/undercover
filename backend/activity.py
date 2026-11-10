"""Public activity labels contain no model messages or tool payloads."""

from typing import Literal

Activity = Literal[
    "context_started",
    "context_read",
    "wording_started",
    "wording_read",
    "decision_started",
    "payment_started",
]
LABELS = {
    "run_started": "Agent started",
    "context_started": "Reading claim and customer records",
    "context_read": "Claim, policy, plan and customer history retrieved",
    "wording_started": "Reading policy wording",
    "wording_read": "Policy wording retrieved",
    "decision_started": "Recording decision",
    "decision_recorded": "Decision recorded",
    "payment_started": "Requesting simulated payment",
    "payment_recorded": "Simulated payment recorded",
    "payment_blocked": "Simulated payment blocked by backend rules",
    "sign_off_recorded": "Handler sign-off recorded",
    "run_completed": "Agent completed",
    "run_failed": "Agent run failed",
}
