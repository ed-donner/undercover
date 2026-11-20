"""Write the loan applications and the underwriters' decisions for the loan approval lab.

The decisions are worked out from the rules in data/lending_policy.md, so the labels
always match the policy. Run it from this folder: python make_data.py
"""

import json
import math
from datetime import date
from pathlib import Path

DATA = Path(__file__).parent / "data"
APPLIED_ON = date(2026, 10, 1)

PRODUCTS = {
    "personal": {"minimum": 1_000, "maximum": 40_000},
    "car": {"minimum": 5_000, "maximum": 60_000},
}
PAYMENT_FACTORS = {24: 0.047, 36: 0.033, 60: 0.022}
PROHIBITED = {"gambling", "cryptocurrency", "business"}


def doc(type_, name, content):
    return {"type": type_, "name": name, "content": content}


def id_doc(name):
    return doc("id", "Driver's license", f"State driver's license for {name}, valid until 2030.")


def payslip(name, employer, salary):
    return doc("payslip", "Last three payslips", f"{employer} payslips for {name}, July to September 2026. Annual salary ${salary:,}, paid monthly at ${salary / 12:,.2f} gross.")


def bank_statement(name, extra=""):
    return doc("bank_statement", "Bank statement, three months", f"Checking account for {name}, July to September 2026. Regular salary or business deposits, rent and household spending.{extra}")


def payslip_biweekly(name, employer, salary):
    return doc("payslip", "Last six payslips", f"{employer} payslips for {name}, July to September 2026. Paid every two weeks at ${salary / 26:,.2f} gross.")


def tax_return(name, year, income):
    return doc("tax_return", f"Tax return {year}", f"Tax return for {name}, tax year {year}. Net business income ${income:,}.")


def vehicle_quote(price, vehicle):
    return doc("vehicle_quote", "Vehicle quote", f"Dealer quote for a {vehicle}. Price ${price:,} including taxes and fees.")


# Each case is the application, plus what it is there to test and how hard it is.
CASES = [
    dict(name="Maya Patel", product="personal", amount=10_000, term=36, purpose="home improvements", story="I want to replace the windows in my house before winter.",
         age=34, residency="citizen", employment="employee", employer="Northwind Logistics", months=52, stated=72_000, score=720, debt=400,
         docs=["id", "payslip", "bank"], salary=72_000, difficulty="routine", tests="A routine approval with every document attached"),
    dict(name="Daniel Okafor", product="car", amount=25_000, term=60, purpose="car purchase", story="Buying a two-year-old SUV from a dealer to replace my old car.",
         age=41, residency="citizen", employment="employee", employer="Harbor Health", months=96, stated=95_000, score=760, debt=600,
         docs=["id", "payslip", "bank", "quote"], salary=95_000, price=27_000, vehicle="2024 Toyota RAV4", difficulty="routine", tests="A routine car loan approval"),
    dict(name="Lena Fischer", product="personal", amount=6_000, term=36, purpose="debt consolidation", story="I want to pay off two credit cards with one loan.",
         age=29, residency="citizen", employment="employee", employer="City Bakery", months=30, stated=41_000, score=560, debt=350,
         docs=["id", "payslip", "bank"], salary=41_000, difficulty="routine", tests="A credit score below 580 is a hard decline"),
    dict(name="Marcus Reed", product="personal", amount=8_000, term=36, purpose="medical bills", story="I have some medical bills from earlier this year to pay off.",
         age=45, residency="citizen", employment="employee", employer="Reed Plumbing Supply", months=70, stated=58_000, score=650, debt=300,
         bankruptcy="2025-12-10", docs=["id", "payslip", "bank"], salary=58_000, difficulty="routine", tests="A bankruptcy discharged 10 months ago is a hard decline"),
    dict(name="Priya Shah", product="personal", amount=7_500, term=24, purpose="wedding", story="Paying for part of my wedding next spring.",
         age=31, residency="citizen", employment="employee", employer="Bluefin Software", months=40, stated=88_000, score=735, debt=200,
         docs=["id", "bank"], difficulty="routine", tests="Missing payslips means a referral"),
    dict(name="Tom Becker", product="personal", amount=20_000, term=60, purpose="home improvements", story="Renovating the kitchen.",
         age=38, residency="citizen", employment="employee", employer="Becker & Sons Roofing", months=60, stated=48_000, score=650, debt=300,
         docs=["id", "payslip", "bank"], salary=48_000, difficulty="hard", tests="The income limit at 25% cuts the loan to $12,000"),
    dict(name="Aisha Bello", product="personal", amount=15_000, term=36, purpose="debt consolidation", story="Consolidating a car loan and a store card.",
         age=36, residency="permanent_resident", employment="employee", employer="Greenway Schools", months=84, stated=60_000, score=700, debt=1_600,
         docs=["id", "payslip", "bank"], salary=60_000, difficulty="hard", tests="DTI over 40% means reducing the loan until it fits"),
    dict(name="Kevin Liu", product="personal", amount=8_000, term=24, purpose="vacation", story="A family trip to Japan.",
         age=27, residency="citizen", employment="employee", employer="Metro Transit", months=26, stated=36_000, score=690, debt=1_180,
         docs=["id", "payslip", "bank"], salary=36_000, difficulty="hard", tests="Existing debts leave no room for any loan above the product minimum"),
    dict(name="Sofia Romano", product="personal", amount=12_000, term=36, purpose="furniture", story="Furnishing a new apartment.",
         age=33, residency="citizen", employment="employee", employer="Romano Interiors", months=44, stated=85_000, score=710, debt=500,
         docs=["id", "payslip", "bank"], salary=70_000, difficulty="hard", tests="Stated income 21% above the payslips is a referral"),
    dict(name="James Carter", product="personal", amount=32_000, term=60, purpose="home improvements", story="Adding a deck and redoing the bathroom.",
         age=47, residency="citizen", employment="employee", employer="Carter Engineering", months=120, stated=66_000, score=745, debt=900,
         docs=["id", "payslip", "bank"], salary=62_000, difficulty="hard", tests="Stated income within 10%, but the income limit uses the verified $62,000"),
    dict(name="Elena Petrova", product="personal", amount=26_000, term=36, purpose="home improvements", story="New roof and gutters on our house.",
         age=39, residency="citizen", employment="self_employed", employer="Petrova Design (own business)", months=30, stated=66_000, score=710, debt=500,
         docs=["id", "tax", "bank"], tax=(54_000, 66_000), difficulty="hard", tests="Self-employed income is the average of two years, not the latest year"),
    dict(name="Ryan Murphy", product="personal", amount=10_000, term=36, purpose="equipment", story="Buying a new laptop and camera kit for my photography.",
         age=28, residency="citizen", employment="self_employed", employer="Murphy Photo (own business)", months=18, stated=52_000, score=705, debt=250,
         docs=["id", "tax", "bank"], tax=(40_000, 52_000), difficulty="hard", tests="Self-employed for 18 months is a hard decline"),
    dict(name="Grace Kim", product="personal", amount=4_000, term=24, purpose="car repairs", story="My car needs a new transmission.",
         age=25, residency="citizen", employment="employee", employer="Sunrise Diner", months=22, stated=34_000, score=600, debt=150,
         docs=["id", "payslip", "bank"], salary=34_000, difficulty="hard", tests="A credit score of 600 is a referral, not a decline"),
    dict(name="Arjun Mehta", product="personal", amount=9_000, term=36, purpose="relocation", story="Moving costs for my new job in Denver.",
         age=30, residency="temporary_resident", employment="employee", employer="Summit Analytics", months=14, stated=110_000, score=740, debt=0,
         docs=["id", "payslip", "bank"], salary=110_000, difficulty="hard", tests="A temporary resident is referred despite strong numbers"),
    dict(name="Nathan Cole", product="personal", amount=15_000, term=36, purpose="cryptocurrency", story="I want to buy more Bitcoin while the price is low.",
         age=35, residency="citizen", employment="employee", employer="Cole Freight", months=58, stated=90_000, score=780, debt=400,
         docs=["id", "payslip", "bank"], salary=90_000, difficulty="hard", tests="Buying cryptocurrency is a prohibited purpose"),
    dict(name="Hannah Weber", product="car", amount=30_000, term=60, purpose="car purchase", story="Buying a used hatchback from a dealer.",
         age=32, residency="citizen", employment="employee", employer="Weber Dental", months=48, stated=80_000, score=730, debt=400,
         docs=["id", "payslip", "bank", "quote"], salary=80_000, price=24_000, vehicle="2023 Honda Civic", difficulty="hard", tests="A car loan is capped at the vehicle price"),
    dict(name="Luis Garcia", product="car", amount=18_000, term=60, purpose="car purchase", story="Buying a pickup truck for my commute.",
         age=44, residency="citizen", employment="employee", employer="Garcia Landscaping Co", months=90, stated=75_000, score=725, debt=500,
         docs=["id", "payslip", "bank"], salary=75_000, difficulty="hard", tests="A car loan without a vehicle quote is referred"),
    dict(name="Olivia Brown", product="personal", amount=5_000, term=24, purpose="moving costs", story="Moving to a bigger apartment.",
         age=29, residency="citizen", employment="employee", employer="Brown & Hart Law", months=36, stated=68_000, score=700, debt=300, missed=3,
         docs=["id", "payslip", "bank"], salary=68_000, difficulty="hard", tests="Three missed payments is a hard decline despite a good score"),
    dict(name="Ethan Walsh", product="personal", amount=6_000, term=36, purpose="furniture", story="Furnishing my first home.",
         age=26, residency="citizen", employment="employee", employer="Walsh Media", months=4, stated=62_000, score=715, debt=200,
         docs=["id", "payslip", "bank"], salary=62_000, difficulty="hard", tests="Four months in the current job is a referral"),
    dict(name="Chloe Martin", product="personal", amount=10_000, term=36, purpose="debt consolidation", story="Combining two credit card balances.",
         age=40, residency="citizen", employment="employee", employer="Martin Consulting", months=75, stated=60_000, score=745, debt=1_800,
         docs=["id", "payslip", "bank"], salary=60_000, difficulty="hard", tests="DTI of 42.6% is allowed because the 745 score gets the 45% limit"),
    dict(name="Ben Turner", product="personal", amount=12_000, term=36, purpose="home improvements", story="Replacing the furnace. I have no other loans or debts.",
         age=37, residency="citizen", employment="employee", employer="Turner Electric", months=64, stated=70_000, score=705, debt=0,
         docs=["id", "payslip", "bank"], salary=70_000, bank_extra=" A payment of $650 goes to QuickCash Loans on the 3rd of every month.",
         difficulty="hard", tests="The bank statement shows a $650 monthly loan the application does not declare"),
    dict(name="Zoe Adams", product="personal", amount=5_000, term=24, purpose="vacation", story="A trip to Italy for our anniversary.",
         age=50, residency="citizen", employment="employee", employer="Adams Pharmacy", months=150, stated=82_000, score=770, debt=300,
         docs=["id", "payslip", "bank"], salary=82_000, difficulty="routine", tests="A small routine approval"),
    dict(name="Samuel Ortiz", product="personal", amount=9_000, term=36, purpose="car repairs", story="Fixing my car and catching up on a few bills.",
         age=43, residency="citizen", employment="employee", employer="Ortiz Auto Body", months=80, stated=54_000, score=640, debt=350,
         bankruptcy="2024-03-15", docs=["id", "payslip", "bank"], salary=54_000, difficulty="hard", tests="A bankruptcy 30 months ago is not a decline, and the 25% income limit applies"),
    dict(name="Isabella Rossi", product="personal", amount=50_000, term=60, purpose="home improvements", story="A full basement renovation.",
         age=52, residency="citizen", employment="employee", employer="Rossi Architects", months=200, stated=150_000, score=780, debt=1_000,
         docs=["id", "payslip", "bank"], salary=150_000, difficulty="hard", tests="A request above the $40,000 personal loan maximum"),
    dict(name="Noah Jensen", product="personal", amount=7_000, term=36, purpose="medical bills", story="Paying for dental work.",
         age=36, residency="citizen", employment="employee", employer="Jensen Hardware", months=55, stated=57_000, score=690, debt=450, missed=2,
         docs=["id", "payslip", "bank"], salary=57_000, difficulty="hard", tests="Two missed payments is under the limit of three"),
    # The harder cases: boundaries, two rules at once, and income that has to be worked out
    dict(name="Ava Thompson", product="personal", amount=18_000, term=60, purpose="home improvements", story="Finishing the attic as a home office.",
         age=35, residency="citizen", employment="employee", employer="Thompson Realty", months=40, stated=54_000, score=660, debt=1_550,
         docs=["id", "payslip", "bank"], salary=54_000, difficulty="harder", tests="The income limit cuts to $13,500, then DTI cuts again to $11,000"),
    dict(name="Leo Nguyen", product="personal", amount=20_000, term=36, purpose="debt consolidation", story="Paying off a personal loan and a credit card.",
         age=33, residency="citizen", employment="employee", employer="Nguyen Dental Lab", months=58, stated=72_000, score=700, debt=1_972,
         docs=["id", "payslip", "bank"], salary=72_000, difficulty="harder", tests="The DTI limit allows $12,969, which rounds down to $12,500, not up to $13,000"),
    dict(name="Mia Clarke", product="personal", amount=15_000, term=36, purpose="furniture", story="Furnishing our new house.",
         age=42, residency="citizen", employment="employee", employer="Clarke Accounting", months=110, stated=60_000, score=739, debt=1_650,
         docs=["id", "payslip", "bank"], salary=60_000, difficulty="harder", tests="A score of 739 gets the 40% DTI limit, not 45%"),
    dict(name="Owen Price", product="personal", amount=6_000, term=24, purpose="car repairs", story="New tires and brakes, and a clutch.",
         age=24, residency="citizen", employment="employee", employer="Price Hardware", months=28, stated=40_000, score=620, debt=300,
         docs=["id", "payslip", "bank"], salary=40_000, difficulty="harder", tests="A score of exactly 620 is not a referral"),
    dict(name="Ruby Hall", product="personal", amount=10_000, term=36, purpose="wedding", story="Paying for our wedding reception.",
         age=30, residency="citizen", employment="employee", employer="Hall Events", months=45, stated=66_000, score=700, debt=500,
         docs=["id", "payslip", "bank"], salary=60_000, difficulty="harder", tests="Stated income exactly 10% above verified is not more than 10%, so no referral"),
    dict(name="Felix Wright", product="personal", amount=9_000, term=36, purpose="home improvements", story="Replacing the fence and the patio.",
         age=39, residency="citizen", employment="employee", employer="Wright Machining", months=66, stated=75_000, score=720, debt=400,
         docs=["id", "payslip", "bank"], salary=68_000, difficulty="harder", tests="Stated income 10.3% above verified is just over the line, a referral"),
    dict(name="Nora Evans", product="personal", amount=12_000, term=36, purpose="home improvements", story="Replacing the windows and the front door of my house.",
         age=46, residency="citizen", employment="self_employed", employer="Evans Pottery (own business)", months=24, stated=58_000, score=725, debt=300,
         docs=["id", "tax1", "bank"], tax=(55_000, 58_000), difficulty="harder", tests="Self-employed with only one tax return is a missing document"),
    dict(name="Isaac Hughes", product="personal", amount=5_000, term=36, purpose="medical bills", story="Paying for physiotherapy after a sports injury.",
         age=48, residency="citizen", employment="employee", employer="Hughes Freight", months=88, stated=50_000, score=640, debt=200,
         bankruptcy="2024-10-01", docs=["id", "payslip", "bank"], salary=50_000, difficulty="harder", tests="A bankruptcy discharged exactly 24 months ago is not a decline"),
    dict(name="Ella Price", product="personal", amount=4_000, term=24, purpose="moving costs", story="Moving across the state for my partner's new job.",
         age=37, residency="citizen", employment="employee", employer="Lakeside Clinic", months=50, stated=52_000, score=690, debt=250,
         bankruptcy="2024-11-15", docs=["id", "payslip", "bank"], salary=52_000, difficulty="harder", tests="A bankruptcy discharged 22 months ago is a decline"),
    dict(name="Jack Morris", product="personal", amount=3_000, term=24, purpose="car repairs", story="My car failed its inspection.",
         age=32, residency="citizen", employment="employee", employer="Morris Storage", months=20, stated=38_000, score=570, debt=200,
         docs=["id", "bank"], difficulty="harder", tests="A hard decline comes before the referral for a missing payslip"),
    dict(name="Lily Foster", product="personal", amount=7_000, term=24, purpose="inventory for my online shop",
         story="I sell handmade candles online alongside my day job and need to buy wax and jars in bulk for the holiday season.",
         age=29, residency="citizen", employment="employee", employer="Foster Pediatrics", months=34, stated=61_000, score=735, debt=200, prohibited=True,
         docs=["id", "payslip", "bank"], salary=61_000, difficulty="harder", tests="Stock for an online shop is business use on a personal loan"),
    dict(name="Caleb Ward", product="car", amount=9_000, term=60, purpose="car purchase", story="Buying an older car to get to work.",
         age=23, residency="citizen", employment="employee", employer="Ward Warehouse", months=18, stated=30_000, score=650, debt=900,
         docs=["id", "payslip", "bank", "quote"], salary=30_000, price=9_000, vehicle="2016 Ford Focus", difficulty="harder",
         tests="The most that fits is $4,500, below the $5,000 car loan minimum"),
    dict(name="Emma Scott", product="personal", amount=30_000, term=60, purpose="home improvements", story="Solar panels and a new water heater.",
         age=41, residency="citizen", employment="employee", employer="Scott Engineering", months=72, stated=65_000, score=690, debt=400,
         docs=["id", "payslip_biweekly", "bank"], salary=65_000, difficulty="harder", tests="Biweekly pay of $2,500 is $65,000 a year (26 paydays), not $60,000"),
    dict(name="Victor Lee", product="personal", amount=15_000, term=60, purpose="home improvements", story="Renovating the bathroom. Business has been great this year.",
         age=44, residency="citizen", employment="self_employed", employer="Lee Contracting (own business)", months=48, stated=90_000, score=730, debt=600,
         docs=["id", "tax", "bank"], tax=(30_000, 90_000), difficulty="harder", tests="Stated income matches the latest year but is far above the two-year average"),
    dict(name="Ivy Bennett", product="car", amount=28_000, term=60, purpose="car purchase", story="Buying a new electric car.",
         age=38, residency="citizen", employment="employee", employer="Bennett Pharmacy", months=60, stated=60_000, score=740, debt=1_650,
         docs=["id", "payslip", "bank", "quote"], salary=60_000, price=26_000, vehicle="2026 Hyundai Kona Electric", difficulty="harder",
         tests="Capped at the vehicle price, and a score of exactly 740 gets the 45% DTI limit"),
    dict(name="Max Rivera", product="personal", amount=8_000, term=36, purpose="furniture", story="Furnishing my apartment after moving for my new job.",
         age=27, residency="citizen", employment="employee", employer="Rivera Biotech", months=6, stated=58_000, score=710, debt=300,
         docs=["id", "payslip", "bank"], salary=58_000, difficulty="harder", tests="Exactly 6 months in the job is not a referral"),
]


def build(number, case):
    """Turn a case into the application the model sees."""
    name = case["name"]
    builders = {
        "id": lambda: [id_doc(name)],
        "payslip": lambda: [payslip(name, case["employer"], case["salary"])],
        "payslip_biweekly": lambda: [payslip_biweekly(name, case["employer"], case["salary"])],
        "bank": lambda: [bank_statement(name, case.get("bank_extra", ""))],
        "tax": lambda: [tax_return(name, 2024, case["tax"][0]), tax_return(name, 2025, case["tax"][1])],
        "tax1": lambda: [tax_return(name, 2025, case["tax"][1])],
        "quote": lambda: [vehicle_quote(case["price"], case["vehicle"])],
    }
    return {
        "application_id": f"APP-{5000 + number}",
        "applied_on": APPLIED_ON.isoformat(),
        "product": case["product"],
        "amount_requested": case["amount"],
        "term_months": case["term"],
        "purpose": case["purpose"],
        "story": case["story"],
        "applicant": {
            "name": name,
            "age": case["age"],
            "residency": case["residency"],
            "employment_type": case["employment"],
            "employer": case["employer"],
            "months_in_current_job_or_business": case["months"],
            "stated_annual_income": case["stated"],
        },
        "credit_file": {
            "credit_score": case["score"],
            "existing_monthly_debt_payments": case["debt"],
            "missed_payments_last_12_months": case.get("missed", 0),
            "bankruptcy_discharged_on": case.get("bankruptcy"),
        },
        "documents": [document for key in case["docs"] for document in builders[key]()],
    }


def months_between(earlier, later):
    return (later.year - earlier.year) * 12 + later.month - earlier.month - (later.day < earlier.day)


def underwrite(case):
    """Apply the lending policy. Returns the decision, the approved amount and the reason."""
    score, product = case["score"], PRODUCTS[case["product"]]
    self_employed = case["employment"] == "self_employed"

    # Section 5: hard declines
    if case["age"] < 18:
        return "decline", 0, "The applicant is under 18 (section 5)."
    if score < 580:
        return "decline", 0, f"The credit score of {score} is below 580 (section 5)."
    if case.get("bankruptcy") and months_between(date.fromisoformat(case["bankruptcy"]), APPLIED_ON) < 24:
        return "decline", 0, "A bankruptcy was discharged within the last 24 months (section 5)."
    if case.get("missed", 0) >= 3:
        return "decline", 0, f"{case['missed']} missed payments in the last 12 months (section 5)."
    if self_employed and case["months"] < 24:
        return "decline", 0, f"Self-employed for {case['months']} months, less than 24 (section 5)."
    if case.get("prohibited"):
        return "decline", 0, "This is business use on a personal loan, a prohibited purpose (section 2)."
    if case["purpose"] in PROHIBITED:
        return "decline", 0, f"Lending for {case['purpose']} is a prohibited purpose (section 2)."

    # Section 6: referrals
    required = {"id", "bank", "tax" if self_employed else "payslip"} | ({"quote"} if case["product"] == "car" else set())
    attached = {key.removesuffix("_biweekly") for key in case["docs"]}
    if missing := required - attached:
        return "refer", 0, f"Required documents are missing: {', '.join(sorted(missing))} (section 3)."
    verified = sum(case["tax"]) / 2 if self_employed else case["salary"]
    if case["stated"] > verified * 1.10:
        return "refer", 0, f"Stated income ${case['stated']:,} is more than 10% above the verified ${verified:,.0f} (section 4)."
    if score < 620:
        return "refer", 0, f"A credit score of {score} is in the 580 to 619 referral band (section 6)."
    if case["residency"] == "temporary_resident":
        return "refer", 0, "Temporary residents are referred (section 6)."
    if not self_employed and case["months"] < 6:
        return "refer", 0, f"Only {case['months']} months in the current job (section 6)."
    if "bank_extra" in case:
        return "refer", 0, "The bank statement shows a loan repayment that the application does not declare (section 6)."

    # Sections 7 to 9: the approved amount
    multiple = 0.25 if score < 680 else 0.40 if score < 740 else 0.50
    caps = [case["amount"], product["maximum"], verified * multiple] + ([case["price"]] if case["product"] == "car" else [])
    amount = min(caps)
    steps = [f"Income limit {multiple:.0%} of ${verified:,.0f} is ${verified * multiple:,.0f}"]
    factor = PAYMENT_FACTORS[case["term"]]
    monthly_income = verified / 12
    limit = 0.45 if score >= 740 else 0.40
    dti = (case["debt"] + amount * factor) / monthly_income
    if dti > limit:
        amount = (limit * monthly_income - case["debt"]) / factor
        steps.append(f"DTI of {dti:.1%} is over {limit:.0%}, so the amount is reduced to fit")
    else:
        steps.append(f"DTI of {dti:.1%} is within {limit:.0%}")
    if amount < case["amount"]:
        amount = max(0, math.floor(amount / 500) * 500)
    if amount < product["minimum"]:
        return "decline", 0, ". ".join(steps) + f". The most that fits is below the ${product['minimum']:,} minimum (section 9)."
    return "approve", float(amount), ". ".join(steps) + f". Approve ${amount:,.0f} (section 9)."


def main():
    applications, decisions = [], []
    for number, case in enumerate(CASES, start=1):
        application = build(number, case)
        decision, amount, reason = underwrite(case)
        applications.append(application)
        decisions.append({
            "application_id": application["application_id"],
            "decision": decision,
            "approved_amount": amount,
            "reason": reason,
            "tests": case["tests"],
            "difficulty": case["difficulty"],
        })
        print(f"{application['application_id']} {decision:8} ${amount:>9,.0f}  {reason}")
    (DATA / "applications.json").write_text(json.dumps(applications, indent=2), encoding="utf-8")
    (DATA / "decisions.json").write_text(json.dumps(decisions, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
