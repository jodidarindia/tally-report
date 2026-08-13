"""
ID Mapping service for tenant and company UUIDs.
Maps opaque UUIDs to encrypted actual names for security.
"""
import os
import uuid
import hmac
import hashlib
import logging
from db import db
from services.encryption_service import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)


def _stable_name_hash(name: str) -> str:
    """Deterministic HMAC-SHA256 hash of a company name — used as the lookup
    key for `company_mappings`. This fixes the duplicate-company bug:
    Fernet.encrypt is non-deterministic (random IV per call), so comparing
    two ciphertexts of the same plaintext never matches and every sync
    request would create a fresh UUID. A keyed hash gives us stable lookups
    while keeping the actual name encrypted at rest."""
    secret = os.environ.get("JWT_SECRET", "fallback_company_hash_key_change_me")
    return hmac.new(secret.encode("utf-8"), (name or "").strip().encode("utf-8"),
                    hashlib.sha256).hexdigest()


async def generate_tenant_id() -> str:
    """Generate a unique UUID-format tenant ID."""
    return str(uuid.uuid4())


async def generate_company_id() -> str:
    """Generate a unique UUID-format company ID."""
    return str(uuid.uuid4())


async def register_company_mapping(tenant_id: str, company_name: str) -> str:
    """Register a company name and return its UUID. If already mapped, return existing UUID.

    Lookup uses a deterministic HMAC hash so duplicate calls reliably resolve
    to the same UUID. The display name itself is still stored Fernet-encrypted.
    """
    name = (company_name or "").strip()
    if not name:
        return ""
    name_hash = _stable_name_hash(name)

    existing = await db.company_mappings.find_one(
        {"tenant_id": tenant_id, "company_name_hash": name_hash}, {"_id": 0}
    )
    if existing:
        return existing["company_uuid"]

    # Backfill: legacy rows have only `company_name_encrypted` (non-deterministic).
    # Walk them once, decrypting each to find a match before creating a new UUID.
    legacy_rows = await db.company_mappings.find(
        {"tenant_id": tenant_id, "company_name_hash": {"$exists": False}}, {"_id": 0}
    ).to_list(500)
    for row in legacy_rows:
        try:
            if decrypt_field(row.get("company_name_encrypted", "")).strip() == name:
                # Adopt the legacy UUID and stamp the hash so future lookups are O(1)
                await db.company_mappings.update_one(
                    {"company_uuid": row["company_uuid"], "tenant_id": tenant_id},
                    {"$set": {"company_name_hash": name_hash}},
                )
                return row["company_uuid"]
        except Exception:
            continue

    company_uuid = str(uuid.uuid4())
    await db.company_mappings.insert_one({
        "tenant_id": tenant_id,
        "company_uuid": company_uuid,
        "company_name_encrypted": encrypt_field(name),
        "company_name_hash": name_hash,
    })
    logger.info(f"Registered company mapping: {name} -> {company_uuid}")
    return company_uuid


async def register_company_by_folder(tenant_id: str, folder_id: str,
                                     display_name: str) -> str:
    """v1.5.4 — Busy Sync Agent variant of `register_company_mapping`.

    The Busy agent sends a **stable folder id** (e.g. `COMP0002`) as
    `company_id` — that never changes — plus the current human-readable
    company name (e.g. `NAVDURGA AUTO SPARES JABALPUR`) which the user
    might edit inside Busy over time.

    We key the mapping on the folder id so:
      - A rename in Busy just updates the display name in-place (no
        duplicate UUID, no orphan data).
      - The legacy row whose `company_name_hash` still equals the folder
        id (from v1.5.3 and earlier, when the agent sent the folder id
        as the name) gets adopted and re-labelled instead of leaving
        stale data.
    """
    folder_id = (folder_id or "").strip()
    display_name = (display_name or "").strip() or folder_id
    if not folder_id:
        return ""

    folder_hash = _stable_name_hash(f"__folder__:{folder_id}")
    # 1) Fast path — mapping already keyed on the folder id.
    existing = await db.company_mappings.find_one(
        {"tenant_id": tenant_id, "folder_id_hash": folder_hash}, {"_id": 0}
    )
    if existing:
        # Keep the display name fresh (Busy rename → FLOWRA rename).
        current_name = ""
        try:
            current_name = decrypt_field(existing.get("company_name_encrypted", "")).strip()
        except Exception:
            pass
        if display_name and display_name != current_name:
            await db.company_mappings.update_one(
                {"company_uuid": existing["company_uuid"], "tenant_id": tenant_id},
                {"$set": {
                    "company_name_encrypted": encrypt_field(display_name),
                    "company_name_hash": _stable_name_hash(display_name),
                }},
            )
            logger.info(
                f"Renamed company mapping {existing['company_uuid']}: "
                f"'{current_name}' → '{display_name}'"
            )
        return existing["company_uuid"]

    # 2) Legacy migration — mapping created by v1.5.3 with the folder id
    #    as the display name. Adopt it, stamp folder_id_hash, rename.
    legacy = await db.company_mappings.find_one(
        {"tenant_id": tenant_id, "company_name_hash": _stable_name_hash(folder_id)},
        {"_id": 0}
    )
    if legacy:
        await db.company_mappings.update_one(
            {"company_uuid": legacy["company_uuid"], "tenant_id": tenant_id},
            {"$set": {
                "folder_id_hash": folder_hash,
                "company_name_encrypted": encrypt_field(display_name),
                "company_name_hash": _stable_name_hash(display_name),
            }},
        )
        logger.info(
            f"Migrated legacy folder-name mapping {legacy['company_uuid']}: "
            f"folder='{folder_id}' → display='{display_name}'"
        )
        return legacy["company_uuid"]

    # 3) Also check if a mapping already exists under the display name
    #    hash (user might have registered manually first). Adopt it.
    name_hash = _stable_name_hash(display_name)
    by_name = await db.company_mappings.find_one(
        {"tenant_id": tenant_id, "company_name_hash": name_hash}, {"_id": 0}
    )
    if by_name:
        await db.company_mappings.update_one(
            {"company_uuid": by_name["company_uuid"], "tenant_id": tenant_id},
            {"$set": {"folder_id_hash": folder_hash}},
        )
        return by_name["company_uuid"]

    # 4) Nothing exists — create a fresh mapping keyed on both hashes.
    company_uuid = str(uuid.uuid4())
    await db.company_mappings.insert_one({
        "tenant_id": tenant_id,
        "company_uuid": company_uuid,
        "folder_id_hash": folder_hash,
        "company_name_encrypted": encrypt_field(display_name),
        "company_name_hash": name_hash,
    })
    logger.info(
        f"Registered folder-keyed company mapping: folder='{folder_id}' "
        f"display='{display_name}' -> {company_uuid}"
    )
    return company_uuid


async def get_company_name(tenant_id: str, company_uuid: str) -> str:
    """Resolve a company UUID back to its display name."""
    mapping = await db.company_mappings.find_one({
        "tenant_id": tenant_id,
        "company_uuid": company_uuid
    }, {"_id": 0})
    if mapping:
        return decrypt_field(mapping["company_name_encrypted"])
    return company_uuid


async def get_company_uuid(tenant_id: str, company_name: str) -> str:
    """Find the UUID for a company name. Returns None if not found."""
    name = (company_name or "").strip()
    if not name:
        return None
    name_hash = _stable_name_hash(name)
    mapping = await db.company_mappings.find_one(
        {"tenant_id": tenant_id, "company_name_hash": name_hash}, {"_id": 0}
    )
    if mapping:
        return mapping["company_uuid"]
    # Legacy fallback — walk and decrypt
    async for m in db.company_mappings.find(
        {"tenant_id": tenant_id, "company_name_hash": {"$exists": False}}, {"_id": 0}
    ):
        try:
            if decrypt_field(m.get("company_name_encrypted", "")).strip() == name:
                return m["company_uuid"]
        except Exception:
            continue
    return None


async def get_all_company_mappings(tenant_id: str) -> list:
    """Get all company UUID -> name mappings for a tenant. De-duplicates by name."""
    mappings = await db.company_mappings.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).to_list(500)
    # De-duplicate by name (defends against legacy duplicate rows)
    seen = {}
    for m in mappings:
        try:
            name = decrypt_field(m.get("company_name_encrypted", "")).strip()
        except Exception:
            name = ""
        if not name or name in seen:
            continue
        seen[name] = m["company_uuid"]
    return [{"company_id": uid, "company_name": name} for name, uid in seen.items()]


async def resolve_company_names(tenant_id: str, company_uuids: list) -> dict:
    """Resolve a list of company UUIDs to their display names. Returns {uuid: name}."""
    if not company_uuids:
        return {}
    mappings = await db.company_mappings.find(
        {"tenant_id": tenant_id, "company_uuid": {"$in": company_uuids}},
        {"_id": 0}
    ).to_list(500)
    return {
        m["company_uuid"]: decrypt_field(m["company_name_encrypted"])
        for m in mappings
    }


async def deduplicate_company_mappings(tenant_id: str) -> dict:
    """One-shot cleanup: collapse duplicate company_mappings rows for a tenant
    into a single canonical UUID per name. Re-points all docs that referenced
    the obsolete UUIDs to the canonical one. Idempotent."""
    rows = await db.company_mappings.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(2000)
    by_name: dict[str, list[str]] = {}
    for r in rows:
        try:
            name = decrypt_field(r.get("company_name_encrypted", "")).strip()
        except Exception:
            continue
        if not name:
            continue
        by_name.setdefault(name, []).append(r["company_uuid"])

    canonical_map = {}     # name -> canonical uuid
    obsolete_map = {}      # obsolete_uuid -> canonical_uuid
    for name, uuids in by_name.items():
        canonical = uuids[0]
        canonical_map[name] = canonical
        for u in uuids[1:]:
            obsolete_map[u] = canonical

    if not obsolete_map:
        return {"removed": 0, "repointed": 0, "canonical": canonical_map}

    # Re-point every collection that stamps `company_id`
    repointed = 0
    target_collections = await db.list_collection_names()
    for coll in target_collections:
        if coll.startswith("system.") or coll == "company_mappings":
            continue
        try:
            for obsolete, canonical in obsolete_map.items():
                res = await db[coll].update_many(
                    {"tenant_id": tenant_id, "company_id": obsolete},
                    {"$set": {"company_id": canonical}},
                )
                repointed += res.modified_count
        except Exception as e:
            logger.warning(f"dedup: skip collection {coll}: {e}")

    # Drop obsolete mapping rows
    res = await db.company_mappings.delete_many(
        {"tenant_id": tenant_id, "company_uuid": {"$in": list(obsolete_map.keys())}}
    )
    # Stamp the deterministic hash on every surviving canonical row
    for name, uid in canonical_map.items():
        await db.company_mappings.update_one(
            {"tenant_id": tenant_id, "company_uuid": uid},
            {"$set": {"company_name_hash": _stable_name_hash(name)}},
        )
    # Re-point user.companies arrays too
    user_repointed = 0
    async for u in db.users.find({"tenant_id": tenant_id}, {"_id": 0, "username": 1, "companies": 1}):
        comps = u.get("companies") or []
        new_comps = list({obsolete_map.get(c, c) for c in comps})  # de-dup
        if new_comps != comps:
            await db.users.update_one(
                {"username": u["username"]},
                {"$set": {"companies": new_comps}},
            )
            user_repointed += 1

    logger.info(f"dedup tenant={tenant_id}: removed {res.deleted_count} dupes, "
                f"repointed {repointed} docs across {len(target_collections)} colls, "
                f"updated {user_repointed} users")
    return {
        "removed": res.deleted_count,
        "repointed": repointed,
        "users_updated": user_repointed,
        "canonical": canonical_map,
    }
