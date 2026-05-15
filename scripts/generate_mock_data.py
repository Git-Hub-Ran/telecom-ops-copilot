"""
generate_mock_data.py

Generates the four mock data files used by the Telecom Ops Copilot agent.

This script creates:
  - mock-data/customers.json    : 20 fake customer accounts
  - mock-data/billing.json      : up to 3 months of bills per customer
  - mock-data/outages.json      : a few active network outages
  - mock-data/diagnostics.json  : speed test data per customer

Run from the project root:
    python scripts/generate_mock_data.py

The script uses a fixed random seed so the output is the same on every run.
That makes evaluation tests stable. To get different data, change the SEED value.

This script is meant to be read as well as run. Each section has comments
explaining what it does and why.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# Fixed seed for repeatable random choices. Anyone running this script
# will get the exact same customers, bills, etc.
SEED = 42
random.seed(SEED)

# All dates in the data are relative to this anchor date.
# Bills, join dates, outages, etc. are computed from REFERENCE_DATE.
REFERENCE_DATE = date(2026, 5, 13)

# Where the output files go. This script lives in scripts/, so we go
# up one level (parent.parent) and into mock-data/.
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "mock-data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Prices and types come from the KB plan documents in kb/plans/.
# If you change a price here, also update the matching plan doc.
PLAN_PRICES = {
    "essential": 25,
    "connect": 45,
    "unlimited": 65,
    "internet_100": 50,
    "fiber_1000": 80,
}

PLAN_TYPES = {
    "essential": "mobile",
    "connect": "mobile",
    "unlimited": "mobile",
    "internet_100": "home_internet",
    "fiber_1000": "home_internet",
}

# ------------------------------------------------------------------
# Hand-designed customer profiles
# ------------------------------------------------------------------
#
# Each tuple is one customer. We hand-design these (instead of fully
# random generation) so the data covers diverse scenarios on purpose:
# - A few simple cases (single mobile, single internet)
# - Bundle customers (mobile + home internet, get $15 off)
# - Family accounts (multiple lines, get tiered discounts)
# - Discount programs (senior, military)
# - Edge cases (suspended, pending, recently joined)
#
# Format:
#   (account_id, name, plan_ids, join_year, status, payment_method, discounts, zip)

CUSTOMER_PROFILES = [
    # Simple single-service mobile customers
    ("ACC-10001", "John Smith",        ["essential"],                  2023, "active",    "autopay_card", ["autopay"],                  "10001"),
    ("ACC-10003", "Maria Garcia",      ["connect"],                    2022, "active",    "manual",        [],                          "60601"),
    ("ACC-10004", "David Lee",         ["essential"],                  2024, "suspended", "manual",        [],                          "94103"),
    ("ACC-10011", "Christopher Taylor",["unlimited"],                  2017, "active",    "autopay_card", ["autopay"],                  "80202"),
    ("ACC-10015", "Mark White",        ["unlimited"],                  2022, "suspended", "manual",        [],                          "37201"),
    ("ACC-10018", "Karen Thompson",    ["connect"],                    2020, "active",    "autopay_card", ["autopay"],                  "63101"),

    # Bundle customers (mobile + home internet, get $15 bundle discount)
    ("ACC-10002", "Sarah Johnson",     ["unlimited", "fiber_1000"],    2021, "active",    "autopay_card", ["autopay", "bundle"],        "90210"),
    ("ACC-10005", "Emily Chen",        ["unlimited", "internet_100"],  2022, "active",    "autopay_bank", ["autopay", "bundle"],        "02115"),
    ("ACC-10010", "Patricia Wilson",   ["connect", "internet_100"],    2026, "active",    "autopay_card", ["autopay", "bundle"],        "33139"),
    ("ACC-10016", "Susan Harris",      ["connect", "fiber_1000"],      2020, "active",    "autopay_card", ["autopay", "bundle"],        "98101"),
    ("ACC-10019", "Paul Garcia",       ["connect", "internet_100"],    2023, "active",    "autopay_card", ["autopay", "bundle", "military"], "30303"),

    # Home internet only
    ("ACC-10009", "Jennifer Martinez", ["fiber_1000"],                 2022, "active",    "autopay_card", ["autopay"],                  "78701"),
    ("ACC-10014", "Nancy Jackson",     ["internet_100"],               2024, "active",    "manual",        [],                          "53703"),

    # Family / multi-line accounts (get family discounts on extra lines)
    ("ACC-10006", "Robert Brown",      ["connect", "connect", "connect"],            2019, "active", "autopay_card", ["autopay", "family"], "75201"),
    ("ACC-10013", "Daniel Thomas",     ["unlimited", "unlimited", "connect"],        2018, "active", "autopay_card", ["autopay", "family"], "85001"),

    # Discount program customers
    ("ACC-10007", "Linda Williams",    ["connect"],                    2020, "active",    "autopay_card", ["autopay", "senior"],        "55401"),
    ("ACC-10008", "Michael Davis",     ["unlimited"],                  2021, "active",    "autopay_card", ["autopay", "military"],      "20001"),
    ("ACC-10012", "Barbara Anderson",  ["essential"],                  2023, "active",    "autopay_bank", ["autopay", "senior"],        "97201"),

    # New / pending customers
    ("ACC-10017", "Steven Martin",     ["unlimited"],                  2026, "active",    "autopay_card", ["autopay"],                  "73301"),
    ("ACC-10020", "Lisa Robinson",     ["essential"],                  2026, "pending",   "autopay_card", [],                            "27601"),
]


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def make_email(name):
    """Create a fake but realistic email address from a name."""
    first, last = name.lower().split(" ", 1)
    return f"{first}.{last.replace(' ', '')}@example.com"


def make_phone_contact(account_id):
    """Generate a unique contact phone for the account (not a line phone)."""
    # Use digits from the account_id to make the phone deterministic
    digits = account_id.split("-")[1]
    return f"+1-555-{digits[:3]}-{digits[1:]}"


# ------------------------------------------------------------------
# Customers
# ------------------------------------------------------------------

def generate_customers():
    """Turn the CUSTOMER_PROFILES tuples into full customer records."""
    customers = []

    for profile in CUSTOMER_PROFILES:
        account_id, name, plans, join_year, status, payment, discounts, billing_zip = profile

        # Pick a random month and day for the join date in the given year.
        # We avoid days > 28 so we never hit February issues.
        join_month = random.randint(1, 12)
        join_day = random.randint(1, 28)
        join_date = date(join_year, join_month, join_day)

        # Build the services list (one entry per plan line)
        services = []
        for i, plan_id in enumerate(plans):
            line_id = f"LINE-{account_id.split('-')[1]}-{i + 1}"

            # Mobile lines get a phone number, home internet does not
            if PLAN_TYPES[plan_id] == "mobile":
                phone_number = f"+1-555-{account_id.split('-')[1][-3:]}-{1000 + i}"
            else:
                phone_number = None

            services.append({
                "line_id": line_id,
                "type": PLAN_TYPES[plan_id],
                "plan_id": plan_id,
                "phone_number": phone_number,
                "status": "pending" if status == "pending" else "active",
                "activated_on": str(join_date),
            })

        # Build payment info. Card customers get a deterministic last 4 digits.
        if payment == "autopay_card":
            digits_hash = (int(account_id.split("-")[1]) * 7) % 10000
            card_last_four = f"{digits_hash:04d}"
            payment_info = {"method": "autopay_card", "card_last_four": card_last_four}
        elif payment == "autopay_bank":
            payment_info = {"method": "autopay_bank", "card_last_four": None}
        else:
            payment_info = {"method": "manual", "card_last_four": None}

        customers.append({
            "account_id": account_id,
            "name": name,
            "email": make_email(name),
            "phone_contact": make_phone_contact(account_id),
            "billing_zip": billing_zip,
            "join_date": str(join_date),
            "status": status,
            "services": services,
            "payment": payment_info,
            "discounts": discounts,
        })

    return customers


# ------------------------------------------------------------------
# Billing
# ------------------------------------------------------------------

def calculate_bill_amount(plans, discounts, is_autopay):
    """
    Calculate the line items and totals for one bill, applying all discounts
    in the same way the real billing system would.

    Returns: (line_items, subtotal, discount_total, taxes, total)
    """
    line_items = []
    subtotal = 0

    # 1. Plan charges, with family discount applied to extra mobile lines
    mobile_line_index = 0
    for plan_id in plans:
        price = PLAN_PRICES[plan_id]

        # Family discount kicks in on the 2nd mobile line and beyond
        if PLAN_TYPES[plan_id] == "mobile":
            mobile_line_index += 1
            if "family" in discounts:
                if mobile_line_index == 2:
                    price -= 10
                elif mobile_line_index == 3:
                    price -= 15
                elif mobile_line_index >= 4:
                    price -= 20

        line_items.append({
            "description": f"{plan_id.replace('_', ' ').title()} plan",
            "amount": price,
        })
        subtotal += price

    # 2. Apply remaining discounts
    discount_total = 0

    if "bundle" in discounts:
        line_items.append({"description": "Bundle discount", "amount": -15})
        discount_total -= 15

    if is_autopay:
        # $5 off per mobile line
        mobile_lines = sum(1 for p in plans if PLAN_TYPES[p] == "mobile")
        autopay_discount = -5 * mobile_lines
        if autopay_discount < 0:
            line_items.append({"description": "Autopay discount", "amount": autopay_discount})
            discount_total += autopay_discount

    if "senior" in discounts:
        line_items.append({"description": "Senior discount", "amount": -10})
        discount_total -= 10

    if "military" in discounts:
        # 15% off mobile plans only
        mobile_total = sum(PLAN_PRICES[p] for p in plans if PLAN_TYPES[p] == "mobile")
        military_discount = -round(mobile_total * 0.15, 2)
        if military_discount < 0:
            line_items.append({"description": "Military discount", "amount": military_discount})
            discount_total += military_discount

    # 3. Taxes (we use a flat 10% to keep things simple)
    pre_tax = subtotal + discount_total
    taxes = round(pre_tax * 0.10, 2)
    line_items.append({"description": "Taxes and fees", "amount": taxes})

    total = round(pre_tax + taxes, 2)

    return line_items, subtotal, discount_total, taxes, total


def generate_billing(customers):
    """Generate up to 3 months of billing history per customer."""
    bills = []

    for customer in customers:
        # Pending customers have no billing history yet
        if customer["status"] == "pending":
            continue

        account_id = customer["account_id"]
        plans = [s["plan_id"] for s in customer["services"]]
        discounts = customer["discounts"]
        is_autopay = "autopay" in discounts

        # Get billing cycle day from the join date
        join_date = date.fromisoformat(customer["join_date"])
        cycle_day = min(join_date.day, 28)

        # Generate the last 3 billing cycles before today
        for months_ago in [2, 1, 0]:
            # Compute the issue date for this cycle
            issue_year = REFERENCE_DATE.year
            issue_month = REFERENCE_DATE.month - months_ago
            while issue_month <= 0:
                issue_month += 12
                issue_year -= 1

            issue_date = date(issue_year, issue_month, cycle_day)

            # Skip bills that would be in the future
            if issue_date > REFERENCE_DATE:
                continue

            # Period end is one day before next cycle's issue date
            next_month = issue_month + 1
            next_year = issue_year
            if next_month > 12:
                next_month = 1
                next_year += 1
            period_end = date(next_year, next_month, cycle_day) - timedelta(days=1)

            due_date = issue_date + timedelta(days=21)

            # Calculate the bill amount using the helper
            line_items, subtotal, discount_total, taxes, total = calculate_bill_amount(
                plans, discounts, is_autopay
            )

            # Decide the payment status
            # Autopay customers always pay on time
            # Manual customers sometimes pay late (or not yet)
            if due_date < REFERENCE_DATE:
                if is_autopay:
                    status = "paid"
                    paid_date = str(due_date - timedelta(days=random.randint(0, 3)))
                else:
                    if random.random() < 0.7:
                        status = "paid"
                        paid_date = str(due_date + timedelta(days=random.randint(-3, 8)))
                    else:
                        status = "overdue"
                        paid_date = None
            else:
                # Bill not yet due
                if is_autopay:
                    status = "scheduled"
                else:
                    status = "unpaid"
                paid_date = None

            # Suspended customers must have at least one overdue bill in history
            if customer["status"] == "suspended" and months_ago == 1:
                status = "overdue"
                paid_date = None

            bill_id = f"BILL-{account_id.split('-')[1]}-{issue_year}{issue_month:02d}"

            bills.append({
                "bill_id": bill_id,
                "account_id": account_id,
                "billing_period_start": str(issue_date),
                "billing_period_end": str(period_end),
                "issue_date": str(issue_date),
                "due_date": str(due_date),
                "subtotal": subtotal,
                "discounts": discount_total,
                "taxes": taxes,
                "total": total,
                "status": status,
                "paid_date": paid_date,
                "line_items": line_items,
            })

    return bills


# ------------------------------------------------------------------
# Outages
# ------------------------------------------------------------------

def generate_outages():
    """A few active outages in different areas, hand-designed for variety."""
    return [
        {
            "outage_id": "OUT-2026-05-12-001",
            "type": "mobile",
            "zip_codes": ["10001", "10002", "10003"],
            "service_affected": "mobile_data_and_voice",
            "started_at": "2026-05-12T14:30:00Z",
            "estimated_resolution": "2026-05-13T18:00:00Z",
            "status": "active",
            "description": "Tower maintenance affecting mobile data and voice in lower Manhattan",
        },
        {
            "outage_id": "OUT-2026-05-13-001",
            "type": "home_internet",
            "zip_codes": ["94103", "94110"],
            "service_affected": "home_internet",
            "started_at": "2026-05-13T08:15:00Z",
            "estimated_resolution": "2026-05-13T20:00:00Z",
            "status": "active",
            "description": "Fiber cable damage during construction in San Francisco Mission District",
        },
        {
            "outage_id": "OUT-2026-05-13-002",
            "type": "mobile",
            "zip_codes": ["75201"],
            "service_affected": "mobile_data",
            "started_at": "2026-05-13T11:00:00Z",
            "estimated_resolution": "2026-05-13T15:00:00Z",
            "status": "active",
            "description": "Brief network upgrade in downtown Dallas, mobile data only",
        },
    ]


# ------------------------------------------------------------------
# Diagnostics
# ------------------------------------------------------------------

def generate_diagnostics(customers):
    """Pre-computed speed test and signal data for each customer."""
    diagnostics = {}

    for customer in customers:
        account_id = customer["account_id"]
        plans = [s["plan_id"] for s in customer["services"]]

        has_mobile = any(PLAN_TYPES[p] == "mobile" for p in plans)
        home_plan = next((p for p in plans if PLAN_TYPES[p] == "home_internet"), None)

        # Home internet diagnostics
        if home_plan == "internet_100":
            expected_down, expected_up = 100, 20
        elif home_plan == "fiber_1000":
            expected_down, expected_up = 1000, 1000
        else:
            expected_down = expected_up = 0

        if home_plan:
            # 80% of customers see normal speeds, 20% see degraded
            if random.random() < 0.8:
                wired_down = round(expected_down * random.uniform(0.9, 1.05), 1)
                wired_up = round(expected_up * random.uniform(0.9, 1.05), 1)
            else:
                wired_down = round(expected_down * random.uniform(0.3, 0.6), 1)
                wired_up = round(expected_up * random.uniform(0.3, 0.6), 1)
            wifi_down = round(wired_down * random.uniform(0.7, 0.95), 1)
            wifi_up = round(wired_up * random.uniform(0.7, 0.95), 1)
            home_diag = {
                "wired_download_mbps": wired_down,
                "wired_upload_mbps": wired_up,
                "wifi_download_mbps": wifi_down,
                "wifi_upload_mbps": wifi_up,
            }
        else:
            home_diag = None

        # Mobile diagnostics
        if has_mobile:
            # Signal strength: -65 is strong, -95 is very weak
            signal_dbm = random.choice([-65, -72, -78, -85, -92])
            data_gb = round(random.uniform(0.5, 8.0), 1)
            mobile_diag = {
                "signal_strength_dbm": signal_dbm,
                "data_used_gb_this_cycle": data_gb,
            }
        else:
            mobile_diag = None

        diagnostics[account_id] = {
            "last_test_date": str(REFERENCE_DATE - timedelta(days=random.randint(0, 7))),
            "home_internet": home_diag,
            "mobile": mobile_diag,
        }

    return diagnostics


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

def main():
    """Run all four generators and write JSON files."""
    print(f"Generating mock data into {OUTPUT_DIR}")

    customers = generate_customers()
    print(f"  Built {len(customers)} customers")

    bills = generate_billing(customers)
    print(f"  Built {len(bills)} bills")

    outages = generate_outages()
    print(f"  Built {len(outages)} outages")

    diagnostics = generate_diagnostics(customers)
    print(f"  Built {len(diagnostics)} diagnostic records")

    for name, data in [
        ("customers", customers),
        ("billing", bills),
        ("outages", outages),
        ("diagnostics", diagnostics),
    ]:
        path = OUTPUT_DIR / f"{name}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Wrote {path.name}")

    print("Done.")


if __name__ == "__main__":
    main()
