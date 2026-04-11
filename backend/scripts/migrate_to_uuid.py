"""
Migration script: Convert plain-text tenant_id and company_id to UUID format.
Run once after deployment. Idempotent — safe to run multiple times.
"""
import asyncio
import uuid
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_COLLECTIONS = [
    "inventory_items", "sales_vouchers", "customers", "receipt_vouchers",
    "credit_notes", "journal_vouchers", "stock_journals", "purchase_vouchers",
    "debit_notes", "sundry_creditors", "sync_status", "sync_history",
    "customer_followups", "customer_targets", "audit_logs", "overdue_digest",
    "ai_queries", "tally_connections", "renewal_requests", "salesman_master",
    "purchase_orders"
]


async def run_migration():
    from dotenv import load_dotenv
    load_dotenv()

    from motor.motor_asyncio import AsyncIOMotorClient
    from services.encryption_service import encrypt_field

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "flowra")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    logger.info("=" * 60)
    logger.info("FLOWRA Migration: Plain-text IDs -> UUID format")
    logger.info("=" * 60)

    # Check if migration already done
    migration_marker = await db.migration_log.find_one({"migration": "uuid_ids_v1"})
    if migration_marker:
        logger.info("Migration already completed. Skipping.")
        return

    # Step 1: Collect all unique tenant_ids from users
    logger.info("\n--- Step 1: Migrate Tenant IDs ---")
    tenant_map = {}  # old_tenant_id -> new_uuid

    users = await db.users.find({}, {"_id": 0, "tenant_id": 1, "username": 1, "role": 1}).to_list(1000)
    old_tenant_ids = set()
    for u in users:
        tid = u.get("tenant_id", "")
        if tid:
            old_tenant_ids.add(tid)

    for old_tid in old_tenant_ids:
        # Check if it's already a UUID format (idempotent)
        try:
            uuid.UUID(old_tid)
            logger.info(f"  {old_tid} — already UUID, skipping")
            tenant_map[old_tid] = old_tid
            continue
        except ValueError:
            pass

        new_uuid = str(uuid.uuid4())
        tenant_map[old_tid] = new_uuid
        logger.info(f"  {old_tid} -> {new_uuid}")

    logger.info(f"  Total tenants to migrate: {len([k for k, v in tenant_map.items() if k != v])}")

    # Step 2: Collect all unique company names per tenant
    logger.info("\n--- Step 2: Migrate Company IDs ---")
    company_map = {}  # (old_tenant_id, old_company_name) -> new_uuid

    for old_tid in old_tenant_ids:
        admin = await db.users.find_one({"tenant_id": old_tid, "role": "admin"}, {"_id": 0, "companies": 1})
        if not admin:
            continue
        companies = admin.get("companies", [])
        for comp_name in companies:
            if not comp_name:
                continue
            try:
                uuid.UUID(comp_name)
                company_map[(old_tid, comp_name)] = comp_name
                logger.info(f"  [{old_tid}] {comp_name} — already UUID, skipping")
                continue
            except ValueError:
                pass
            new_comp_uuid = str(uuid.uuid4())
            company_map[(old_tid, comp_name)] = new_comp_uuid
            logger.info(f"  [{old_tid}] {comp_name} -> {new_comp_uuid}")

            # Create company_mappings entry
            new_tenant_uuid = tenant_map.get(old_tid, old_tid)
            await db.company_mappings.update_one(
                {"tenant_id": new_tenant_uuid, "company_uuid": new_comp_uuid},
                {"$set": {
                    "tenant_id": new_tenant_uuid,
                    "company_uuid": new_comp_uuid,
                    "company_name_encrypted": encrypt_field(comp_name),
                }},
                upsert=True
            )

    # Also scan data collections for company_ids not in users.companies
    for coll_name in DATA_COLLECTIONS:
        try:
            pipeline = [
                {"$match": {"company_id": {"$exists": True, "$ne": ""}}},
                {"$group": {"_id": {"tenant_id": "$tenant_id", "company_id": "$company_id"}}}
            ]
            results = await db[coll_name].aggregate(pipeline).to_list(1000)
            for r in results:
                old_tid = r["_id"].get("tenant_id", "")
                old_cid = r["_id"].get("company_id", "")
                if not old_tid or not old_cid:
                    continue
                key = (old_tid, old_cid)
                if key not in company_map:
                    try:
                        uuid.UUID(old_cid)
                        company_map[key] = old_cid
                        continue
                    except ValueError:
                        pass
                    new_comp_uuid = str(uuid.uuid4())
                    company_map[key] = new_comp_uuid
                    new_tenant_uuid = tenant_map.get(old_tid, old_tid)
                    await db.company_mappings.update_one(
                        {"tenant_id": new_tenant_uuid, "company_uuid": new_comp_uuid},
                        {"$set": {
                            "tenant_id": new_tenant_uuid,
                            "company_uuid": new_comp_uuid,
                            "company_name_encrypted": encrypt_field(old_cid),
                        }},
                        upsert=True
                    )
                    logger.info(f"  [data:{coll_name}] [{old_tid}] {old_cid} -> {new_comp_uuid}")
        except Exception as e:
            logger.warning(f"  Scanning {coll_name} for companies failed: {e}")

    # Step 3: Update users collection
    logger.info("\n--- Step 3: Update users collection ---")
    for old_tid, new_tid in tenant_map.items():
        if old_tid == new_tid:
            continue
        # Update tenant_id
        result = await db.users.update_many(
            {"tenant_id": old_tid},
            {"$set": {"tenant_id": new_tid, "_old_tenant_id": old_tid}}
        )
        logger.info(f"  users: {old_tid} -> {new_tid} ({result.modified_count} docs)")

        # Update companies array (replace names with UUIDs)
        admin = await db.users.find_one({"tenant_id": new_tid, "role": "admin"}, {"_id": 0, "companies": 1})
        if admin:
            old_companies = admin.get("companies", [])
            new_companies = []
            for comp_name in old_companies:
                key = (old_tid, comp_name)
                new_companies.append(company_map.get(key, comp_name))
            await db.users.update_one(
                {"tenant_id": new_tid, "role": "admin"},
                {"$set": {"companies": new_companies}}
            )
            logger.info(f"  Companies updated: {old_companies} -> {new_companies}")

    # Step 4: Update all data collections
    logger.info("\n--- Step 4: Update data collections ---")
    for coll_name in DATA_COLLECTIONS:
        total_updated = 0
        for old_tid, new_tid in tenant_map.items():
            if old_tid == new_tid:
                continue
            result = await db[coll_name].update_many(
                {"tenant_id": old_tid},
                {"$set": {"tenant_id": new_tid}}
            )
            total_updated += result.modified_count

        for (old_tid, old_cid), new_cid in company_map.items():
            if old_cid == new_cid:
                continue
            new_tid = tenant_map.get(old_tid, old_tid)
            result = await db[coll_name].update_many(
                {"tenant_id": new_tid, "company_id": old_cid},
                {"$set": {"company_id": new_cid}}
            )
            total_updated += result.modified_count

        if total_updated > 0:
            logger.info(f"  {coll_name}: {total_updated} docs updated")

    # Step 5: Update deleted_users and archived_tenant_data
    logger.info("\n--- Step 5: Update archived collections ---")
    for old_tid, new_tid in tenant_map.items():
        if old_tid == new_tid:
            continue
        await db.deleted_users.update_many(
            {"original_tenant_id": old_tid},
            {"$set": {"original_tenant_id": new_tid}}
        )
        await db.archived_tenant_data.update_many(
            {"tenant_id": old_tid},
            {"$set": {"tenant_id": new_tid}}
        )

    # Step 6: Record migration
    from datetime import datetime, timezone
    await db.migration_log.insert_one({
        "migration": "uuid_ids_v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "tenant_mappings": {k: v for k, v in tenant_map.items() if k != v},
        "company_mappings_count": len([k for k, v in company_map.items() if k != v]),
    })

    logger.info("\n" + "=" * 60)
    logger.info("Migration complete!")
    logger.info(f"  Tenants migrated: {len([k for k, v in tenant_map.items() if k != v])}")
    logger.info(f"  Companies mapped: {len([k for k, v in company_map.items() if k != v])}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_migration())
