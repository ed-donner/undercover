"""A stand-in swarm that saves to Postgres, for crashing on purpose.

The notebook runs this file as its own process, kills that process while the stand-ins are working,
then resumes the same thread itself with build(). Each stand-in writes a row to lab.stand_in_log when
it starts and marks it when it finishes, so we can see which claims LangGraph works again.

Run: python week2day4_crash_swarm.py <thread_id> <claim_id> [<claim_id> ...]
"""

import operator
import os
import sys
import time
from typing import Annotated, TypedDict

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from psycopg.rows import dict_row

MAX_CONCURRENCY = 5


class Dispatch(TypedDict):
    """What the dispatcher keeps for one run."""

    claims: list[str]
    results: Annotated[list, operator.add]
    scores: dict


def connect():
    """A connection with the settings LangGraph's checkpointer needs, in the lab schema."""
    load_dotenv("../../.env", override=True)
    connection = psycopg.connect(
        os.environ["DATABASE_URL"], autocommit=True, prepare_threshold=0, row_factory=dict_row, options="-c search_path=lab"
    )
    connection.execute("CREATE SCHEMA IF NOT EXISTS lab")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS stand_in_log ("
        "id SERIAL PRIMARY KEY, thread_id TEXT, claim_id TEXT, pid INTEGER,"
        " started TIMESTAMPTZ DEFAULT now(), finished TIMESTAMPTZ)"
    )
    return connection


def build(connection, claim_ids, thread_id):
    """The dispatcher with a slow stand-in and the score_run node, saved by PostgresSaver."""

    def list_claims(state: Dispatch):
        """The claims to work in this run."""
        return {"claims": claim_ids}

    def fan_out(state: Dispatch):
        """Send each claim to a stand-in."""
        return [Send("work_claim", claim_id) for claim_id in state["claims"]]

    def slow_stand_in(claim_id):
        """Pretend to work a claim for 2 to 6 seconds, logging the start and the finish."""
        row = connection.execute(
            "INSERT INTO stand_in_log (thread_id, claim_id, pid) VALUES (%s, %s, %s) RETURNING id",
            (thread_id, claim_id, os.getpid()),
        ).fetchone()
        time.sleep(2 + claim_ids.index(claim_id) % 5)
        connection.execute("UPDATE stand_in_log SET finished = now() WHERE id = %s", (row["id"],))
        return {"results": [{"claim_id": claim_id}]}

    def score_run(state: Dispatch):
        """Count the results once every stand-in has finished."""
        return {"scores": {"claims": len(state["results"])}}

    checkpointer = PostgresSaver(connection)
    checkpointer.setup()
    builder = StateGraph(Dispatch)
    builder.add_node("list_claims", list_claims)
    builder.add_node("work_claim", slow_stand_in)
    builder.add_node("score_run", score_run)
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim"])
    builder.add_edge("work_claim", "score_run")
    builder.add_edge("score_run", END)
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    thread_id, *claim_ids = sys.argv[1:]
    connection = connect()
    graph = build(connection, claim_ids, thread_id)
    config = {"configurable": {"thread_id": thread_id}, "max_concurrency": MAX_CONCURRENCY}
    graph.invoke({}, config, durability=os.getenv("DURABILITY", "async"))
