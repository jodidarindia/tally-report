"""
ID Mapping service for tenant and company UUIDs.
Maps opaque UUIDs to encrypted actual names for security.
"""
import uuid
import logging
from db import db
from services.encryption_service import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)


async def generate_tenant_id() -> str:
    """Generate a unique UUID-format tenant ID."""
    return str(uuid.uuid4())


async def generate_company_id() -> str:
    """Generate a unique UUID-format company ID."""
    return str(uuid.uuid4())


async def register_company_mapping(tenant_id: str, company_name: str) -> str:
    """Register a company name and return its UUID. If already mapped, return existing UUID."""
    existing = await db.company_mappings.find_one({
        "tenant_id": tenant_id,
        "company_name_encrypted": encrypt_field(company_name)
    }, {"_id": 0})
    if existing:
        return existing["company_uuid"]

    company_uuid = str(uuid.uuid4())
    await db.company_mappings.insert_one({
        "tenant_id": tenant_id,
        "company_uuid": company_uuid,
        "company_name_encrypted": encrypt_field(company_name),
    })
    logger.info(f"Registered company mapping: {company_name} -> {company_uuid}")
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
    encrypted_name = encrypt_field(company_name)
    mapping = await db.company_mappings.find_one({
        "tenant_id": tenant_id,
        "company_name_encrypted": encrypted_name
    }, {"_id": 0})
    if mapping:
        return mapping["company_uuid"]
    return None


async def get_all_company_mappings(tenant_id: str) -> list:
    """Get all company UUID -> name mappings for a tenant."""
    mappings = await db.company_mappings.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).to_list(100)
    result = []
    for m in mappings:
        result.append({
            "company_id": m["company_uuid"],
            "company_name": decrypt_field(m["company_name_encrypted"])
        })
    return result


async def resolve_company_names(tenant_id: str, company_uuids: list) -> dict:
    """Resolve a list of company UUIDs to their display names. Returns {uuid: name}."""
    if not company_uuids:
        return {}
    mappings = await db.company_mappings.find(
        {"tenant_id": tenant_id, "company_uuid": {"$in": company_uuids}},
        {"_id": 0}
    ).to_list(100)
    return {
        m["company_uuid"]: decrypt_field(m["company_name_encrypted"])
        for m in mappings
    }
