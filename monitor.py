"""A monitor for your AWS spend: uv run monitor.py

It reads two daily cost budgets in AWS Budgets, one with everything you use and one with
what's left to pay after your credits, and shows today and the last 30 days on a page
that checks again every 5 minutes. The first run creates the two budgets in your
account. Budgets with no alerts are free, and so is reading them. AWS updates the
figures up to three times a day, so they can be several hours behind your actual use."""

from datetime import UTC, datetime, timedelta

import boto3
import gradio as gr
import plotly.graph_objects as go

ALL_SPEND = "shoppie-daily-spend"
AFTER_CREDITS = "shoppie-daily-spend-after-credits"
CHECK_EVERY_SECONDS = 5 * 60
DAYS = 30

# A cost budget subtracts your credits from your spend unless it filters them out
WITHOUT_CREDITS = {
    "Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}
}

# Each number is green below the first amount, yellow up to the second and red above
TODAY_LIMITS = (0.10, 1.00)
MONTH_LIMITS = (1.00, 10.00)
OFFICIAL = (
    "For the official source of truth, please review Billing and Cost Management in "
    "your AWS console. Always have budgets with billing alerts."
)
GREEN, YELLOW, RED, INK, BLUE = "#069D75", "#FFD166", "#EF476F", "#073B4C", "#118AB2"

session = boto3.Session()
account = session.client("sts").get_caller_identity()["Account"]
budgets = session.client("budgets")


def make_budget(name, filter_expression=None):
    """Create a daily cost budget with no alerts, unless it already exists. The
    limit only matters for alerts, so any amount will do."""
    budget = {
        "BudgetName": name,
        "BudgetLimit": {"Amount": "1.0", "Unit": "USD"},
        "TimeUnit": "DAILY",
        "BudgetType": "COST",
        "Metrics": ["UnblendedCost"],
    }
    if filter_expression:
        budget["FilterExpression"] = filter_expression
    try:
        budgets.create_budget(AccountId=account, Budget=budget)
        print(f"Created the budget {name} in your account")
    except budgets.exceptions.DuplicateRecordException:
        pass


def read_budget(name):
    """Each day's spend on a daily budget by UTC date, and when AWS last updated it."""
    now = datetime.now(UTC)
    period = {"Start": now - timedelta(days=DAYS), "End": now}
    pages = budgets.get_paginator("describe_budget_performance_history").paginate(
        AccountId=account, BudgetName=name, TimePeriod=period
    )
    spend = {}
    for page in pages:
        for day in page["BudgetPerformanceHistory"]["BudgetedAndActualAmountsList"]:
            # Skip days AWS hasn't filled in yet, such as today
            if "ActualAmount" not in day:
                continue
            date = day["TimePeriod"]["Start"].astimezone(UTC).date()
            spend[date] = float(day["ActualAmount"]["Amount"])
    budget = budgets.describe_budget(AccountId=account, BudgetName=name)["Budget"]
    if "CalculatedSpend" in budget:
        spend[now.date()] = float(budget["CalculatedSpend"]["ActualSpend"]["Amount"])
    return spend, budget["LastUpdatedTime"]


def card(title, amount, note, limits):
    """A big dollar amount on a card that's green, yellow or red by the limits."""
    low, high = limits
    color = GREEN if amount < low else YELLOW if amount <= high else RED
    text = INK if color == YELLOW else "white"
    shape = "border-radius:12px; padding:20px; text-align:center"
    return f"""
<div style="background:{color}; color:{text}; {shape}">
  <div style="font-size:18px; font-weight:600">{title}</div>
  <div style="font-size:52px; font-weight:700; margin:8px 0">${amount:,.2f}</div>
  <div style="font-size:14px">{note}</div>
</div>"""


def total(spend, first_day):
    """The spend on each day from the first day on, added up."""
    return sum(amount for date, amount in spend.items() if date >= first_day)


def spend_chart(all_spend, after_credits, first_day):
    """A line for each budget's daily spend, from the first day on."""
    chart = go.Figure()
    lines = [
        ("All spend", all_spend, BLUE, "solid"),
        ("After credits", after_credits, GREEN, "dot"),
    ]
    for name, spend, color, dash in lines:
        days = sorted(date for date in spend if date >= first_day)
        chart.add_scatter(
            x=[f"{date:%b} {date.day}" for date in days],
            y=[spend[date] for date in days],
            name=name,
            mode="lines+markers",
            line={"color": color, "dash": dash, "width": 3},
            marker={"size": 10},
        )
    grid = "rgba(128,128,128,0.25)"
    chart.update_layout(
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#888888", "size": 14},
        legend={"orientation": "h", "y": 1.1},
        margin={"l": 60, "r": 20, "t": 40, "b": 50},
        xaxis={"title": "Day (UTC)", "gridcolor": grid, "type": "category"},
        yaxis={
            "title": "US dollars",
            "gridcolor": grid,
            "zerolinecolor": grid,
            "tickprefix": "$",
            "tickformat": ".2f",
            "rangemode": "tozero",
        },
    )
    return chart


def refresh():
    """Read both budgets and return the four cards, the chart and a status line."""
    all_spend, updated = read_budget(ALL_SPEND)
    after_credits, _ = read_budget(AFTER_CREDITS)
    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=DAYS - 1)
    earliest = min(all_spend, default=today)
    period = (
        "Last 30 days"
        if earliest <= first_day
        else f"Since {earliest:%b} {earliest.day}"
    )

    everything, paid = "Including what credits paid for", "What you pay after credits"
    status = (
        f"AWS last updated these figures at {updated.astimezone():%H:%M}, and updates "
        f"them up to three times a day. Checked at {datetime.now():%H:%M:%S}.\n\n"
        f"{OFFICIAL}"
    )
    return (
        card("Today (UTC)", all_spend.get(today, 0.0), everything, TODAY_LIMITS),
        card("Today (UTC)", after_credits.get(today, 0.0), paid, TODAY_LIMITS),
        card(period, total(all_spend, first_day), everything, MONTH_LIMITS),
        card(period, total(after_credits, first_day), paid, MONTH_LIMITS),
        spend_chart(all_spend, after_credits, first_day),
        status,
    )


with gr.Blocks(title="AWS spend") as demo:
    gr.Markdown(f"# AWS spend\nAccount {account}, from AWS Budgets")
    with gr.Row(equal_height=True):
        cards = [gr.HTML(apply_default_css=False) for _ in range(4)]
    chart = gr.Plot(show_label=False)
    status = gr.Markdown()
    outputs = [*cards, chart, status]
    demo.load(refresh, outputs=outputs)
    gr.Timer(CHECK_EVERY_SECONDS).tick(refresh, outputs=outputs)


if __name__ == "__main__":
    make_budget(ALL_SPEND, WITHOUT_CREDITS)
    make_budget(AFTER_CREDITS)
    demo.launch(inbrowser=True, footer_links=[])
