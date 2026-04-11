"""IST (Indian Standard Time) utility functions."""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Get current datetime in IST."""
    return datetime.now(IST)


def now_ist_iso() -> str:
    """Get current IST as ISO string."""
    return now_ist().isoformat()


def to_ist(dt_str: str) -> datetime:
    """Convert an ISO/UTC datetime string to IST datetime."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST)
    except Exception:
        return None


def format_ist(dt_str: str, fmt: str = "%d/%m/%Y, %H:%M:%S") -> str:
    """Format a datetime string to IST display format."""
    ist_dt = to_ist(dt_str)
    if not ist_dt:
        return "N/A"
    return ist_dt.strftime(fmt)


def format_ist_date(dt_str: str) -> str:
    """Format to IST date only."""
    return format_ist(dt_str, "%d %b %Y")


def subscription_expires_at(start_iso: str, months: int = 12) -> str:
    """Calculate subscription expiry from start date + months. Returns ISO string."""
    if not start_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        year = start.year + (start.month + months - 1) // 12
        month = (start.month + months - 1) % 12 + 1
        day = min(start.day, 28)
        expires = start.replace(year=year, month=month, day=day)
        return expires.isoformat()
    except Exception:
        return None


def is_subscription_active(start_iso: str, months: int = 12) -> bool:
    """Check if subscription is still active."""
    expires = subscription_expires_at(start_iso, months)
    if not expires:
        return True  # No start date means legacy account, treat as active
    try:
        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < exp_dt
    except Exception:
        return True


def days_until_expiry(start_iso: str, months: int = 12) -> int:
    """Return number of days until subscription expires. Negative = already expired."""
    expires = subscription_expires_at(start_iso, months)
    if not expires:
        return 999  # No date = effectively infinite
    try:
        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        delta = exp_dt - datetime.now(timezone.utc)
        return delta.days
    except Exception:
        return 999
