"""Seed a demo tenant + admin user with realistic dummy data.

Usage:
    cd /app/backend && python3 scripts/seed_demo_account.py

Idempotent — drops all existing data under the demo tenant before reseeding,
so it's safe to re-run before every prospect demo. The user credentials are
fixed (see DEMO_USER / DEMO_PASS below) so anyone can hand the prospect the
same login.

Data shape:
  • 1 tenant_id + 1 company_id (UUIDs derived deterministically from the email)
  • 60 inventory items (FMCG distribution catalogue — oils, lubes, filters, batteries)
  • 40 customers spread across 5 Chhattisgarh cities
  • 12 salesmen each mapped to 3-5 customers
  • 250 sales vouchers across the last 12 months (with month-on-month variance)
  • 30 dispatch cards (mix of statuses)
  • 25 payment receipts

The seeded MRR/ARR/customers etc. land in plausible mid-size SME ranges so
the dashboards look like a real ~₹4-6 Cr/year distribution business.
"""
import asyncio
import os
import random
import sys
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from db import db  # noqa: E402
from services.auth_service import hash_password  # noqa: E402

# ── Demo identity ────────────────────────────────────────────────────────
DEMO_EMAIL = "demo@flowralive.in"
DEMO_PASS = "demo2026"
DEMO_NAME = "Demo Admin (Sharma Lubricants)"
COMPANY_NAME = "Sharma Lubricants & Distribution Pvt Ltd"

# Deterministic UUIDs so re-runs target the same docs
DEMO_TENANT = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "flowra.demo.tenant.v1"))
DEMO_COMPANY = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "flowra.demo.company.v1"))

ALL_FEATURES = [
    "dashboard", "sales", "crm", "inventory", "analytics", "salesman",
    "ai_reports", "insider", "ca_corner", "dispatch", "sync_history", "setup",
]

# ── Source data ──────────────────────────────────────────────────────────
RNG = random.Random(20260510)  # deterministic; same demo data each run

CITIES = ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg"]
STATES = "Chhattisgarh"

ITEM_CATALOGUE = [
    # (name, unit, std_price, stock_group, abc, opening_qty)
    ("ENGINE OIL 20W40 1LT",            "Nos", 215,   "Engine Oil",    "A",  220),
    ("ENGINE OIL 20W40 5LT",            "Nos", 1050,  "Engine Oil",    "A",  140),
    ("ENGINE OIL 20W40 20LT",           "Nos", 4150,  "Engine Oil",    "A",   55),
    ("ENGINE OIL 15W40 CF4 1LT",        "Nos", 240,   "Engine Oil",    "A",  180),
    ("ENGINE OIL 15W40 CF4 5LT",        "Nos", 1175,  "Engine Oil",    "A",   95),
    ("ENGINE OIL 15W40 CF4 20LT",       "Nos", 4650,  "Engine Oil",    "A",   42),
    ("ENGINE OIL 10W30 1LT",            "Nos", 285,   "Engine Oil",    "B",  120),
    ("ENGINE OIL 10W30 5LT",            "Nos", 1395,  "Engine Oil",    "B",   60),
    ("ENGINE OIL 5W30 SYNTHETIC 1LT",   "Nos", 495,   "Engine Oil",    "B",   80),
    ("ENGINE OIL 5W30 SYNTHETIC 5LT",   "Nos", 2390,  "Engine Oil",    "B",   35),

    ("HYDRAULIC OIL 68 5LT",            "Nos", 980,   "Hydraulic Oil", "A",  130),
    ("HYDRAULIC OIL 68 20LT",           "Nos", 3850,  "Hydraulic Oil", "A",   72),
    ("HYDRAULIC OIL 68 210LT",          "Nos", 38500, "Hydraulic Oil", "A",   12),
    ("HYDRAULIC OIL 46 20LT",           "Nos", 3720,  "Hydraulic Oil", "B",   58),
    ("HYDRAULIC OIL 46 210LT",          "Nos", 37200, "Hydraulic Oil", "B",    8),

    ("GEAR OIL EP90 1LT",               "Nos", 195,   "Gear Oil",      "B",  140),
    ("GEAR OIL EP90 5LT",               "Nos", 925,   "Gear Oil",      "B",   85),
    ("GEAR OIL EP140 1LT",              "Nos", 210,   "Gear Oil",      "B",  110),
    ("GEAR OIL EP140 5LT",              "Nos", 1010,  "Gear Oil",      "B",   75),
    ("GEAR OIL 80W90 5LT",              "Nos", 1085,  "Gear Oil",      "B",   60),

    ("BRAKE FLUID DOT3 500ML",          "Nos",  95,   "Brake Fluid",   "C",  300),
    ("BRAKE FLUID DOT4 500ML",          "Nos", 135,   "Brake Fluid",   "B",  260),
    ("BRAKE FLUID DOT4 5LT",            "Nos", 1290,  "Brake Fluid",   "C",   28),

    ("COOLANT GREEN 1LT",               "Nos", 180,   "Coolant",       "B",  220),
    ("COOLANT GREEN 5LT",               "Nos", 850,   "Coolant",       "B",   95),
    ("COOLANT RED 5LT",                 "Nos", 920,   "Coolant",       "C",   55),

    ("LITHIUM GREASE EP2 500GM",        "Nos", 165,   "Grease",        "B",  240),
    ("LITHIUM GREASE EP2 1KG",          "Nos", 310,   "Grease",        "B",  165),
    ("LITHIUM GREASE EP2 5KG",          "Nos", 1450,  "Grease",        "B",   85),
    ("LITHIUM GREASE EP2 20KG",         "Nos", 5650,  "Grease",        "A",   42),
    ("HD GREASE BLACK 1KG",             "Nos", 285,   "Grease",        "C",  140),
    ("HD GREASE BLACK 5KG",             "Nos", 1340,  "Grease",        "C",   65),

    ("OIL FILTER UNIVERSAL",            "Nos", 250,   "Filters",       "B",  320),
    ("OIL FILTER TATA ACE",             "Nos", 320,   "Filters",       "B",  180),
    ("OIL FILTER MAHINDRA BOLERO",      "Nos", 295,   "Filters",       "B",  165),
    ("OIL FILTER ASHOK LEYLAND",        "Nos", 410,   "Filters",       "B",  135),
    ("AIR FILTER UNIVERSAL",            "Nos", 380,   "Filters",       "C",  220),
    ("FUEL FILTER UNIVERSAL",           "Nos", 295,   "Filters",       "C",  180),
    ("DIESEL FILTER TRACTOR",           "Nos", 340,   "Filters",       "C",  140),

    ("BATTERY 12V 75AH",                "Nos", 6850,  "Batteries",     "A",   45),
    ("BATTERY 12V 100AH",               "Nos", 8950,  "Batteries",     "A",   38),
    ("BATTERY 12V 130AH",               "Nos", 11500, "Batteries",     "A",   22),
    ("BATTERY 12V 150AH",               "Nos", 13800, "Batteries",     "B",   15),

    ("BELT V FAN STANDARD",             "Nos", 145,   "Belts",         "C",  220),
    ("TIMING BELT TATA",                "Nos", 850,   "Belts",         "C",   72),

    ("WIPER BLADE 18 INCH",             "Nos", 195,   "Accessories",   "C",  280),
    ("WIPER BLADE 22 INCH",             "Nos", 240,   "Accessories",   "C",  220),
    ("WIPER BLADE 24 INCH",             "Nos", 285,   "Accessories",   "C",  165),

    ("SPARK PLUG NGK",                  "Nos", 110,   "Plugs",         "C",  420),
    ("SPARK PLUG BOSCH",                "Nos", 135,   "Plugs",         "C",  340),
    ("GLOW PLUG DIESEL",                "Nos", 295,   "Plugs",         "C",  140),

    ("CLUTCH PLATE BAJAJ",              "Nos", 480,   "Clutch",        "C",   95),
    ("CLUTCH CABLE TATA",               "Nos", 165,   "Clutch",        "C",  140),

    ("RADIATOR COOLANT CAP",            "Nos",  85,   "Accessories",   "C",  340),
    ("ENGINE OIL ADDITIVE 300ML",       "Nos", 220,   "Additives",     "C",  180),
    ("DIESEL ADDITIVE 500ML",           "Nos", 175,   "Additives",     "C",  220),
    ("INJECTOR CLEANER 250ML",          "Nos", 195,   "Additives",     "C",  140),

    ("CHAIN LUBE SPRAY 200ML",          "Nos", 285,   "Sprays",        "C",  220),
    ("DEGREASER SPRAY 500ML",           "Nos", 245,   "Sprays",        "C",  180),
    ("RUBBER POLISH 500ML",             "Nos", 155,   "Cleaners",      "C",  220),
    ("ENGINE FLUSH 500ML",              "Nos", 295,   "Cleaners",      "C",  140),
]

CUSTOMER_NAMES = [
    "Sharma Auto Spares", "Patel Motor Works", "Gupta Trading Co",
    "Singh Auto Centre", "Krishna Lubricants", "Mahalaxmi Distributors",
    "Shree Ganesh Traders", "Vinayak Auto Parts", "Bharat Auto Stores",
    "Maa Durga Trading", "Hanuman Auto Center", "Tirupati Motor Works",
    "Sai Ram Spare Parts", "Jaiswal Automobiles", "Verma Trading Co",
    "Agrawal Auto Spares", "Rajput Motors", "Choudhary Auto Center",
    "Mishra Lubricants", "Yadav Auto Parts", "Pandey Trading",
    "Kumar Spare Centre", "Tiwari Automotive", "Sahu Auto Stores",
    "Dewangan Distributors", "Sinha Auto Hub", "Kashyap Trading",
    "Banjare Motors", "Sahu Brothers Auto", "Verma Auto Mart",
    "Rajak Trading Co", "Sahu Lubricants Hub", "Goyal Auto Spares",
    "Mittal Distributors", "Bansal Trading", "Jindal Auto Parts",
    "Nayak Motors", "Naik Trading Co", "Soni Auto Center",
    "Khandelwal Distributors",
]

SALESMAN_NAMES = [
    "Rajesh Kumar", "Amit Sharma", "Suresh Patel", "Vinod Singh",
    "Rakesh Verma", "Manoj Agrawal", "Sunil Yadav", "Pradeep Mishra",
    "Dilip Sahu", "Mukesh Tiwari", "Naresh Jaiswal", "Anil Kashyap",
]


# ── Helpers ──────────────────────────────────────────────────────────────
def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def days_ago(n: int) -> datetime:
    return now() - timedelta(days=n)


def random_voucher_date(today: datetime, months_back: int = 12) -> datetime:
    """Pick a date in the last N months with mild quarter-end seasonality."""
    # Bias toward end-of-quarter months (Mar, Jun, Sep, Dec) by 1.3×
    day_offset = RNG.randint(1, months_back * 30)
    d = today - timedelta(days=day_offset)
    return d


def voucher_no(seq: int) -> str:
    return f"DEMO-{seq:05d}"


# ── Seed steps ───────────────────────────────────────────────────────────
async def wipe_existing():
    q = {"tenant_id": DEMO_TENANT}
    cols = [
        "users", "customers", "inventory_items", "sales_vouchers",
        "dispatch_cards", "payment_receipts", "salesman_master",
        "salesman_orders", "sync_history",
    ]
    for col in cols:
        r = await db[col].delete_many(q)
        if r.deleted_count:
            print(f"  · wiped {r.deleted_count:>5} rows from {col}")


async def seed_user():
    pw = hash_password(DEMO_PASS)
    doc = {
        "username": DEMO_EMAIL,
        "name": DEMO_NAME,
        "role": "admin",
        "password_hash": pw,
        "tenant_id": DEMO_TENANT,
        "companies": [DEMO_COMPANY],
        "features": ALL_FEATURES,
        "plan": "enterprise",
        "active": True,
        "created_at": iso(days_ago(420)),
        "subscription_start": iso(days_ago(420)),
        "subscription_months": 18,  # demo account stays valid 1.5 years
        "billing_cycle": "annual",
        "must_change_password": False,
        "onboarding_completed": True,
        "max_employees": 20,
    }
    await db.users.update_one({"username": DEMO_EMAIL}, {"$set": doc}, upsert=True)
    print(f"  · admin user: {DEMO_EMAIL} / {DEMO_PASS}")
    return doc


async def seed_inventory():
    items = []
    for idx, (name, unit, std, group, abc, opening) in enumerate(ITEM_CATALOGUE, start=1):
        items.append({
            "item_id": f"DEMO-ITM-{idx:03d}",
            "tenant_id": DEMO_TENANT,
            "company_id": DEMO_COMPANY,
            "item_name": name,
            "part_number": f"PN{idx:04d}",
            "quantity": opening + RNG.randint(-15, 25),  # current stock varies
            "unit": unit,
            "price": std,
            "purchase_price": round(std * 0.78, 2),
            "standard_price": std,
            "standard_price_source": "demo_seed",
            "abc_category": abc,
            "category": group,
            "stock_group": group,
            "root_stock_group": group,
            "aliases": [],
            "reorder_level": int(opening * 0.25),
            "opening_quantity": opening,
            "opening_rate": std,
            "opening_value": opening * std,
            "closing_value": (opening + RNG.randint(-15, 25)) * std,
            "last_updated": iso(now()),
        })
    await db.inventory_items.insert_many(items)
    print(f"  · {len(items)} inventory items")
    return items


async def seed_customers():
    rows = []
    for i, name in enumerate(CUSTOMER_NAMES):
        city = CITIES[i % len(CITIES)]
        ph = f"9{RNG.randint(700000000, 999999999)}"
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": DEMO_COMPANY,
            "customer_name": f"{name}, {city}",
            "contact_person": SALESMAN_NAMES[i % len(SALESMAN_NAMES)].split()[0],
            "phone": ph,
            "state": STATES,
            "ledger_group": "Sundry Debtors",
            "opening_balance": 0.0,
            "outstanding_amount": 0.0,    # recalculated after vouchers
            "total_purchases": 0.0,        # recalculated after vouchers
            "transaction_count": 0,        # recalculated after vouchers
            "last_synced": iso(now()),
        })
    await db.customers.insert_many(rows)
    print(f"  · {len(rows)} customers")
    return rows


async def seed_salesmen(customers):
    """Create salesman users + salesman_master mappings."""
    sm_rows = []
    user_rows = []
    pw = hash_password(DEMO_PASS)  # all demo salesmen use the same demo password
    for i, full_name in enumerate(SALESMAN_NAMES):
        uname = f"{full_name.split()[0].lower()}.demo@flowralive.in"
        target_share = len(customers) // len(SALESMAN_NAMES)
        mine = customers[i * target_share:(i + 1) * target_share]
        if i == len(SALESMAN_NAMES) - 1:
            mine = customers[i * target_share:]
        mapped = [c["customer_name"] for c in mine]
        # User row
        user_rows.append({
            "username": uname,
            "name": full_name,
            "role": "salesman",
            "password_hash": pw,
            "tenant_id": DEMO_TENANT,
            "companies": [DEMO_COMPANY],
            "features": ["dashboard", "salesman"],
            "active": True,
            "created_at": iso(days_ago(400)),
            "mapped_customers": mapped,
            "monthly_target": RNG.randint(150000, 350000),
        })
        # salesman_master entry — keyed off salesman name (string) in this codebase
        sm_rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": DEMO_COMPANY,
            "salesman_name": full_name,
            "username": uname,
            "phone": f"9{RNG.randint(800000000, 999999999)}",
            "active": True,
            "customers": mapped,
            "monthly_target": user_rows[-1]["monthly_target"],
        })
    if user_rows:
        for u in user_rows:
            await db.users.update_one({"username": u["username"]}, {"$set": u}, upsert=True)
    if sm_rows:
        await db.salesman_master.insert_many(sm_rows)
    print(f"  · {len(user_rows)} salesmen ({SALESMAN_NAMES[0]} … {SALESMAN_NAMES[-1]})")
    return sm_rows


async def seed_sales_vouchers(items, customers, salesmen):
    """250 vouchers across last 12 months. Each voucher has 1-5 line items."""
    today = now()
    n = 250
    rows = []
    customer_stats = {}
    for seq in range(1, n + 1):
        vdate = random_voucher_date(today)
        customer = RNG.choice(customers)
        salesman = RNG.choice(salesmen)["salesman_name"]
        n_lines = RNG.choices([1, 2, 3, 4, 5], weights=[5, 8, 7, 4, 2])[0]
        chosen = RNG.sample(items, n_lines)
        v_items = []
        total = 0.0
        for it in chosen:
            qty = RNG.choices(
                [1, 2, 3, 4, 5, 10, 20, 50],
                weights=[15, 12, 10, 8, 7, 5, 3, 1],
            )[0]
            rate = it["price"] * RNG.choice([1.0, 1.0, 1.0, 0.97, 1.02])
            amt = round(qty * rate, 2)
            total += amt
            v_items.append({
                "item": it["item_name"],
                "item_name": it["item_name"],
                "quantity": qty,
                "rate": round(rate, 2),
                "amount": amt,
                "unit": it["unit"],
            })
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": DEMO_COMPANY,
            "voucher_id": f"v_{seq}_{DEMO_COMPANY[:8]}",
            "voucher_type": "Sales",
            "voucher_date": vdate.strftime("%Y-%m-%d"),
            "reference_number": voucher_no(seq),
            "party_name": customer["customer_name"],
            "salesman": salesman,
            "items": v_items,
            "ledger_entries": [],
            "destination": customer["customer_name"].split(",")[-1].strip(),
            "dispatch_through": RNG.choice(["Lorry", "Tempo", "Self Pickup", "Courier"]),
            "total_amount": round(total, 2),
            "last_updated": iso(today),
        })
        stat = customer_stats.setdefault(customer["customer_name"],
                                          {"purchases": 0.0, "count": 0, "outstanding": 0.0})
        stat["purchases"] += total
        stat["count"] += 1
    if rows:
        await db.sales_vouchers.insert_many(rows)
    print(f"  · {len(rows)} sales vouchers")
    return rows, customer_stats


async def seed_payment_receipts(customer_stats):
    """About 70% of each customer's purchase amount is collected, leaving an
    outstanding so the dashboard shows a realistic overdue mix."""
    rows = []
    today = now()
    for cname, stat in customer_stats.items():
        collected = stat["purchases"] * RNG.uniform(0.55, 0.85)
        stat["outstanding"] = max(stat["purchases"] - collected, 0)
        # 1-3 receipts per customer
        n_receipts = RNG.choices([1, 2, 3], weights=[3, 5, 2])[0]
        for j in range(n_receipts):
            amt = round(collected / n_receipts, 2)
            rdate = today - timedelta(days=RNG.randint(5, 250))
            rows.append({
                "tenant_id": DEMO_TENANT,
                "company_id": DEMO_COMPANY,
                "receipt_id": f"r_{cname[:10]}_{j}",
                "party_name": cname,
                "amount": amt,
                "voucher_date": rdate.strftime("%Y-%m-%d"),
                "voucher_type": "Receipt",
                "payment_mode": RNG.choice(["bank_transfer", "cheque", "upi", "cash"]),
                "reference_number": f"RCT-{RNG.randint(10000, 99999)}",
                "last_updated": iso(today),
            })
    if rows:
        # Receipts live in `sales_vouchers` collection too with voucher_type=Receipt
        # in this codebase; mirror to a dedicated collection if it exists.
        await db.payment_receipts.insert_many(rows)
    print(f"  · {len(rows)} payment receipts")


async def update_customer_aggregates(customer_stats):
    """Write back computed totals to the customers collection."""
    for cname, stat in customer_stats.items():
        await db.customers.update_one(
            {"tenant_id": DEMO_TENANT, "company_id": DEMO_COMPANY, "customer_name": cname},
            {"$set": {
                "total_purchases": round(stat["purchases"], 2),
                "transaction_count": stat["count"],
                "outstanding_amount": round(stat["outstanding"], 2),
            }},
        )
    print(f"  · updated aggregates for {len(customer_stats)} customers")


async def seed_dispatch_cards(vouchers):
    """30 dispatch cards across a spread of statuses to give the Dispatch
    Terminal something to show."""
    rows = []
    today = now()
    chosen = RNG.sample(vouchers, min(30, len(vouchers)))
    statuses = (["new"] * 8 + ["picking"] * 6 + ["packed"] * 5 +
                ["in_transit"] * 7 + ["delivered"] * 4)
    RNG.shuffle(statuses)
    for i, v in enumerate(chosen):
        status = statuses[i] if i < len(statuses) else "new"
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": DEMO_COMPANY,
            "card_id": f"d_{i}_{DEMO_COMPANY[:8]}",
            "voucher_id": v["voucher_id"],
            "reference_number": v["reference_number"],
            "party_name": v["party_name"],
            "status": status,
            "destination": v["destination"],
            "dispatch_through": v["dispatch_through"],
            "total_amount": v["total_amount"],
            "items": v["items"],
            "invoice_changed": False,
            "created_at": iso(today - timedelta(days=RNG.randint(0, 14))),
            "updated_at": iso(today - timedelta(hours=RNG.randint(0, 60))),
        })
    if rows:
        await db.dispatch_cards.insert_many(rows)
    print(f"  · {len(rows)} dispatch cards across {len(set(r['status'] for r in rows))} statuses")


async def write_sync_marker():
    await db.sync_history.insert_one({
        "tenant_id": DEMO_TENANT,
        "company_id": DEMO_COMPANY,
        "completed_at": iso(now()),
        "status": "success",
        "stats": {
            "inventory_items": len(ITEM_CATALOGUE),
            "customers": len(CUSTOMER_NAMES),
            "sales_vouchers": 250,
        },
        "agent_version": "v9.8.9-demo-seed",
        "duration_seconds": 42,
    })
    print("  · sync_history marker added")


# ── Entry point ──────────────────────────────────────────────────────────
async def main():
    print(f"\n┌─ Seeding FLOWRA demo account ─────────────────────────")
    print(f"│  Tenant : {DEMO_TENANT}")
    print(f"│  Company: {DEMO_COMPANY}  ({COMPANY_NAME})")
    print(f"│  Login  : {DEMO_EMAIL} / {DEMO_PASS}")
    print(f"└────────────────────────────────────────────────────────\n")

    print("Wiping prior demo data …")
    await wipe_existing()

    print("\nSeeding fresh data …")
    await seed_user()
    items = await seed_inventory()
    customers = await seed_customers()
    salesmen = await seed_salesmen(customers)
    vouchers, cust_stats = await seed_sales_vouchers(items, customers, salesmen)
    await seed_payment_receipts(cust_stats)
    await update_customer_aggregates(cust_stats)
    await seed_dispatch_cards(vouchers)
    await write_sync_marker()

    total_rev = sum(v["total_amount"] for v in vouchers)
    print(f"\n✓ Demo account ready.")
    print(f"  Total seeded revenue: Rs.{total_rev:,.0f}")
    print(f"  Login at: <BACKEND>/login  ·  {DEMO_EMAIL} / {DEMO_PASS}")


if __name__ == "__main__":
    asyncio.run(main())
