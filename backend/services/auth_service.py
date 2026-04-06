import os
import secrets
import asyncio
import resend
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

class AuthService:
    def __init__(self):
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.sender_email = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
        if self.resend_api_key:
            resend.api_key = self.resend_api_key
    
    def generate_otp(self) -> str:
        """Generate 6-digit OTP"""
        return str(secrets.randbelow(1000000)).zfill(6)
    
    def generate_session_token(self) -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    async def send_otp_email(self, email: str, otp: str) -> bool:
        """Send OTP via email using Resend"""
        try:
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #064E3B 0%, #047857 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                        <h1 style="margin: 0; font-size: 28px;">Tally Reports</h1>
                        <p style="margin: 10px 0 0 0; opacity: 0.9;">Your Login Verification Code</p>
                    </div>
                    
                    <div style="background: #FDFBF7; padding: 40px; border-radius: 10px; margin-top: 20px;">
                        <h2 style="color: #1C1917; margin-top: 0;">Your OTP Code</h2>
                        <p style="color: #44403C; font-size: 16px; line-height: 1.6;">
                            Use this code to complete your login:
                        </p>
                        
                        <div style="background: white; border: 2px solid #064E3B; border-radius: 8px; padding: 20px; text-align: center; margin: 30px 0;">
                            <div style="font-size: 36px; font-weight: bold; color: #064E3B; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                                {otp}
                            </div>
                        </div>
                        
                        <p style="color: #78716C; font-size: 14px;">
                            This code will expire in <strong>10 minutes</strong>.
                        </p>
                        <p style="color: #78716C; font-size: 14px;">
                            If you didn't request this code, please ignore this email.
                        </p>
                    </div>
                    
                    <div style="text-align: center; margin-top: 30px; color: #A8A29E; font-size: 12px;">
                        <p>Tally SaaS Report Builder - AI-Powered Analytics</p>
                    </div>
                </body>
            </html>
            """
            
            params = {
                "from": self.sender_email,
                "to": [email],
                "subject": "Your Login OTP for Tally Reports",
                "html": html_content
            }
            
            # Run sync SDK in thread to keep FastAPI non-blocking
            result = await asyncio.to_thread(resend.Emails.send, params)
            logger.info(f"OTP email sent to {email}, ID: {result.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            return False
    
    def is_otp_expired(self, expires_at: datetime) -> bool:
        """Check if OTP has expired"""
        return datetime.now(timezone.utc) > expires_at
    
    def is_session_valid(self, expires_at: datetime) -> bool:
        """Check if session is still valid"""
        return datetime.now(timezone.utc) < expires_at
