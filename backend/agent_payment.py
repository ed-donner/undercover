"""Attempt-fenced agent payments share the handler payment transaction."""

from backend.models import PaymentInput


class AgentPaymentInput(PaymentInput):
    run_id: str
