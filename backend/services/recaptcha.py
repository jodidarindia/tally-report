import os
import requests
import logging

logger = logging.getLogger(__name__)

RECAPTCHA_SECRET = os.environ.get("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha(token: str) -> bool:
    """Verify a reCAPTCHA v3 token with Google. Returns True if score >= 0.3."""
    if not RECAPTCHA_SECRET:
        logger.warning("RECAPTCHA_SECRET_KEY not set — skipping verification")
        return True
    if not token:
        logger.warning("Empty reCAPTCHA token — allowing (reCAPTCHA may not have loaded)")
        return True
    try:
        resp = requests.post(RECAPTCHA_VERIFY_URL, data={
            "secret": RECAPTCHA_SECRET,
            "response": token,
        }, timeout=5)
        result = resp.json()
        success = result.get("success", False)
        score = result.get("score", 0)
        action = result.get("action", "")
        logger.info(f"reCAPTCHA verify: success={success}, score={score}, action={action}")
        if not success:
            logger.warning(f"reCAPTCHA failed: {result.get('error-codes', [])}")
            return False
        # v3 returns a score (0.0 = bot, 1.0 = human). Threshold 0.3 is lenient.
        if score < 0.3:
            logger.warning(f"reCAPTCHA score too low: {score}")
            return False
        return True
    except Exception as e:
        logger.error(f"reCAPTCHA verification error: {e}")
        return True  # fail-open on network issues
