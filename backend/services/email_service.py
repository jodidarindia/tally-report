"""
Email service for FLOWRA subscription lifecycle emails.
Uses Resend API. Emails sent from support@flowralive.in.
"""
import os
import asyncio
import logging
import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "support@flowralive.in")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def send_email(to_email: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email")
        return False
    try:
        params = {
            "from": f"FLOWRA <{SENDER_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {result.get('id', 'ok')}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to_email}: {e}")
        return False


def _base_template(content: str) -> str:
    """Wrap content in FLOWRA email template."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:32px 16px;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06);">
  <!-- Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#2563EB,#1D4ED8);padding:28px 32px;text-align:center;">
      <div style="font-size:28px;font-weight:800;color:#ffffff;letter-spacing:1px;">FLOWRA</div>
      <div style="font-size:12px;color:#93c5fd;margin-top:4px;letter-spacing:2px;">ORGANIZE &middot; AUTOMATE &middot; ACCELERATE</div>
    </td>
  </tr>
  <!-- Body -->
  <tr>
    <td style="padding:32px;">
      {content}
    </td>
  </tr>
  <!-- Footer -->
  <tr>
    <td style="background:#f8fafc;padding:24px 32px;border-top:1px solid #e2e8f0;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-size:12px;color:#94a3b8;line-height:1.6;">
            <strong style="color:#64748b;">FLOWRA</strong> &mdash; A product by JODIDAR INDIA<br>
            <a href="https://www.flowralive.in" style="color:#2563EB;text-decoration:none;">www.flowralive.in</a><br>
            <a href="mailto:support@flowralive.in" style="color:#2563EB;text-decoration:none;">support@flowralive.in</a> &middot;
            <a href="https://wa.me/918120470018" style="color:#25D366;text-decoration:none;">WhatsApp</a>
          </td>
        </tr>
        <tr>
          <td style="font-size:10px;color:#cbd5e1;padding-top:12px;">
            Tally* is the trademark of its respective owner. This email was sent because you have an active FLOWRA account.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


async def send_subscription_started(to_email: str, name: str, plan: str, months: int, expires_date: str):
    """Email when a new subscription starts."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">Welcome to FLOWRA! 🎉</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">Your subscription is now active.</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-radius:8px;padding:20px;margin-bottom:24px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Account Name</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{name}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Plan</td>
              <td style="padding:6px 0;font-size:14px;color:#2563EB;font-weight:600;text-align:right;">{plan.title()}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Duration</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{months} month{'s' if months > 1 else ''}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Valid Until</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{expires_date}</td>
            </tr>
          </table>
        </td></tr>
      </table>

      <h3 style="font-size:15px;color:#1e293b;margin:0 0 12px;">Get Started in 3 Steps:</h3>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr>
          <td style="padding:8px 0;">
            <span style="display:inline-block;width:24px;height:24px;background:#2563EB;color:#fff;border-radius:50%;text-align:center;line-height:24px;font-size:12px;font-weight:700;margin-right:10px;">1</span>
            <span style="font-size:14px;color:#334155;">Download the <strong>FLOWRA Desktop Agent</strong> from Setup page</span>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;">
            <span style="display:inline-block;width:24px;height:24px;background:#2563EB;color:#fff;border-radius:50%;text-align:center;line-height:24px;font-size:12px;font-weight:700;margin-right:10px;">2</span>
            <span style="font-size:14px;color:#334155;">Connect with your <strong>Tally*</strong> software</span>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;">
            <span style="display:inline-block;width:24px;height:24px;background:#2563EB;color:#fff;border-radius:50%;text-align:center;line-height:24px;font-size:12px;font-weight:700;margin-right:10px;">3</span>
            <span style="font-size:14px;color:#334155;">Start syncing and explore your <strong>Dashboard</strong></span>
          </td>
        </tr>
      </table>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://www.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Login to FLOWRA</a>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#94a3b8;margin:20px 0 0;text-align:center;">Need help? Reply to this email or WhatsApp us at +91 81204 70018</p>
    """
    return await send_email(to_email, "Welcome to FLOWRA — Your Subscription is Active!", _base_template(content))


async def send_subscription_renewed(to_email: str, name: str, plan: str, months: int, new_expires_date: str):
    """Email when subscription is renewed."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">Subscription Renewed Successfully</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">Thank you for continuing with FLOWRA, {name}!</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:20px;margin-bottom:24px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Status</td>
              <td style="padding:6px 0;font-size:14px;color:#16a34a;font-weight:700;text-align:right;">RENEWED</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Plan</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{plan.title()}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Extended By</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{months} month{'s' if months > 1 else ''}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">New Expiry Date</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:700;text-align:right;">{new_expires_date}</td>
            </tr>
          </table>
        </td></tr>
      </table>

      <p style="font-size:14px;color:#334155;line-height:1.6;margin-bottom:24px;">
        Your FLOWRA subscription has been renewed. All your data, reports, and analytics remain intact. Continue enjoying uninterrupted Tally* sync and business insights.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://www.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Open Dashboard</a>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#94a3b8;margin:20px 0 0;text-align:center;">Questions about your subscription? Contact us at support@flowralive.in</p>
    """
    return await send_email(to_email, "FLOWRA Subscription Renewed — You're All Set!", _base_template(content))


async def send_subscription_expiry_warning(to_email: str, name: str, days_left: int, expires_date: str):
    """Email when subscription is about to expire."""
    urgency_color = "#dc2626" if days_left <= 7 else "#f59e0b"
    urgency_bg = "#fef2f2" if days_left <= 7 else "#fffbeb"
    urgency_border = "#fecaca" if days_left <= 7 else "#fde68a"
    urgency_label = "URGENT" if days_left <= 7 else "REMINDER"

    content = f"""
      <table width="100%" cellpadding="0" cellspacing="0" style="background:{urgency_bg};border:1px solid {urgency_border};border-radius:8px;padding:16px 20px;margin-bottom:24px;">
        <tr><td>
          <span style="display:inline-block;background:{urgency_color};color:#fff;font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;letter-spacing:1px;">{urgency_label}</span>
          <span style="font-size:14px;color:{urgency_color};font-weight:600;margin-left:8px;">Your subscription expires in {days_left} day{'s' if days_left != 1 else ''}!</span>
        </td></tr>
      </table>

      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">Subscription Expiring Soon</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">Hi {name}, your FLOWRA subscription is about to expire.</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:8px;padding:20px;margin-bottom:24px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Expires On</td>
              <td style="padding:6px 0;font-size:14px;color:{urgency_color};font-weight:700;text-align:right;">{expires_date}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Days Remaining</td>
              <td style="padding:6px 0;font-size:14px;color:{urgency_color};font-weight:700;text-align:right;">{days_left} day{'s' if days_left != 1 else ''}</td>
            </tr>
          </table>
        </td></tr>
      </table>

      <h3 style="font-size:15px;color:#1e293b;margin:0 0 12px;">What happens after expiry?</h3>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr><td style="padding:6px 0;font-size:13px;color:#64748b;">
          &#8226; Tally* sync will stop and your dashboard data won't update<br>
          &#8226; You will lose access to reports, analytics, and CRM features<br>
          &#8226; Your data remains safe for 90 days — renew anytime to restore
        </td></tr>
      </table>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://wa.me/918120470018?text=Hi%2C%20I%20want%20to%20renew%20my%20FLOWRA%20subscription" style="display:inline-block;background:#2563EB;color:#ffffff;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:700;text-decoration:none;">Renew Now</a>
        </td></tr>
        <tr><td align="center" style="padding:12px 0 0;">
          <a href="mailto:support@flowralive.in" style="font-size:13px;color:#2563EB;text-decoration:none;">Or email us at support@flowralive.in</a>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#94a3b8;margin:20px 0 0;text-align:center;">Don't lose your business insights — renew today!</p>
    """
    subject = f"{'URGENT: ' if days_left <= 7 else ''}Your FLOWRA Subscription Expires in {days_left} Day{'s' if days_left != 1 else ''}"
    return await send_email(to_email, subject, _base_template(content))
