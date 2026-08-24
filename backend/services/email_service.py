"""
Email service for FLOWRA subscription lifecycle emails.
Uses Resend API. Emails sent from support@flowralive.in.

CC policy:
  • GLOBAL_ADMIN_CC is auto-included on general administrative / business
    information emails (lead alerts, renewals, expiry reminders, employee-
    added admin notifications, Insights-branded mails).
  • Sensitive emails (passwords, OTPs, credentials, password resets) MUST
    pass cc=None to suppress the global CC.
"""
import os
import asyncio
import logging
import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "support@flowralive.in")

# Admin recipient that must be CC'd on all non-sensitive emails.
GLOBAL_ADMIN_CC = "jodidarindiaoffice@gmail.com"
# Where new-lead / Insights signup notifications land (TO field).
LEAD_NOTIFY_TO = "support@flowralive.in"
# FLOWRA logo hosted on the marketing site.
FLOWRA_LOGO_URL = "https://flowralive.in/assets/flowra-logo.png"

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def send_email(to_email, subject: str, html: str, cc=None, tag: str = "") -> bool:
    """Send an email via Resend.

    Args:
        to_email: A single email string or a list of recipient emails.
        subject:  Email subject. Callers add any branding prefix themselves.
        html:     Rendered HTML body.
        cc:       List/string of CC addresses, or the sentinel value
                  ``None`` to suppress the global admin CC (used for
                  sensitive emails like credentials/OTP/password resets).
                  Pass ``"auto"`` (default) to attach GLOBAL_ADMIN_CC.
        tag:      Optional Resend tag (e.g. "insights", "lead").
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email")
        return False

    to_list = [to_email] if isinstance(to_email, str) else list(to_email)

    if cc == "auto":
        cc_list = [GLOBAL_ADMIN_CC]
    elif cc is None:
        cc_list = []
    elif isinstance(cc, str):
        cc_list = [cc]
    else:
        cc_list = list(cc)

    # Never let the global CC duplicate the TO address.
    cc_list = [c for c in cc_list if c and c.lower() not in {t.lower() for t in to_list}]

    try:
        params = {
            "from": f"FLOWRA <{SENDER_EMAIL}>",
            "to": to_list,
            "subject": subject,
            "html": html,
        }
        if cc_list:
            params["cc"] = cc_list
        if tag:
            params["tags"] = [{"name": "category", "value": tag}]
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_list} (cc={cc_list}): {result.get('id', 'ok')}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to_list}: {e}")
        return False


def _base_template(content: str, insights: bool = False) -> str:
    """Wrap content in FLOWRA email template.

    When ``insights=True`` the header carries the FLOWRA logo and an
    explicit "FLOWRA Insights" sub-brand band — used for lead alerts and
    general business notifications.
    """
    insights_band = (
        '<div style="font-size:11px;color:#bfdbfe;margin-top:6px;'
        'letter-spacing:3px;text-transform:uppercase;font-weight:600;">'
        'FLOWRA INSIGHTS</div>'
        if insights else ''
    )
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
      <img src="{FLOWRA_LOGO_URL}" alt="FLOWRA" width="44" height="44" style="display:inline-block;border-radius:8px;background:#fff;padding:4px;margin-bottom:8px;" />
      <div style="font-size:28px;font-weight:800;color:#ffffff;letter-spacing:1px;">FLOWRA</div>
      <div style="font-size:12px;color:#93c5fd;margin-top:4px;letter-spacing:2px;">ORGANIZE &middot; AUTOMATE &middot; ACCELERATE</div>
      {insights_band}
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


async def send_subscription_started(to_email: str, name: str, plan: str, months: int, expires_date: str, password: str = ""):
    """Email when a new subscription starts. When `password` is provided,
    includes a login-credentials block so the new admin can sign in
    immediately. The email plainly tells the user to change the password
    after first login."""
    creds_block = ""
    if password:
        creds_block = f"""
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:16px 20px;margin-bottom:24px;">
        <tr><td>
          <div style="font-size:12px;color:#854d0e;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">🔐 Your Login Credentials</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#713f12;">Login URL</td>
              <td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;"><a href="https://insights.flowralive.in" style="color:#2563EB;text-decoration:none;">insights.flowralive.in</a></td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#713f12;">User ID</td>
              <td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;font-family:'SFMono-Regular',Consolas,Menlo,monospace;">{to_email}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#713f12;">Password</td>
              <td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;font-family:'SFMono-Regular',Consolas,Menlo,monospace;">{password}</td>
            </tr>
          </table>
          <p style="font-size:11px;color:#854d0e;margin:10px 0 0;line-height:1.5;">
            ⚠️ For your security, please change this password right after your first login from <strong>Profile → Change Password</strong>. Do not share these credentials.
          </p>
        </td></tr>
      </table>
    """
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
      {creds_block}

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
    return await send_email(to_email, "Welcome to FLOWRA — Your Subscription is Active!", _base_template(content), cc=None, tag="welcome")


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
    return await send_email(
        to_email,
        "FLOWRA Insights · Subscription Renewed — You're All Set!",
        _base_template(content, insights=True),
        cc="auto",
        tag="insights-renewal",
    )


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
    subject = f"FLOWRA Insights · {'URGENT: ' if days_left <= 7 else ''}Subscription Expires in {days_left} Day{'s' if days_left != 1 else ''}"
    return await send_email(
        to_email,
        subject,
        _base_template(content, insights=True),
        cc="auto",
        tag="insights-expiry",
    )


async def send_employee_created_to_employee(to_email: str, employee_name: str, password: str, admin_company: str):
    """Email to new employee with their login credentials."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">Your FLOWRA Account is Ready</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">Hi {employee_name}, you've been added to <strong>{admin_company}</strong> on FLOWRA.</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border:1px solid #bfdbfe;border-radius:8px;padding:20px;margin-bottom:24px;">
        <tr><td>
          <div style="font-size:11px;color:#2563EB;font-weight:700;letter-spacing:1px;margin-bottom:12px;">YOUR LOGIN CREDENTIALS</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Email (User ID)</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{to_email}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Password</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;font-family:monospace;background:#fff;border-radius:4px;padding:4px 8px;">{password}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Role</td>
              <td style="padding:6px 0;font-size:14px;color:#2563EB;font-weight:600;text-align:right;">Employee</td>
            </tr>
          </table>
        </td></tr>
      </table>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;margin-bottom:24px;">
        <tr><td style="font-size:12px;color:#92400e;">
          <strong>Security Tip:</strong> Please change your password after your first login from your Profile settings.
        </td></tr>
      </table>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://www.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Login to FLOWRA</a>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#94a3b8;margin:20px 0 0;text-align:center;">Need help? Contact your administrator or reach us at support@flowralive.in</p>
    """
    return await send_email(to_email, f"Your FLOWRA Account — Login Credentials for {admin_company}", _base_template(content), cc=None, tag="credentials")


async def send_employee_created_to_admin(to_email: str, admin_name: str, employee_name: str, employee_email: str, employee_role: str):
    """Email to admin confirming a new employee was created."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">New Employee Added</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">Hi {admin_name}, a new employee account has been created under your organization.</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:20px;margin-bottom:24px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Employee Name</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{employee_name}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Email</td>
              <td style="padding:6px 0;font-size:14px;color:#1e293b;font-weight:600;text-align:right;">{employee_email}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Role</td>
              <td style="padding:6px 0;font-size:14px;color:#2563EB;font-weight:600;text-align:right;">{employee_role.title()}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#64748b;">Status</td>
              <td style="padding:6px 0;font-size:14px;color:#16a34a;font-weight:700;text-align:right;">ACTIVE</td>
            </tr>
          </table>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#64748b;line-height:1.6;margin-bottom:20px;">
        The employee has been emailed their login credentials. They can access FLOWRA immediately using the credentials you set.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://www.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Manage Employees</a>
        </td></tr>
      </table>
    """
    return await send_email(
        to_email,
        f"FLOWRA Insights · Employee Added — {employee_name} ({employee_email})",
        _base_template(content, insights=True),
        cc="auto",
        tag="insights-employee",
    )



# ==================== INSIGHTS LANDING-PAGE LEAD NOTIFICATIONS ====================

def _row(label: str, value: str, value_color: str = "#1e293b") -> str:
    """Helper: render a label/value row inside the lead summary table."""
    safe = (value or "—").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<tr>'
        f'<td style="padding:6px 0;font-size:13px;color:#64748b;width:38%;">{label}</td>'
        f'<td style="padding:6px 0;font-size:14px;color:{value_color};'
        f'font-weight:600;text-align:right;">{safe}</td>'
        f'</tr>'
    )


async def send_lead_signup_notification(prospect: dict) -> bool:
    """Notify admins (support@ + jodidarindiaoffice CC) of a new Insights
    landing-page signup ("Start Free Trial" form)."""
    company = prospect.get("company_name", "")
    contact = prospect.get("contact_person", "")
    email = prospect.get("email", "")
    phone = prospect.get("phone", "")
    plan = prospect.get("selected_plan", "—")
    gst = prospect.get("gst_number", "")
    address = prospect.get("address", "")
    message = prospect.get("message", "")
    referral = prospect.get("referral_code", "")
    pid = prospect.get("prospect_id", "")
    returning = prospect.get("returning_user", False)
    ip = prospect.get("ip_address", "")

    msg_block = ""
    if message:
        safe_msg = message.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        msg_block = (
            '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;'
            'padding:14px 18px;margin-bottom:24px;">'
            '<div style="font-size:11px;color:#92400e;font-weight:700;letter-spacing:1px;'
            'text-transform:uppercase;margin-bottom:6px;">Prospect Message</div>'
            f'<div style="font-size:13px;color:#451a03;line-height:1.6;">{safe_msg}</div>'
            '</div>'
        )

    returning_badge = (
        '<span style="display:inline-block;background:#fee2e2;color:#b91c1c;font-size:10px;'
        'font-weight:700;padding:3px 8px;border-radius:4px;letter-spacing:1px;margin-left:8px;">'
        'RETURNING USER</span>'
        if returning else ''
    )

    content = f"""
      <span style="display:inline-block;background:#dcfce7;color:#15803d;font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;letter-spacing:1px;">NEW LEAD</span>{returning_badge}
      <h2 style="margin:10px 0 8px;font-size:22px;color:#1e293b;">New Free-Trial Signup</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">A prospect just submitted the <strong>Start Free Trial</strong> form on insights.flowralive.in.</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-radius:8px;padding:20px;margin-bottom:20px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            {_row('Prospect ID', pid, '#2563EB')}
            {_row('Company', company)}
            {_row('Contact Person', contact)}
            {_row('Email', email)}
            {_row('Phone', phone)}
            {_row('Plan Interested', (plan or '—').title() if plan else '—', '#2563EB')}
            {_row('GST Number', gst)}
            {_row('Address', address)}
            {_row('Referral Code', referral)}
            {_row('Submitted From IP', ip)}
          </table>
        </td></tr>
      </table>

      {msg_block}

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://insights.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Open Super-Admin Console</a>
        </td></tr>
      </table>

      <p style="font-size:12px;color:#94a3b8;margin:20px 0 0;text-align:center;">
        Reach out to the prospect within 24 hours for best conversion.
      </p>
    """
    subject = f"FLOWRA Insights · New Lead — {company or contact or email}"
    return await send_email(
        LEAD_NOTIFY_TO,
        subject,
        _base_template(content, insights=True),
        cc=GLOBAL_ADMIN_CC,
        tag="insights-lead",
    )


async def send_prospect_welcome_email(prospect: dict) -> bool:
    """iter-123: Auto-welcome email to the prospect the moment their
    enquiry lands. Sets expectations (24h SLA, no card required),
    reinforces the DPDP consent they just gave, and gives them a quick
    "book a slot" CTA so keen leads don't have to wait for our team."""
    company = prospect.get("company_name", "")
    contact = prospect.get("contact_person", "")
    email = prospect.get("email", "")
    plan = (prospect.get("selected_plan") or "").title() or "Free Trial"
    pid = prospect.get("prospect_id", "")
    first_name = contact.split()[0] if contact else "there"

    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">Thanks for reaching out, {first_name}!</h2>
      <p style="color:#334155;font-size:14px;margin:0 0 18px;line-height:1.7;">
        We've received your enquiry for <b>{company or 'your business'}</b> and someone
        from the FLOWRA team will reach out within <b>one working day</b> to walk you
        through the platform on your own data.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border:1px solid #dbeafe;border-radius:8px;padding:18px 22px;margin-bottom:22px;">
        <tr><td>
          <div style="font-size:11px;color:#1d4ed8;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Enquiry snapshot</div>
          <p style="margin:2px 0;font-size:13px;color:#1e293b;"><b>Reference:</b> {pid}</p>
          <p style="margin:2px 0;font-size:13px;color:#1e293b;"><b>Plan of interest:</b> {plan}</p>
          <p style="margin:2px 0;font-size:13px;color:#1e293b;"><b>Contact email:</b> {email}</p>
        </td></tr>
      </table>

      <p style="color:#334155;font-size:14px;margin:0 0 12px;line-height:1.7;">
        <b>What happens next?</b>
      </p>
      <ol style="margin:0 0 18px 0;padding-left:22px;font-size:13.5px;color:#334155;line-height:1.9;">
        <li>Our onboarding team studies your enquiry and picks the right specialist.</li>
        <li>You get a call &amp; a personalised 20-minute demo on Tally or Busy* data.</li>
        <li>Start the 14-day <b>Free Trial</b> with full Enterprise access &mdash; no card required.</li>
      </ol>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0 24px;">
          <a href="https://insights.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Explore FLOWRA</a>
        </td></tr>
      </table>

      <div style="border-top:1px solid #e2e8f0;padding-top:14px;margin-top:8px;">
        <p style="font-size:11px;color:#94a3b8;line-height:1.55;margin:0;">
          <b>DPDP Act, 2023 Notice:</b> You gave consent for JODIDAR INDIA to process the
          personal data you shared (name, business email, phone, GSTIN, address) for
          onboarding, demos and lifecycle communication of FLOWRA. Withdraw consent
          any time or request access, correction or erasure by writing to
          <a href="mailto:privacy@flowralive.in" style="color:#2563EB;">privacy@flowralive.in</a>.
        </p>
      </div>
    """
    subject = f"We've got your FLOWRA enquiry, {first_name} — next steps inside"
    return await send_email(
        email, subject,
        _base_template(content, insights=True),
        tag="prospect-welcome",
    )


async def send_lead_demo_requested_notification(prospect: dict) -> bool:
    """Notify admins when an existing prospect requests demo access."""
    company = prospect.get("company_name", "")
    email = prospect.get("email", "")
    pid = prospect.get("prospect_id", "")

    content = f"""
      <span style="display:inline-block;background:#dbeafe;color:#1d4ed8;font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;letter-spacing:1px;">DEMO REQUESTED</span>
      <h2 style="margin:10px 0 8px;font-size:22px;color:#1e293b;">Prospect Requested a Demo</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
        <strong>{company or email}</strong> has just clicked "Try Demo" on the Insights landing page.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-radius:8px;padding:20px;margin-bottom:20px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            {_row('Prospect ID', pid, '#2563EB')}
            {_row('Company', company)}
            {_row('Email', email)}
          </table>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#64748b;line-height:1.6;">
        This prospect is actively exploring FLOWRA — a good moment to follow up
        with a personalised demo invite.
      </p>
    """
    subject = f"FLOWRA Insights · Demo Requested — {company or email}"
    return await send_email(
        LEAD_NOTIFY_TO,
        subject,
        _base_template(content, insights=True),
        cc=GLOBAL_ADMIN_CC,
        tag="insights-demo",
    )


async def send_lead_requirements_notification(prospect: dict, requirements, notes: str = "") -> bool:
    """Notify admins when a prospect submits feature requirements after demo."""
    company = prospect.get("company_name", "")
    email = prospect.get("email", "")
    pid = prospect.get("prospect_id", "")

    req_list = requirements if isinstance(requirements, list) else []
    req_html = "".join(
        f'<li style="padding:4px 0;font-size:13px;color:#334155;">'
        f'{str(r).replace("<", "&lt;").replace(">", "&gt;")}</li>'
        for r in req_list
    ) or '<li style="font-size:13px;color:#94a3b8;">(no specific items)</li>'

    notes_block = ""
    if notes:
        safe_notes = notes.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        notes_block = (
            '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;'
            'padding:14px 18px;margin-bottom:24px;">'
            '<div style="font-size:11px;color:#92400e;font-weight:700;letter-spacing:1px;'
            'text-transform:uppercase;margin-bottom:6px;">Additional Notes</div>'
            f'<div style="font-size:13px;color:#451a03;line-height:1.6;">{safe_notes}</div>'
            '</div>'
        )

    content = f"""
      <span style="display:inline-block;background:#ede9fe;color:#6d28d9;font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;letter-spacing:1px;">REQUIREMENTS SUBMITTED</span>
      <h2 style="margin:10px 0 8px;font-size:22px;color:#1e293b;">Prospect Shared Their Requirements</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
        <strong>{company or email}</strong> completed the post-demo questionnaire.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-radius:8px;padding:20px;margin-bottom:20px;">
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            {_row('Prospect ID', pid, '#2563EB')}
            {_row('Company', company)}
            {_row('Email', email)}
          </table>
        </td></tr>
      </table>

      <div style="margin-bottom:20px;">
        <div style="font-size:11px;color:#2563EB;font-weight:700;letter-spacing:1px;
          text-transform:uppercase;margin-bottom:8px;">Requested Features</div>
        <ul style="margin:0;padding-left:20px;">{req_html}</ul>
      </div>

      {notes_block}

      <p style="font-size:13px;color:#64748b;line-height:1.6;">
        Prepare a tailored proposal and reach out to close.
      </p>
    """
    subject = f"FLOWRA Insights · Requirements Submitted — {company or email}"
    return await send_email(
        LEAD_NOTIFY_TO,
        subject,
        _base_template(content, insights=True),
        cc=GLOBAL_ADMIN_CC,
        tag="insights-requirements",
    )



# ─── Rich Welcome + 14-day Trial Reminder Templates (Phase A) ────────────

def _fmt_kv_row(label: str, value: str) -> str:
    """Small helper to render one row inside the details table."""
    safe = "" if value is None else str(value)
    return (
        f'<tr>'
        f'<td style="padding:6px 0;font-size:13px;color:#64748b;">{label}</td>'
        f'<td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;">{safe}</td>'
        f'</tr>'
    )


async def send_welcome_admin_rich(
    to_email: str, name: str, password: str, plan: str,
    plan_price_display: str, billing_cycle: str, subscription_display: str,
    company_name: str = "", mobile: str = "", gst: str = "",
    address: str = "", city: str = "", industry: str = "",
    sales_count: int = 0, dispatch_count: int = 0,
    is_trial: bool = False, trial_end_display: str = "",
):
    """Rich welcome mail sent when a Super Admin creates a customer.

    Includes ALL the details captured on the form so the recipient can
    verify what was recorded, plus their login credentials and the plan
    details. When ``is_trial`` is True, adds a prominent trial countdown
    banner and a 'convert now' CTA."""
    trial_banner = ""
    if is_trial:
        trial_banner = f"""
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#ecfeff;border:1px solid #67e8f9;border-radius:8px;padding:14px 18px;margin-bottom:24px;">
        <tr><td>
          <div style="font-size:12px;color:#0e7490;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">14-Day Free Trial</div>
          <div style="font-size:14px;color:#0f172a;line-height:1.55;">You have <strong>full Enterprise access</strong> until <strong>{trial_end_display}</strong>. Convert to a paid plan any time before then to keep your data and dashboards.</div>
        </td></tr>
      </table>"""

    company_row  = _fmt_kv_row("Company",           company_name) if company_name else ""
    mobile_row   = _fmt_kv_row("Mobile / WhatsApp", mobile)       if mobile else ""
    gst_row      = _fmt_kv_row("GST",               gst)          if gst else ""
    city_row     = _fmt_kv_row("City",              city)         if city else ""
    address_row  = _fmt_kv_row("Address",           address)      if address else ""
    industry_row = _fmt_kv_row("Industry",          industry)     if industry else ""
    team_row     = _fmt_kv_row("Team split",
                               f"{sales_count} sales · {dispatch_count} dispatch") if (sales_count or dispatch_count) else ""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">Welcome to FLOWRA, {name.split()[0] if name else 'there'}!</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px;line-height:1.55;">
        We've set up your FLOWRA workspace with the details you shared. Below is a copy for your records &mdash; please verify and reply to this email if anything looks off.
      </p>

      {trial_banner}

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-radius:8px;padding:20px;margin-bottom:20px;">
        <tr><td>
          <div style="font-size:12px;color:#1e40af;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">Your Plan</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            {_fmt_kv_row("Plan",           plan)}
            {_fmt_kv_row("Price",          plan_price_display)}
            {_fmt_kv_row("Billing cycle",  billing_cycle.title())}
            {_fmt_kv_row("Subscription",   subscription_display)}
          </table>
        </td></tr>
      </table>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin-bottom:20px;">
        <tr><td>
          <div style="font-size:12px;color:#334155;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">Account Details</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            {_fmt_kv_row("Name",  name)}
            {_fmt_kv_row("Email", to_email)}
            {company_row}
            {mobile_row}
            {gst_row}
            {city_row}
            {address_row}
            {industry_row}
            {team_row}
          </table>
        </td></tr>
      </table>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:16px 20px;margin-bottom:24px;">
        <tr><td>
          <div style="font-size:12px;color:#854d0e;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">Your Login Credentials</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#713f12;">Login URL</td>
              <td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;"><a href="https://insights.flowralive.in" style="color:#2563EB;text-decoration:none;">insights.flowralive.in</a></td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#713f12;">User ID</td>
              <td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;font-family:'SFMono-Regular',Consolas,Menlo,monospace;">{to_email}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;font-size:13px;color:#713f12;">Password</td>
              <td style="padding:6px 0;font-size:13px;color:#1e293b;font-weight:600;text-align:right;font-family:'SFMono-Regular',Consolas,Menlo,monospace;">{password}</td>
            </tr>
          </table>
          <p style="font-size:11px;color:#854d0e;margin:10px 0 0;line-height:1.5;">
            For your safety, please change this password right after your first login under <strong>Profile &rarr; Change Password</strong>.
          </p>
        </td></tr>
      </table>

      <h3 style="font-size:15px;color:#1e293b;margin:0 0 12px;">Get started in 3 steps</h3>
      <ol style="margin:0 0 20px;padding-left:22px;font-size:14px;color:#334155;line-height:1.7;">
        <li>Log in to <a href="https://insights.flowralive.in" style="color:#2563EB;text-decoration:none;">insights.flowralive.in</a> with the credentials above.</li>
        <li>Open <strong>Setup</strong> and download the FLOWRA Desktop Agent for your ERP (Tally or Busy).</li>
        <li>Run the agent once to sync your books &mdash; your dashboards populate within minutes.</li>
      </ol>

      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://insights.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Log in to FLOWRA</a>
        </td></tr>
      </table>

      <p style="font-size:13px;color:#94a3b8;margin:20px 0 0;text-align:center;">Questions? Reply to this email or WhatsApp us on +91 81204 70018.</p>
    """
    subject_prefix = "Your 14-day FLOWRA trial is live" if is_trial else "Welcome to FLOWRA"
    subject = f"{subject_prefix} \u2014 {plan}"
    # We DO cc the global admin here (business record) but suppress if
    # you'd rather keep passwords private — callers get to choose via
    # standard cc arg.
    return await send_email(to_email, subject, _base_template(content), cc=None, tag="welcome-rich")


# ─── 14-day trial reminder emails (Day 5 / 8 / 12 / 14) ─────────────────

_TRIAL_CTA_URL = "https://insights.flowralive.in/profile?upgrade=1"


def _trial_reminder_footer() -> str:
    return (
        '<p style="font-size:12px;color:#94a3b8;margin:24px 0 0;text-align:center;line-height:1.55;">'
        'Not sure which plan fits? Reply to this email and we\'ll help you pick. '
        '&mdash; The FLOWRA team.</p>'
    )


async def send_trial_reminder_day5(to_email: str, name: str, days_left: int, trial_end_display: str, preview_only: bool = False):
    """Curiosity / education. Show them what to explore next."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">How's the first week going, {name.split()[0] if name else 'there'}?</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 20px;line-height:1.6;">
        You have <strong>{days_left} day{'s' if days_left != 1 else ''}</strong> left in your FLOWRA free trial (ends {trial_end_display}). Here's what most teams try in week 1 &mdash; if you haven't yet, now is a great time.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-radius:8px;padding:20px;margin-bottom:20px;">
        <tr><td>
          <ol style="margin:0;padding-left:22px;font-size:14px;color:#334155;line-height:1.9;">
            <li>Open the <strong>Dashboard</strong> and drill into a single-day sales trend.</li>
            <li>Try the <strong>AI Reports</strong> tab &mdash; ask "Top 10 slow-moving items this quarter".</li>
            <li>Head to <strong>Analytics &rarr; Demand Forecast</strong> and click any row for a per-SKU deep dive.</li>
            <li>Add one <strong>employee</strong> under Profile so they can log in with you.</li>
          </ol>
        </td></tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="https://insights.flowralive.in" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Continue the tour</a>
        </td></tr>
      </table>
      {_trial_reminder_footer()}
    """
    return await send_email(to_email,
        f"Day 5 of your FLOWRA trial \u2014 explore these 4 things",
        _base_template(content), cc="auto", tag="trial-d5") if not preview_only else {
        "subject": "Day 5 of your FLOWRA trial \u2014 explore these 4 things",
        "html":    _base_template(content),
    }


async def send_trial_reminder_day8(to_email: str, name: str, days_left: int, trial_end_display: str, preview_only: bool = False):
    """Halfway mark / progress-nudge with social proof."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1e293b;">You're past halfway, {name.split()[0] if name else 'there'}.</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 20px;line-height:1.6;">
        Only <strong>{days_left} day{'s' if days_left != 1 else ''}</strong> left in your free trial (ends {trial_end_display}). Most FLOWRA customers convert around this point &mdash; because by now they've caught at least one payment leak or slow-mover their spreadsheet missed.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#ecfdf5;border-left:4px solid #10b981;border-radius:6px;padding:16px 20px;margin-bottom:20px;">
        <tr><td>
          <div style="font-size:13px;color:#065f46;line-height:1.55;">
            <strong>What our customers say:</strong> <em>"FLOWRA paid for itself in the first month &mdash; we spotted &#8377;3L stuck with a single party and reworked our payment cycle."</em> &mdash; A dealer in Raipur.
          </div>
        </td></tr>
      </table>
      <p style="color:#334155;font-size:14px;margin:0 0 20px;line-height:1.6;">
        Lock in your plan now and we'll port every dashboard, sync-history entry and forecast snapshot you've generated so far. Nothing to redo.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="{_TRIAL_CTA_URL}" style="display:inline-block;background:#2563EB;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">See plans &amp; upgrade</a>
        </td></tr>
      </table>
      {_trial_reminder_footer()}
    """
    return await send_email(to_email,
        f"{days_left} days left on your FLOWRA trial \u2014 pick your plan",
        _base_template(content), cc="auto", tag="trial-d8") if not preview_only else {
        "subject": f"{days_left} days left on your FLOWRA trial \u2014 pick your plan",
        "html":    _base_template(content),
    }


async def send_trial_reminder_day12(to_email: str, name: str, days_left: int, trial_end_display: str, preview_only: bool = False):
    """Loss aversion / anchor. 2 days to go."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#b91c1c;">Two days left on your FLOWRA trial</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 20px;line-height:1.6;">
        Hi {name.split()[0] if name else 'there'} &mdash; your free trial ends on <strong>{trial_end_display}</strong> ({days_left} day{'s' if days_left != 1 else ''} to go). After that, log-in is paused until you pick a paid plan.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:18px 20px;margin-bottom:20px;">
        <tr><td>
          <div style="font-size:14px;color:#7f1d1d;line-height:1.6;">
            <strong>Here's what stays on FLOWRA when you convert:</strong>
            <ul style="margin:8px 0 0;padding-left:20px;">
              <li>Every sync, forecast and report you've created.</li>
              <li>Your desktop-agent connection &mdash; no re-install.</li>
              <li>Employee logins you've already provisioned.</li>
            </ul>
          </div>
        </td></tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="{_TRIAL_CTA_URL}" style="display:inline-block;background:#dc2626;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">Upgrade in 60 seconds</a>
        </td></tr>
      </table>
      {_trial_reminder_footer()}
    """
    return await send_email(to_email,
        f"48 hours left \u2014 keep your FLOWRA data",
        _base_template(content), cc="auto", tag="trial-d12") if not preview_only else {
        "subject": "48 hours left \u2014 keep your FLOWRA data",
        "html":    _base_template(content),
    }


async def send_trial_reminder_day14(to_email: str, name: str, trial_end_display: str, preview_only: bool = False):
    """Final call. Urgency + lockout notice."""
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#b91c1c;">Your FLOWRA trial ends tonight</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 20px;line-height:1.6;">
        Hi {name.split()[0] if name else 'there'} &mdash; today is <strong>day 14 of your free FLOWRA trial</strong>. Log-in will be paused from {trial_end_display} onwards unless you convert to a paid plan.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef2f2;border:1px solid #f87171;border-radius:8px;padding:18px 20px;margin-bottom:20px;">
        <tr><td>
          <div style="font-size:14px;color:#7f1d1d;line-height:1.6;">
            Your dashboards, syncs and forecasts are safe &mdash; we keep them ready to switch on the moment you upgrade. But sign-in stops working after today.
          </div>
        </td></tr>
      </table>
      <p style="color:#334155;font-size:14px;margin:0 0 20px;line-height:1.6;">
        Take 60 seconds to pick a plan &mdash; Starter starts at &#8377;999/mo, Professional at &#8377;2,499/mo, Enterprise at &#8377;3,799/mo. Reply to this email if you'd like a walkthrough before deciding.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:8px 0;">
          <a href="{_TRIAL_CTA_URL}" style="display:inline-block;background:#dc2626;color:#ffffff;padding:14px 40px;border-radius:8px;font-size:15px;font-weight:700;text-decoration:none;">Convert now &mdash; keep access</a>
        </td></tr>
      </table>
      {_trial_reminder_footer()}
    """
    return await send_email(to_email,
        "Final day \u2014 your FLOWRA trial ends tonight",
        _base_template(content), cc="auto", tag="trial-d14") if not preview_only else {
        "subject": "Final day \u2014 your FLOWRA trial ends tonight",
        "html":    _base_template(content),
    }
