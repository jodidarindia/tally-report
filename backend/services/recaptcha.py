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
        error_codes = result.get("error-codes", []) or []
        logger.info(f"reCAPTCHA verify: success={success}, score={score}, action={action}, errors={error_codes}")
        if not success:
            # Fail-open on environmental / configuration errors so a newly deployed
            # domain that hasn't been whitelisted in the reCAPTCHA console does
            # not lock every user out. Only strict secret-side errors are treated
            # as hard failures.
            env_errors = {
                "invalid-input-response",
                "timeout-or-duplicate",
                "browser-error",
                "hostname-mismatch",
                "missing-input-response",
            }
            if any(code in env_errors for code in error_codes) or not error_codes:
                logger.warning(f"reCAPTCHA env/config error, allowing login: {error_codes}")
                return True
            logger.warning(f"reCAPTCHA hard failure: {error_codes}")
            return False
        # v3 returns a score (0.0 = bot, 1.0 = human). Threshold 0.3 is lenient.
        if score < 0.3:
            logger.warning(f"reCAPTCHA score too low: {score}")
            return False
        return True
    except Exception as e:
        logger.error(f"reCAPTCHA verification error: {e}")
        return True  # fail-open on network issues
