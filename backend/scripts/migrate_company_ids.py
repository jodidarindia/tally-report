"""
Migration: Backfill company_id on existing data and register companies on admin.
Also creates a small second company dataset for multi-company switcher testing.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"
TENANT = "tenant_admin"
PRIMARY_COMPANY = "ASA AUTOTECH INDIA PRIVATE LIMITED"
DEMO_COMPANY = "Demo Trading Co"


async def migrate():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # 1. Backfill company_id on existing data
    for coll_name in ["inventory_items", "sales_vouchers", "customers"]:
        coll = db[coll_name]
        result = await coll.update_many(
            {"tenant_id": TENANT, "$or": [{"company_id": ""}, {"company_id": None}, {"company_id": {"$exists": False}}]},
            {"$set": {"company_id": PRIMARY_COMPANY}}
        )
        print(f"  [{coll_name}] Backfilled company_id on {result.modified_count} docs")

    # Also backfill sync_status, overdue_digest, and other support collections
    for coll_name in ["sync_status", "overdue_digest", "sync_history"]:
        coll = db[coll_name]
        result = await coll.update_many(
            {"tenant_id": TENANT, "$or": [{"company_id": ""}, {"company_id": None}, {"company_id": {"$exists": False}}]},
            {"$set": {"company_id": PRIMARY_COMPANY}}
        )
        print(f"  [{coll_name}] Backfilled company_id on {result.modified_count} docs")

    # 2. Register primary company on admin user
    res = await db.users.update_one(
        {"username": "admin", "role": "admin"},
        {"$addToSet": {"companies": PRIMARY_COMPANY}}
    )
    print(f"  [admin user] Registered '{PRIMARY_COMPANY}': modified={res.modified_count}")

    # 3. Create a small demo second company dataset for testing the switcher
    # Check if demo company data already exists
    existing = await db.inventory_items.count_documents({"tenant_id": TENANT, "company_id": DEMO_COMPANY})
    if existing > 0:
        print(f"  [Demo Company] Already has {existing} inventory items, skipping seed")
    else:
        # Seed small demo inventory
        demo_inventory = [
            {"name": "Demo Widget A", "stock_group": "Finished Goods", "category": "Primary", "quantity": 100, "rate": 250.0, "value": 25000.0, "unit": "Nos", "tenant_id": TENANT, "company_id": DEMO_COMPANY, "last_updated": "2026-04-10T00:00:00"},
            {"name": "Demo Widget B", "stock_group": "Raw Materials", "category": "Primary", "quantity": 50, "rate": 500.0, "value": 25000.0, "unit": "Kgs", "tenant_id": TENANT, "company_id": DEMO_COMPANY, "last_updated": "2026-04-10T00:00:00"},
            {"name": "Demo Widget C", "stock_group": "Finished Goods", "category": "Primary", "quantity": 200, "rate": 150.0, "value": 30000.0, "unit": "Nos", "tenant_id": TENANT, "company_id": DEMO_COMPANY, "last_updated": "2026-04-10T00:00:00"},
        ]
        await db.inventory_items.insert_many(demo_inventory)
        print(f"  [Demo Company] Seeded {len(demo_inventory)} inventory items")

        # Seed small demo sales
        demo_sales = [
            {"voucher_id": "DEMO-001", "date": "2026-04-01", "party_name": "Demo Customer 1", "amount": 15000.0, "voucher_type": "Sales", "financial_year": "2025-26", "tenant_id": TENANT, "company_id": DEMO_COMPANY, "last_updated": "2026-04-10T00:00:00"},
            {"voucher_id": "DEMO-002", "date": "2026-04-02", "party_name": "Demo Customer 2", "amount": 25000.0, "voucher_type": "Sales", "financial_year": "2025-26", "tenant_id": TENANT, "company_id": DEMO_COMPANY, "last_updated": "2026-04-10T00:00:00"},
        ]
        await db.sales_vouchers.insert_many(demo_sales)
        print(f"  [Demo Company] Seeded {len(demo_sales)} sales vouchers")

        # Seed demo customers
        demo_customers = [
            {"name": "Demo Customer 1", "closing_balance": 15000.0, "credit_period": 30, "tenant_id": TENANT, "company_id": DEMO_COMPANY},
            {"name": "Demo Customer 2", "closing_balance": 25000.0, "credit_period": 45, "tenant_id": TENANT, "company_id": DEMO_COMPANY},
        ]
        await db.customers.insert_many(demo_customers)
        print(f"  [Demo Company] Seeded {len(demo_customers)} customers")

    # Register demo company on admin
    res = await db.users.update_one(
        {"username": "admin", "role": "admin"},
        {"$addToSet": {"companies": DEMO_COMPANY}}
    )
    print(f"  [admin user] Registered '{DEMO_COMPANY}': modified={res.modified_count}")

    # Verify final state
    user = await db.users.find_one({"username": "admin"}, {"_id": 0, "companies": 1})
    print(f"\n  Final admin companies: {user.get('companies', [])}")

    inv_primary = await db.inventory_items.count_documents({"tenant_id": TENANT, "company_id": PRIMARY_COMPANY})
    inv_demo = await db.inventory_items.count_documents({"tenant_id": TENANT, "company_id": DEMO_COMPANY})
    print(f"  Inventory: {PRIMARY_COMPANY} = {inv_primary}, {DEMO_COMPANY} = {inv_demo}")

    sales_primary = await db.sales_vouchers.count_documents({"tenant_id": TENANT, "company_id": PRIMARY_COMPANY})
    sales_demo = await db.sales_vouchers.count_documents({"tenant_id": TENANT, "company_id": DEMO_COMPANY})
    print(f"  Sales: {PRIMARY_COMPANY} = {sales_primary}, {DEMO_COMPANY} = {sales_demo}")

    client.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
