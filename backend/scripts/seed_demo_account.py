"""Seed the FLOWRA demo account.

Creates ONE admin user (`demo@flowralive.in` / `demo2026`) with access to
THREE companies (Generic Trading, Electronics & Hardware, Textiles &
Garments) so prospects can see how FLOWRA handles multi-company SMEs.

Each company is populated with a realistic, self-contained dataset:
  • a tailored inventory catalogue (~35 items)
  • 12-15 customers across 5 Chhattisgarh cities
  • 3-4 salesmen + customer mappings
  • ~70 sales vouchers across the last 10 months
  • Sales receipts (~75% collection ratio → realistic outstanding)
  • Goods + expense purchases
  • Dispatch cards in mixed statuses
  • Sync history marker

Usage:
    cd /app/backend && python3 scripts/seed_demo_account.py

Idempotent — wipes any prior data tagged with the demo tenant before
reseeding, so re-runs always produce the same shape with dates relative
to *now* (so dashboards keep looking active).
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
from services.id_mapping_service import register_company_mapping  # noqa: E402

# ── Demo identity ────────────────────────────────────────────────────────
DEMO_EMAIL = "demo@flowralive.in"
DEMO_PASS = "demo2026"
DEMO_NAME = "Demo Admin (Flowra Showcase)"
DEMO_TENANT = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "flowra.demo.tenant.v2"))

ALL_FEATURES = [
    "dashboard", "sales", "crm", "inventory", "analytics", "salesman",
    "ai_reports", "insider", "ca_corner", "dispatch", "sync_history", "setup",
]

# ── Source data ──────────────────────────────────────────────────────────
RNG = random.Random(20260218)  # deterministic re-runs

CITIES = ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg"]
STATE = "Chhattisgarh"

# ── Company catalogues ───────────────────────────────────────────────────
# Each entry: (name, unit, std_price, group, abc, opening_qty)
LUBRICANT_CATALOGUE = [
    ("ENGINE OIL 20W40 1LT",            "Nos", 215,   "Engine Oil",    "A",  220),
    ("ENGINE OIL 20W40 5LT",            "Nos", 1050,  "Engine Oil",    "A",  140),
    ("ENGINE OIL 20W40 20LT",           "Nos", 4150,  "Engine Oil",    "A",   55),
    ("ENGINE OIL 15W40 CF4 1LT",        "Nos", 240,   "Engine Oil",    "A",  180),
    ("ENGINE OIL 15W40 CF4 5LT",        "Nos", 1175,  "Engine Oil",    "A",   95),
    ("ENGINE OIL 15W40 CF4 20LT",       "Nos", 4650,  "Engine Oil",    "A",   42),
    ("ENGINE OIL 5W30 SYNTHETIC 1LT",   "Nos", 495,   "Engine Oil",    "B",   80),
    ("ENGINE OIL 5W30 SYNTHETIC 5LT",   "Nos", 2390,  "Engine Oil",    "B",   35),
    ("HYDRAULIC OIL 68 5LT",            "Nos", 980,   "Hydraulic Oil", "A",  130),
    ("HYDRAULIC OIL 68 20LT",           "Nos", 3850,  "Hydraulic Oil", "A",   72),
    ("HYDRAULIC OIL 68 210LT",          "Nos", 38500, "Hydraulic Oil", "A",   12),
    ("GEAR OIL EP90 5LT",               "Nos", 925,   "Gear Oil",      "B",   85),
    ("GEAR OIL EP140 5LT",              "Nos", 1010,  "Gear Oil",      "B",   75),
    ("BRAKE FLUID DOT4 500ML",          "Nos", 135,   "Brake Fluid",   "B",  260),
    ("COOLANT GREEN 5LT",               "Nos", 850,   "Coolant",       "B",   95),
    ("LITHIUM GREASE EP2 1KG",          "Nos", 310,   "Grease",        "B",  165),
    ("LITHIUM GREASE EP2 20KG",         "Nos", 5650,  "Grease",        "A",   42),
    ("OIL FILTER UNIVERSAL",            "Nos", 250,   "Filters",       "B",  320),
    ("AIR FILTER UNIVERSAL",            "Nos", 380,   "Filters",       "C",  220),
    ("BATTERY 12V 100AH",               "Nos", 8950,  "Batteries",     "A",   38),
    ("BATTERY 12V 150AH",               "Nos", 13800, "Batteries",     "A",   15),
    ("WIPER BLADE 22 INCH",             "Nos", 240,   "Accessories",   "C",  220),
    ("SPARK PLUG NGK (PACK 4)",         "Nos", 440,   "Plugs",         "C",  120),
    ("DIESEL ADDITIVE 500ML",           "Nos", 175,   "Additives",     "C",  220),
    ("CHAIN LUBE SPRAY 200ML",          "Nos", 285,   "Sprays",        "C",  220),
    ("DEGREASER SPRAY 500ML",           "Nos", 245,   "Sprays",        "C",  180),
    ("RADIATOR FLUSH 500ML",            "Nos", 295,   "Cleaners",      "C",  140),
    ("ENGINE OIL ADDITIVE 300ML",       "Nos", 220,   "Additives",     "C",  180),
    ("HD GREASE BLACK 5KG",             "Nos", 1340,  "Grease",        "C",   65),
    ("BELT V FAN STANDARD",             "Nos", 145,   "Belts",         "C",  220),
    ("CLUTCH PLATE BAJAJ",              "Nos", 480,   "Clutch",        "C",   95),
    ("WHEEL BEARING SET",               "Nos", 720,   "Bearings",      "C",  140),
    ("SHOCK ABSORBER FRONT",            "Nos", 1450,  "Suspension",    "C",   65),
    ("TYRE TUBE 6.00x16",               "Nos", 380,   "Tyres",         "B",  140),
    ("BRAKE LINING SET",                "Nos", 520,   "Brakes",        "C",   95),
]

ELECTRONICS_CATALOGUE = [
    ("LED BULB 9W B22",                 "Nos",   95,  "LED Lighting",   "A",  650),
    ("LED BULB 12W B22",                "Nos",  130,  "LED Lighting",   "A",  480),
    ("LED BULB 18W B22",                "Nos",  185,  "LED Lighting",   "A",  340),
    ("LED PANEL 18W SQUARE",            "Nos",  320,  "LED Lighting",   "B",  220),
    ("LED PANEL 24W ROUND",             "Nos",  420,  "LED Lighting",   "B",  165),
    ("LED STRIP 5M WARM",               "Nos",  650,  "LED Lighting",   "C",   95),
    ("CEILING FAN 1200MM IVORY",        "Nos", 2150,  "Fans",           "A",   85),
    ("CEILING FAN 1200MM BROWN",        "Nos", 2150,  "Fans",           "A",   72),
    ("TABLE FAN 400MM",                 "Nos", 1850,  "Fans",           "B",   55),
    ("WALL FAN 400MM",                  "Nos", 2250,  "Fans",           "B",   42),
    ("EXHAUST FAN 250MM",               "Nos", 1450,  "Fans",           "C",   85),
    ("MCB SP 6A C-CURVE",               "Nos",  155,  "Switchgear",     "A",  580),
    ("MCB SP 16A C-CURVE",              "Nos",  165,  "Switchgear",     "A",  420),
    ("MCB SP 32A C-CURVE",              "Nos",  195,  "Switchgear",     "B",  280),
    ("RCCB DP 25A 30MA",                "Nos",  890,  "Switchgear",     "A",   95),
    ("RCCB FP 40A 30MA",                "Nos", 1450,  "Switchgear",     "B",   55),
    ("DISTRIBUTION BOX 8WAY",           "Nos", 1850,  "DB Boxes",       "B",   65),
    ("DISTRIBUTION BOX 12WAY",          "Nos", 2650,  "DB Boxes",       "B",   42),
    ("MODULAR SWITCH 6A 1WAY",          "Nos",   45,  "Modular Plates", "A",  920),
    ("MODULAR SWITCH 16A 2WAY",         "Nos",   75,  "Modular Plates", "A",  680),
    ("MODULAR SOCKET 6A 3PIN",          "Nos",   85,  "Modular Plates", "A",  580),
    ("MODULAR PLATE 4M IVORY",          "Nos",  155,  "Modular Plates", "B",  280),
    ("MODULAR PLATE 8M IVORY",          "Nos",  295,  "Modular Plates", "B",  165),
    ("HOUSE WIRE 1.5SQMM 90M COIL",     "Nos", 1180,  "Wires & Cables", "A",   95),
    ("HOUSE WIRE 2.5SQMM 90M COIL",     "Nos", 1950,  "Wires & Cables", "A",   78),
    ("HOUSE WIRE 4SQMM 90M COIL",       "Nos", 3050,  "Wires & Cables", "A",   42),
    ("HOUSE WIRE 6SQMM 90M COIL",       "Nos", 4480,  "Wires & Cables", "B",   28),
    ("FLEX WIRE 0.5SQMM 100M",          "Nos",  550,  "Wires & Cables", "C",  120),
    ("HDMI CABLE 2M",                   "Nos",  185,  "AV Cables",      "C",  220),
    ("CCTV CABLE 90M",                  "Nos", 1850,  "AV Cables",      "C",   42),
    ("EXTENSION BOARD 4SKT 1.5M",       "Nos",  385,  "Extensions",     "B",  165),
    ("EXTENSION BOARD 6SKT 3M",         "Nos",  650,  "Extensions",     "B",   95),
    ("INVERTER 850VA",                  "Nos", 5850,  "Inverters",      "A",   35),
    ("INVERTER BATTERY 150AH",          "Nos", 12500, "Inverters",      "A",   22),
    ("DOORBELL CHIME WIRELESS",         "Nos",  395,  "Doorbell",       "C",  140),
]

TEXTILE_CATALOGUE = [
    ("MEN COTTON SHIRT FORMAL WHITE",    "Pcs",  650,  "Men Shirts",     "A",  480),
    ("MEN COTTON SHIRT FORMAL BLUE",     "Pcs",  650,  "Men Shirts",     "A",  420),
    ("MEN COTTON SHIRT CHECKS",          "Pcs",  720,  "Men Shirts",     "A",  385),
    ("MEN COTTON SHIRT PRINT",           "Pcs",  680,  "Men Shirts",     "B",  280),
    ("MEN TROUSER FORMAL BLACK",         "Pcs",  950,  "Men Trousers",   "A",  340),
    ("MEN TROUSER FORMAL GREY",          "Pcs",  950,  "Men Trousers",   "A",  280),
    ("MEN JEANS BLUE SLIM",              "Pcs", 1050,  "Men Denim",      "A",  220),
    ("MEN JEANS BLACK SLIM",             "Pcs", 1050,  "Men Denim",      "A",  185),
    ("MEN POLO TSHIRT NAVY",             "Pcs",  450,  "Men Tshirts",    "A",  680),
    ("MEN POLO TSHIRT BLACK",            "Pcs",  450,  "Men Tshirts",    "A",  580),
    ("MEN ROUND NECK TSHIRT",            "Pcs",  320,  "Men Tshirts",    "B",  720),
    ("MEN KURTA WHITE PLAIN",            "Pcs",  850,  "Men Ethnic",     "B",  140),
    ("MEN KURTA EMBROIDERED",            "Pcs", 1450,  "Men Ethnic",     "B",   85),
    ("LADIES SAREE COTTON PRINT",        "Pcs",  850,  "Ladies Sarees",  "A",  340),
    ("LADIES SAREE SILK BLEND",          "Pcs", 1850,  "Ladies Sarees",  "A",  220),
    ("LADIES SAREE GEORGETTE",           "Pcs", 1450,  "Ladies Sarees",  "A",  180),
    ("LADIES KURTI COTTON XL",           "Pcs",  650,  "Ladies Kurtis",  "A",  580),
    ("LADIES KURTI RAYON XL",            "Pcs",  720,  "Ladies Kurtis",  "A",  480),
    ("LADIES SALWAR SUIT UNSTITCHED",    "Set",  950,  "Ladies Suits",   "A",  280),
    ("LADIES LEGGINGS BLACK",            "Pcs",  295,  "Ladies Casual",  "B",  680),
    ("LADIES LEGGINGS COLOR PACK",       "Pcs",  295,  "Ladies Casual",  "B",  580),
    ("LADIES NIGHTY COTTON",             "Pcs",  450,  "Ladies Night",   "B",  340),
    ("KIDS TSHIRT 6-8YR",                "Pcs",  220,  "Kids Tops",      "B",  680),
    ("KIDS SHIRT 6-8YR",                 "Pcs",  295,  "Kids Tops",      "B",  480),
    ("KIDS JEANS 6-8YR",                 "Pcs",  395,  "Kids Bottoms",   "B",  380),
    ("KIDS FROCK COTTON 4-6YR",          "Pcs",  450,  "Kids Girls",     "B",  280),
    ("BED SHEET DOUBLE COTTON",          "Pcs",  650,  "Home Linen",     "A",  380),
    ("BED SHEET KING COTTON",            "Pcs",  850,  "Home Linen",     "A",  280),
    ("BED COVER COMFORTER DOUBLE",       "Pcs", 1850,  "Home Linen",     "B",  120),
    ("PILLOW COVER PAIR PRINT",          "Pair",  185,  "Home Linen",    "C",  680),
    ("TOWEL BATH COTTON LARGE",          "Pcs",  295,  "Home Linen",     "B",  580),
    ("HANDKERCHIEF PACK 6",              "Pack", 145,  "Accessories",    "C",  720),
    ("SOCKS PAIR FORMAL",                "Pair",  85,  "Accessories",    "C",  920),
    ("UNIFORM SHIRT WHITE SCHOOL",       "Pcs",  295,  "Uniforms",       "A",  680),
    ("UNIFORM TROUSER GREY SCHOOL",      "Pcs",  395,  "Uniforms",       "A",  580),
]

# ── Company definitions ─────────────────────────────────────────────────
COMPANIES = [
    {
        "name": "Sharma Lubricants & Distribution Pvt Ltd",
        "tag": "LUB",
        "industry": "Generic Trading / Lubricants",
        "catalogue": LUBRICANT_CATALOGUE,
        "voucher_prefix": "SLD",
        "customers": [
            "Sharma Auto Spares", "Patel Motor Works", "Gupta Trading Co",
            "Singh Auto Centre", "Krishna Lubricants", "Mahalaxmi Distributors",
            "Shree Ganesh Traders", "Vinayak Auto Parts", "Bharat Auto Stores",
            "Maa Durga Trading", "Hanuman Auto Center", "Tirupati Motor Works",
            "Jaiswal Automobiles", "Verma Trading Co", "Agrawal Auto Spares",
        ],
        "salesmen": ["Rajesh Kumar", "Amit Sharma", "Suresh Patel", "Vinod Singh"],
        "expense_ledgers": ["Transport Freight Inward", "Loading & Unloading",
                            "Diesel & Vehicle", "Office Stationery"],
    },
    {
        "name": "Bharat Electricals & Hardware Pvt Ltd",
        "tag": "ELC",
        "industry": "Electronics / Hardware",
        "catalogue": ELECTRONICS_CATALOGUE,
        "voucher_prefix": "BEH",
        "customers": [
            "Bharat Electricals Raipur", "Modern Lights Bilaspur",
            "Sunshine Electricals", "City Power Solutions",
            "Mahaveer Electricals", "Rajshree Hardware",
            "Surya Electric Stores", "Jyoti Lighting House",
            "Kapoor Electric Mart", "New Star Electricals",
            "Jain Electric Centre", "Goyal Lighting",
            "Singla Hardware Hub", "Khurana Trading",
            "Sai Baba Electricals",
        ],
        "salesmen": ["Manoj Agrawal", "Sunil Yadav", "Pradeep Mishra"],
        "expense_ledgers": ["Showroom Rent", "Salesman Travel",
                            "Marketing Hoardings", "Electricity & Maintenance"],
    },
    {
        "name": "Krishna Textiles & Garments LLP",
        "tag": "TXT",
        "industry": "Textile / Garments",
        "catalogue": TEXTILE_CATALOGUE,
        "voucher_prefix": "KTG",
        "customers": [
            "Rajshree Saree Bhandar", "Maa Sharda Cloth Centre",
            "Suvidha Garments", "Style Studio Bhilai",
            "Mahalaxmi Vastralay", "Aakash Garments",
            "Lifestyle Cloth House", "Trendy Wear Korba",
            "Tirupati Textiles", "Rajwadi Saree Centre",
            "Kids Mart Durg", "Apna Cloth Mart",
            "Shubh Vastra Bhandar", "Famous Textile Hub",
            "Sapna Saree Sansar", "Modern Garments Raipur",
        ],
        "salesmen": ["Dilip Sahu", "Mukesh Tiwari", "Naresh Jaiswal", "Anil Kashyap",
                     "Hemant Soni"],
        "expense_ledgers": ["Tailor Wages", "Shop Rent",
                            "Festival Discount Schemes", "Packaging Material"],
    },
]


# ── Helpers ──────────────────────────────────────────────────────────────
def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def days_ago(n: int) -> datetime:
    return now() - timedelta(days=n)


def random_recent_date(months_back: int = 10) -> datetime:
    """Pick a date in the last N months. Light recency bias so recent
    weeks have more vouchers (dashboards look active)."""
    days = months_back * 30
    # 60% of vouchers fall in the last 60% of the window
    if RNG.random() < 0.6:
        offset = RNG.randint(0, int(days * 0.6))
    else:
        offset = RNG.randint(int(days * 0.6), days)
    return now() - timedelta(days=offset)


# ── Wipe ─────────────────────────────────────────────────────────────────
async def wipe_existing():
    q = {"tenant_id": DEMO_TENANT}
    cols = [
        "users", "customers", "inventory_items", "sales_vouchers",
        "purchase_vouchers", "receipt_vouchers", "dispatch_cards",
        "salesman_master", "salesman_orders", "sync_history",
        "company_mappings", "all_ledgers", "tenant_settings",
        "salesman_beats", "beat_runs", "customer_targets",
    ]
    total = 0
    for col in cols:
        r = await db[col].delete_many(q)
        if r.deleted_count:
            total += r.deleted_count
            print(f"  · wiped {r.deleted_count:>5} rows from {col}")
    # Also drop the demo user (may not have tenant_id stamped if legacy)
    await db.users.delete_many({"username": {"$regex": r"^.+\.?demo@flowralive\.in$|^demo@flowralive\.in$"}})
    print(f"  ↳ total {total} demo rows removed")


# ── Seeders ──────────────────────────────────────────────────────────────
async def seed_companies():
    """Register the three companies in company_mappings → UUIDs."""
    out = []
    for c in COMPANIES:
        uid = await register_company_mapping(DEMO_TENANT, c["name"])
        c["company_id"] = uid
        out.append((c["name"], uid))
        print(f"  · {c['name']:<55} → {uid[:8]}…")
    return out


async def seed_user():
    company_ids = [c["company_id"] for c in COMPANIES]
    doc = {
        "username": DEMO_EMAIL,
        "name": DEMO_NAME,
        "role": "admin",
        "password_hash": hash_password(DEMO_PASS),
        "tenant_id": DEMO_TENANT,
        "companies": company_ids,
        "features": ALL_FEATURES,
        "plan": "enterprise",
        "active": True,
        "created_at": iso(days_ago(420)),
        "subscription_start": iso(days_ago(60)),
        "subscription_months": 24,           # 2-year window so demo never expires
        "billing_cycle": "annual",
        "must_change_password": False,
        "onboarding_completed": True,
        "max_employees": 20,
        "max_companies": 10,
    }
    await db.users.update_one({"username": DEMO_EMAIL}, {"$set": doc}, upsert=True)
    print(f"  · admin: {DEMO_EMAIL} / {DEMO_PASS}  (3 companies, 24-month subscription)")


async def seed_inventory(company):
    rows = []
    for idx, (name, unit, std, group, abc, opening) in enumerate(company["catalogue"], start=1):
        current_qty = max(opening + RNG.randint(-30, 35), 0)
        rows.append({
            "id": str(_uuid.uuid4()),
            "tenant_id": DEMO_TENANT,
            "company_id": company["company_id"],
            "item_id": f"{company['tag']}-ITM-{idx:03d}",
            "item_name": name,
            "part_number": f"{company['tag']}{idx:04d}",
            "quantity": current_qty,
            "unit": unit,
            "price": std,
            "purchase_price": round(std * RNG.uniform(0.72, 0.82), 2),
            "standard_price": std,
            "standard_price_source": "demo_seed",
            "abc_category": abc,
            "category": group,
            "stock_group": group,
            "root_stock_group": group,
            "aliases": [],
            "reorder_level": int(opening * 0.25),
            "opening_quantity": opening,
            "opening_rate": round(std * 0.78, 2),
            "opening_value": round(opening * std * 0.78, 2),
            "closing_value": round(current_qty * std * 0.78, 2),
            "last_updated": iso(now()),
        })
    await db.inventory_items.insert_many(rows)
    print(f"  · [{company['tag']}] {len(rows)} inventory items")
    return rows


async def seed_customers(company):
    rows = []
    for i, name in enumerate(company["customers"]):
        city = CITIES[i % len(CITIES)]
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": company["company_id"],
            "customer_name": f"{name},{city}",
            "contact_person": company["salesmen"][i % len(company["salesmen"])].split()[0],
            "phone": f"9{RNG.randint(700000000, 999999999)}",
            "state": STATE,
            "city": city,
            "ledger_group": "Sundry Debtors",
            "opening_balance": 0.0,
            "outstanding_amount": 0.0,
            "total_purchases": 0.0,
            "transaction_count": 0,
            "last_synced": iso(now()),
        })
    await db.customers.insert_many(rows)
    print(f"  · [{company['tag']}] {len(rows)} customers")
    return rows


async def seed_salesmen(company, customers):
    sm_rows = []
    user_rows = []
    pw = hash_password(DEMO_PASS)
    n_sm = len(company["salesmen"])
    chunk = max(len(customers) // n_sm, 1)
    for i, full_name in enumerate(company["salesmen"]):
        start = i * chunk
        end = (i + 1) * chunk if i < n_sm - 1 else len(customers)
        mapped = [c["customer_name"] for c in customers[start:end]]
        uname = f"{full_name.split()[0].lower()}.{company['tag'].lower()}.demo@flowralive.in"
        user_rows.append({
            "username": uname,
            "name": full_name,
            "role": "salesman",
            "password_hash": pw,
            "tenant_id": DEMO_TENANT,
            "companies": [company["company_id"]],
            "features": ["dashboard", "salesman"],
            "active": True,
            "created_at": iso(days_ago(400)),
            "mapped_customers": mapped,
            "monthly_target": RNG.randint(150000, 350000),
        })
        sm_rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": company["company_id"],
            "salesman_id": str(_uuid.uuid4()),
            "salesman_name": full_name,
            "username": uname,
            "phone": f"9{RNG.randint(800000000, 999999999)}",
            "active": True,
            "customers": mapped,
            "monthly_target": user_rows[-1]["monthly_target"],
            "quarterly_target": user_rows[-1]["monthly_target"] * 3,
            "created_at": iso(days_ago(400)),
        })
    for u in user_rows:
        await db.users.update_one({"username": u["username"]}, {"$set": u}, upsert=True)
    if sm_rows:
        await db.salesman_master.insert_many(sm_rows)
    print(f"  · [{company['tag']}] {len(sm_rows)} salesmen + login users")
    return sm_rows


async def seed_sales_vouchers(company, items, customers, salesmen, n=70):
    rows = []
    customer_stats = {}
    today = now()
    for seq in range(1, n + 1):
        vdate = random_recent_date(months_back=10)
        customer = RNG.choice(customers)
        salesman = RNG.choice(salesmen)["salesman_name"]
        n_lines = RNG.choices([1, 2, 3, 4, 5], weights=[3, 8, 9, 6, 3])[0]
        chosen = RNG.sample(items, n_lines)
        v_items = []
        subtotal = 0.0
        for it in chosen:
            qty = RNG.choices(
                [1, 2, 3, 4, 5, 6, 10, 12, 20],
                weights=[15, 14, 12, 10, 9, 8, 6, 4, 2],
            )[0]
            rate = round(it["price"] * RNG.choice([1.0, 1.0, 0.97, 1.02, 0.95]), 2)
            amt = round(qty * rate, 2)
            subtotal += amt
            v_items.append({
                "item": it["item_name"],
                "item_name": it["item_name"],
                "quantity": qty,
                "rate": rate,
                "amount": amt,
                "unit": it["unit"],
            })
        gst = round(subtotal * 0.18, 2)
        total = round(subtotal + gst, 2)
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": company["company_id"],
            "voucher_id": f"{company['voucher_prefix']}/{seq:04d}/2526",
            "voucher_type": "sales",
            "voucher_date": vdate.strftime("%Y-%m-%d"),
            "reference_number": f"{company['voucher_prefix']}-{seq:04d}",
            "party_name": customer["customer_name"],
            "salesman": salesman,
            "items": v_items,
            "ledger_entries": [
                {"ledger_name": customer["customer_name"], "amount": total,
                 "is_debit": True, "dr_or_cr": "Dr"},
                {"ledger_name": "CGST Tax", "amount": round(gst / 2, 2),
                 "is_debit": False, "dr_or_cr": "Cr"},
                {"ledger_name": "SGST Tax", "amount": round(gst / 2, 2),
                 "is_debit": False, "dr_or_cr": "Cr"},
            ],
            "destination": customer["city"],
            "dispatch_through": RNG.choice(["Lorry", "Tempo", "Self Pickup", "Courier"]),
            "total_amount": total,
            "last_updated": iso(today),
            "last_synced": iso(today),
        })
        stat = customer_stats.setdefault(customer["customer_name"],
                                          {"purchases": 0.0, "count": 0, "outstanding": 0.0})
        stat["purchases"] += total
        stat["count"] += 1
    await db.sales_vouchers.insert_many(rows)
    print(f"  · [{company['tag']}] {len(rows)} sales vouchers "
          f"(₹{sum(r['total_amount'] for r in rows):,.0f} revenue)")
    return rows, customer_stats


async def seed_receipt_vouchers(company, customer_stats):
    rows = []
    today = now()
    seq = 0
    for cname, stat in customer_stats.items():
        collection_pct = RNG.uniform(0.55, 0.85)
        collected = stat["purchases"] * collection_pct
        stat["outstanding"] = max(stat["purchases"] - collected, 0)
        n_receipts = RNG.choices([1, 2, 3], weights=[3, 5, 2])[0]
        per = collected / n_receipts
        for j in range(n_receipts):
            seq += 1
            rdate = today - timedelta(days=RNG.randint(5, 240))
            amt = round(per, 2)
            rows.append({
                "tenant_id": DEMO_TENANT,
                "company_id": company["company_id"],
                "voucher_id": f"{company['voucher_prefix']}-RC/{seq:04d}/2526",
                "voucher_type": "receipt",
                "voucher_date": rdate.strftime("%Y-%m-%d"),
                "reference_number": f"NEFT-{RNG.randint(100000, 999999)}",
                "party_name": cname,
                "amount": amt,
                "payment_mode": RNG.choice(["bank_transfer", "cheque", "upi", "cash"]),
                "narration": RNG.choice(["NEFT received", "Cheque received",
                                          "UPI received", "Cash received"]),
                "ledger_entries": [
                    {"ledger_name": cname, "amount": amt,
                     "is_debit": False, "dr_or_cr": "Cr"},
                    {"ledger_name": "HDFC Bank (A/c 1234)", "amount": amt,
                     "is_debit": True, "dr_or_cr": "Dr"},
                ],
                "bill_allocations": [],
                "last_synced": iso(today),
            })
    if rows:
        await db.receipt_vouchers.insert_many(rows)
    print(f"  · [{company['tag']}] {len(rows)} receipt vouchers")


async def seed_purchase_vouchers(company, items, n=20):
    """Mix of goods purchases (~70%) and expense purchases (~30%)."""
    rows = []
    today = now()
    suppliers = {
        "LUB": ["Hindustan Petroleum Corp", "Indian Oil B2B", "Castrol India",
                "Gulf Oil Lubricants", "Valvoline Cummins"],
        "ELC": ["Havells India Ltd", "Polycab Wires", "Anchor by Panasonic",
                "Crompton Greaves", "Bajaj Electricals"],
        "TXT": ["Reliance Textiles Surat", "Welspun India", "Trident Group",
                "Vardhman Mills", "Raymond Apparel"],
    }
    suppliers_list = suppliers[company["tag"]]
    for seq in range(1, n + 1):
        vdate = random_recent_date(months_back=10)
        is_expense = RNG.random() < 0.3
        supplier = (RNG.choice(company["expense_ledgers"]) if is_expense
                    else RNG.choice(suppliers_list))
        if is_expense:
            amt = round(RNG.uniform(2500, 35000), 2)
            v_items = []
            ledger_entries = [
                {"ledger_name": supplier, "amount": amt, "is_debit": True, "dr_or_cr": "Dr"},
                {"ledger_name": "Cash", "amount": amt, "is_debit": False, "dr_or_cr": "Cr"},
            ]
            vtype = "expense purchase"
        else:
            n_lines = RNG.randint(2, 5)
            chosen = RNG.sample(items, n_lines)
            v_items = []
            subtotal = 0.0
            for it in chosen:
                qty = RNG.choices([5, 10, 20, 30, 50, 100], weights=[3, 5, 6, 4, 3, 1])[0]
                rate = round(it["purchase_price"] or it["price"] * 0.78, 2)
                amount = round(qty * rate, 2)
                subtotal += amount
                v_items.append({
                    "item": it["item_name"],
                    "item_name": it["item_name"],
                    "quantity": qty,
                    "rate": rate,
                    "amount": amount,
                    "unit": it["unit"],
                })
            gst = round(subtotal * 0.18, 2)
            amt = round(subtotal + gst, 2)
            ledger_entries = [
                {"ledger_name": supplier, "amount": amt, "is_debit": False, "dr_or_cr": "Cr"},
                {"ledger_name": "CGST Input", "amount": round(gst / 2, 2), "is_debit": True, "dr_or_cr": "Dr"},
                {"ledger_name": "SGST Input", "amount": round(gst / 2, 2), "is_debit": True, "dr_or_cr": "Dr"},
            ]
            vtype = "goods purchase"
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": company["company_id"],
            "voucher_id": f"{company['voucher_prefix']}-PU/{seq:04d}/2526",
            "voucher_type": vtype,
            "voucher_date": vdate.strftime("%Y-%m-%d"),
            "reference_number": f"INV-{RNG.randint(10000, 99999)}",
            "party_name": supplier,
            "items": v_items,
            "ledger_entries": ledger_entries,
            "total_amount": amt,
            "last_synced": iso(today),
        })
    await db.purchase_vouchers.insert_many(rows)
    n_exp = sum(1 for r in rows if r["voucher_type"] == "expense purchase")
    print(f"  · [{company['tag']}] {len(rows)} purchase vouchers ({n_exp} expense, {len(rows)-n_exp} goods)")


async def seed_dispatch_cards(company, vouchers):
    """10 dispatch cards per company across realistic statuses."""
    chosen = RNG.sample(vouchers, min(10, len(vouchers)))
    statuses = ["new", "queued", "processing", "packed", "dispatched", "info_shared"]
    rows = []
    today = now()
    for i, v in enumerate(chosen):
        status = statuses[i % len(statuses)]
        created_at = today - timedelta(days=RNG.randint(0, 30))
        rows.append({
            "tenant_id": DEMO_TENANT,
            "company_id": company["company_id"],
            "card_id": f"DSP-{company['tag']}-{i+1:04d}",
            "card_type": "invoice",
            "invoice_number": v["reference_number"],
            "voucher_id": v["voucher_id"],
            "party_name": v["party_name"],
            "items": v["items"],
            "total_amount": v["total_amount"],
            "voucher_date": v["voucher_date"],
            "salesman": v["salesman"],
            "destination_city": v["destination"],
            "status": status,
            "assigned_to": None,
            "total_boxes": RNG.randint(1, 8),
            "transport_name": RNG.choice(["Bombay Goods Carrier", "VRL Logistics",
                                            "Maruti Carriers", "Local Tempo"]),
            "transport_charges": RNG.choice([0, 500, 800, 1200]),
            "porter_name": "",
            "porter_charges": 0,
            "lr_number": f"LR-{RNG.randint(10000, 99999)}",
            "physical_check": status in ("packed", "dispatched", "info_shared"),
            "notes": "",
            "documents": {},
            "status_history": [
                {"status": "new", "at": iso(created_at), "by": "system"},
                {"status": status, "at": iso(today - timedelta(hours=RNG.randint(1, 72))),
                 "by": "admin"},
            ],
            "created_at": iso(created_at),
            "created_by": "system",
            "last_updated_at": iso(today),
            "last_updated_by": "admin",
        })
    if rows:
        await db.dispatch_cards.insert_many(rows)
    print(f"  · [{company['tag']}] {len(rows)} dispatch cards")


async def update_customer_aggregates(company, customer_stats):
    for cname, stat in customer_stats.items():
        await db.customers.update_one(
            {"tenant_id": DEMO_TENANT, "company_id": company["company_id"],
             "customer_name": cname},
            {"$set": {
                "total_purchases": round(stat["purchases"], 2),
                "transaction_count": stat["count"],
                "outstanding_amount": round(stat["outstanding"], 2),
            }},
        )


async def seed_sync_marker(company, voucher_count, item_count, cust_count):
    await db.sync_history.insert_one({
        "tenant_id": DEMO_TENANT,
        "company_id": company["company_id"],
        "company_name": company["name"],
        "completed_at": iso(now()),
        "status": "success",
        "stats": {
            "inventory_items": item_count,
            "customers": cust_count,
            "sales_vouchers": voucher_count,
        },
        "agent_version": "v9.8.9-demo-seed",
        "duration_seconds": RNG.randint(28, 65),
    })


# ── Entry point ──────────────────────────────────────────────────────────
async def main():
    print(f"\n┌─ Seeding FLOWRA demo account ─────────────────────────")
    print(f"│  Tenant  : {DEMO_TENANT}")
    print(f"│  Login   : {DEMO_EMAIL} / {DEMO_PASS}")
    print(f"│  Companies: {len(COMPANIES)} (Lubricants / Electricals / Textiles)")
    print(f"└────────────────────────────────────────────────────────\n")

    print("[1/4] Wiping prior demo data …")
    await wipe_existing()

    print("\n[2/4] Registering companies …")
    await seed_companies()

    print("\n[3/4] Creating demo admin user …")
    await seed_user()

    print("\n[4/4] Populating each company …")
    grand_revenue = 0.0
    grand_vouchers = 0
    for company in COMPANIES:
        print(f"\n▸ {company['name']} ({company['industry']})")
        items = await seed_inventory(company)
        customers = await seed_customers(company)
        salesmen = await seed_salesmen(company, customers)
        vouchers, cust_stats = await seed_sales_vouchers(company, items, customers, salesmen, n=70)
        await seed_receipt_vouchers(company, cust_stats)
        await seed_purchase_vouchers(company, items, n=20)
        await seed_dispatch_cards(company, vouchers)
        await update_customer_aggregates(company, cust_stats)
        await seed_sync_marker(company, len(vouchers), len(items), len(customers))
        grand_revenue += sum(v["total_amount"] for v in vouchers)
        grand_vouchers += len(vouchers)

    print(f"\n┌─ ✓ Demo account ready ────────────────────────────────")
    print(f"│  Login    : {DEMO_EMAIL} / {DEMO_PASS}")
    print(f"│  Companies: {len(COMPANIES)}")
    print(f"│  Vouchers : {grand_vouchers}")
    print(f"│  Revenue  : ₹{grand_revenue:,.0f} across the last 10 months")
    print(f"└────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    asyncio.run(main())
