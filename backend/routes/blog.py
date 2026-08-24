"""Blog CMS routes.

Public: `/api/public/blog` lists published posts, `/api/public/blog/{slug}`
serves a single post. SuperAdmin gets full CRUD + publish toggle.

Post schema (BSON `blogs` collection):
- slug           str, url-safe, unique
- title          str
- excerpt        str (used in listing cards + meta description)
- cover_image    str URL (optional)
- body_md        str Markdown/MDX body
- tags           list[str]
- author         str (defaults to author's display name)
- seo_title      str (falls back to title)
- seo_description str (falls back to excerpt)
- published      bool
- published_at   ISO 8601 (set the first time `published=True`)
- created_at     ISO 8601
- updated_at     ISO 8601
- view_count     int
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from db import db
from models import APIResponse
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:80] or f"post-{uuid.uuid4().hex[:6]}"


async def _require_super_admin(request: Request):
    user = await get_current_user(request, db)
    if not user:
        return None
    if user.get("role") not in ("super_admin", "flowra_staff"):
        return None
    return user


# ── Public ────────────────────────────────────────────────────────────

@router.get("/public/blog")
async def public_list_blog(tag: str = "", limit: int = 20, skip: int = 0):
    """Public listing of PUBLISHED blog posts. Optional ?tag=… filter."""
    try:
        q = {"published": True}
        if tag:
            q["tags"] = tag
        cursor = db.blogs.find(q, {"_id": 0, "body_md": 0}).sort("published_at", -1).skip(skip).limit(min(limit, 100))
        posts = await cursor.to_list(min(limit, 100))
        total = await db.blogs.count_documents(q)
        # Collect all tag facets for nav.
        tags = set()
        async for t in db.blogs.aggregate([
            {"$match": {"published": True}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags"}},
        ]):
            if t.get("_id"):
                tags.add(t["_id"])
        return APIResponse(success=True, data={
            "posts": posts, "total": total, "tags": sorted(tags),
        })
    except Exception as e:
        logger.error(f"public_list_blog: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/public/blog/{slug}")
async def public_get_blog(slug: str):
    try:
        post = await db.blogs.find_one({"slug": slug, "published": True}, {"_id": 0})
        if not post:
            return APIResponse(success=False, error="Post not found")
        # Non-blocking view counter (best-effort).
        try:
            await db.blogs.update_one({"slug": slug}, {"$inc": {"view_count": 1}})
        except Exception:
            pass
        return APIResponse(success=True, data=post)
    except Exception as e:
        logger.error(f"public_get_blog: {e}")
        return APIResponse(success=False, error=str(e))


# ── SuperAdmin CRUD ───────────────────────────────────────────────────

@router.get("/super-admin/blog")
async def sa_list_blog(request: Request):
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Forbidden")
    try:
        posts = await db.blogs.find({}, {"_id": 0, "body_md": 0}).sort("created_at", -1).to_list(500)
        total = len(posts)
        published_count = sum(1 for p in posts if p.get("published"))
        return APIResponse(success=True, data={
            "posts": posts,
            "stats": {
                "total": total,
                "published": published_count,
                "drafts": total - published_count,
            },
        })
    except Exception as e:
        logger.error(f"sa_list_blog: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/super-admin/blog/{post_id}")
async def sa_get_blog(post_id: str, request: Request):
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Forbidden")
    post = await db.blogs.find_one({"post_id": post_id}, {"_id": 0})
    if not post:
        return APIResponse(success=False, error="Post not found")
    return APIResponse(success=True, data=post)


@router.post("/super-admin/blog")
async def sa_create_blog(request: Request):
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Forbidden")
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return APIResponse(success=False, error="Title is required")
    slug = _slugify(body.get("slug") or title)
    # Ensure unique slug.
    if await db.blogs.find_one({"slug": slug}):
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"

    now = datetime.now(timezone.utc).isoformat()
    published = bool(body.get("published"))
    doc = {
        "post_id":         f"BLG-{uuid.uuid4().hex[:8].upper()}",
        "slug":            slug,
        "title":           title,
        "excerpt":         (body.get("excerpt") or "").strip()[:280],
        "cover_image":     (body.get("cover_image") or "").strip(),
        "body_md":         body.get("body_md") or "",
        "tags":            [t.strip() for t in (body.get("tags") or []) if t and isinstance(t, str)][:10],
        "author":          (body.get("author") or sa.get("name") or sa.get("username") or "FLOWRA Team").strip(),
        "seo_title":       (body.get("seo_title") or title).strip()[:70],
        "seo_description": (body.get("seo_description") or body.get("excerpt") or "").strip()[:160],
        "published":       published,
        "published_at":    now if published else "",
        "created_at":      now,
        "updated_at":      now,
        "created_by":      sa.get("username"),
        "view_count":      0,
    }
    await db.blogs.insert_one(doc)
    return APIResponse(success=True, data={"post_id": doc["post_id"], "slug": slug}, message="Blog post created")


@router.put("/super-admin/blog/{post_id}")
async def sa_update_blog(post_id: str, request: Request):
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Forbidden")
    body = await request.json()
    existing = await db.blogs.find_one({"post_id": post_id}, {"_id": 0})
    if not existing:
        return APIResponse(success=False, error="Post not found")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for k in ("title", "excerpt", "cover_image", "body_md", "author", "seo_title", "seo_description"):
        if k in body:
            update[k] = (body.get(k) or "").strip() if isinstance(body.get(k), str) else body.get(k)
    if "tags" in body and isinstance(body["tags"], list):
        update["tags"] = [t.strip() for t in body["tags"] if t and isinstance(t, str)][:10]
    if "slug" in body and body["slug"]:
        new_slug = _slugify(body["slug"])
        if new_slug != existing.get("slug"):
            if await db.blogs.find_one({"slug": new_slug, "post_id": {"$ne": post_id}}):
                return APIResponse(success=False, error="Slug already in use")
            update["slug"] = new_slug
    if "published" in body:
        is_pub = bool(body["published"])
        update["published"] = is_pub
        if is_pub and not existing.get("published_at"):
            update["published_at"] = datetime.now(timezone.utc).isoformat()

    await db.blogs.update_one({"post_id": post_id}, {"$set": update})
    return APIResponse(success=True, message="Blog post updated")


@router.delete("/super-admin/blog/{post_id}")
async def sa_delete_blog(post_id: str, request: Request):
    sa = await _require_super_admin(request)
    if not sa:
        return APIResponse(success=False, error="Forbidden")
    r = await db.blogs.delete_one({"post_id": post_id})
    if r.deleted_count == 0:
        return APIResponse(success=False, error="Post not found")
    return APIResponse(success=True, message="Blog post deleted")
