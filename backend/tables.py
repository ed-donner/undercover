"""The tables: UnderCover's records and the state of its work."""

from sqlalchemy import JSON, Boolean, Column, Integer, MetaData, String, Table

metadata = MetaData()

settings = Table(
    "settings",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", JSON, nullable=False),
)

plans = Table(
    "plans",
    metadata,
    Column("plan", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("trip_cancellation_max_cents", Integer, nullable=False),
    Column("trip_delay_waiting_hours", Integer, nullable=False),
    Column("trip_delay_max_cents", Integer, nullable=False),
    Column("baggage_delay_waiting_hours", Integer, nullable=False),
    Column("baggage_delay_max_cents", Integer, nullable=False),
    Column("baggage_max_cents", Integer, nullable=False),
    Column("per_item_limit_cents", Integer, nullable=False),
    Column("passport_max_cents", Integer, nullable=False),
    Column("emergency_medical_max_cents", Integer, nullable=False),
    Column("deductible_cents", Integer, nullable=False),
)

add_ons = Table(
    "add_ons",
    metadata,
    Column("add_on", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("effect", JSON, nullable=False),
    Column("electronics_per_item_limit_cents", Integer),
)

deductible_benefits = Table(
    "deductible_benefits", metadata, Column("benefit", String, primary_key=True)
)

policies = Table(
    "policies",
    metadata,
    Column("policy_id", String, primary_key=True),
    Column("customer_id", String, nullable=False),
    Column("plan", String, nullable=False),
    Column("purchased_on", String, nullable=False),
    Column("sold_through", String, nullable=False),
    Column("status", String, nullable=False),
    Column("add_ons", JSON, nullable=False),
    Column("trip", JSON, nullable=False),
    Column("travelers", JSON, nullable=False),
)

customers = Table(
    "customers",
    metadata,
    Column("customer_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("phone", String, nullable=False),
    Column("date_of_birth", String, nullable=False),
    Column("customer_since", String, nullable=False),
    Column("address", JSON, nullable=False),
    Column("previous_claims", JSON, nullable=False),
)

handlers = Table(
    "handlers",
    metadata,
    Column("handler_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("role", String, nullable=False),
    Column("email", String, nullable=False),
    Column("can_approve_over_limit", Boolean, nullable=False),
)

document_sections = Table(
    "document_sections",
    metadata,
    Column("document", String, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("heading", String, nullable=False),
    Column("text", String, nullable=False),
)

claims = Table(
    "claims",
    metadata,
    Column("claim_id", String, primary_key=True),
    Column("policy_id", String, nullable=False),
    Column("customer_id", String, nullable=False),
    Column("claim_type", String, nullable=False),
    Column("submitted_on", String, nullable=False),
    Column("incident_date", String, nullable=False),
    Column("incident_location", String, nullable=False),
    Column("summary", String, nullable=False),
    Column("story", String, nullable=False),
    Column("amount_claimed_cents", Integer, nullable=False),
    Column("items", JSON, nullable=False),
    Column("documents", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("thread", Integer, nullable=False, server_default="1"),
    Column("decision", String),
    Column("payout_cents", Integer),
    Column("reason", String),
    Column("policy_reference", String),
    Column("decided_on", String),
    Column("over_approval_limit", Integer),
    Column("signed_off_by", String),
    Column("signed_off_on", String),
    Column("paid_cents", Integer),
    Column("paid_on", String),
    Column("lease_owner", String),
    Column("lease_expires_on", String),
)

STATE_COLUMNS = [
    claims.c[name]
    for name in [
        "claim_id",
        "status",
        "thread",
        "decision",
        "payout_cents",
        "reason",
        "policy_reference",
        "decided_on",
        "over_approval_limit",
        "signed_off_by",
        "signed_off_on",
        "paid_cents",
        "paid_on",
    ]
]
CONTENT_COLUMNS = [
    claims.c[name]
    for name in [
        "claim_id",
        "policy_id",
        "customer_id",
        "claim_type",
        "submitted_on",
        "incident_date",
        "incident_location",
        "summary",
        "story",
        "amount_claimed_cents",
        "items",
        "documents",
    ]
]

claim_steps = Table(
    "claim_steps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("claim_id", String, nullable=False),
    Column("recorded_on", String, nullable=False),
    Column("text", String, nullable=False),
)

runs = Table(
    "runs",
    metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("started_on", String, nullable=False),
    Column("finished_on", String),
    Column("summary", String),
)

run_items = Table(
    "run_items",
    metadata,
    Column("run_id", Integer, primary_key=True),
    Column("claim_id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("note", String),
)
