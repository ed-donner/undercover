"""Structured claim-run outcomes and their handler-facing summary."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class RunOutcomes:
    approved: int
    declined: int
    referred: int
    paid: int
    signoff: int
    technical_issues: int

    def summary(self) -> str:
        return (
            f"{self.approved} approved, {self.declined} declined, "
            f"{self.referred} referred; {self.paid} paid, "
            f"{self.signoff} waiting for sign-off, "
            f"{self.technical_issues} technical issues."
        )


def outcomes(connection: sqlite3.Connection, run_id: str) -> RunOutcomes:
    rows = connection.execute(
        "SELECT c.status, c.needs_handler, d.outcome, p.claim_id AS paid "
        "FROM todos t JOIN claims c ON c.id = t.claim_id "
        "LEFT JOIN decisions d ON d.claim_id = c.id "
        "LEFT JOIN payments p ON p.claim_id = c.id "
        "WHERE t.parent_run_id = ? AND t.admitted = 1",
        (run_id,),
    ).fetchall()
    technical = sum(
        bool(r["needs_handler"])
        or (
            r["outcome"] == "approve"
            and not r["paid"]
            and r["status"] != "waiting_for_sign_off"
        )
        for r in rows
    )
    return RunOutcomes(
        approved=sum(r["outcome"] == "approve" for r in rows),
        declined=sum(r["outcome"] == "decline" for r in rows),
        referred=sum(r["outcome"] == "refer" for r in rows),
        paid=sum(bool(r["paid"]) for r in rows),
        signoff=sum(r["status"] == "waiting_for_sign_off" for r in rows),
        technical_issues=technical,
    )
