"""Email notification service for Chess Observer."""

import logging
import os
from typing import Optional
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@chess.observer")


@dataclass
class CheaterAlertEmail:
    """Email data for cheater detection alert."""
    recipient: str
    player_name: str
    platform: str
    risk_level: str
    games_analyzed: int
    ensemble_score: int
    summary: str


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        LOGGER.warning("SMTP not configured - email not sent")
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        
        # Plain text version
        msg.attach(MIMEText(body, "plain"))
        
        # HTML version
        html_body = body.replace("\n", "<br>")
        msg.attach(MIMEText(f"<html><body>{html_body}</body></html>", "html"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        
        LOGGER.info(f"Email sent to {to}")
        return True
        
    except Exception as e:
        LOGGER.error(f"Failed to send email: {e}")
        return False


def send_cheater_alert(alert: CheaterAlertEmail) -> bool:
    """Send a cheater detection alert email."""
    subject = f"🚨 Chess Observer Alert: {alert.player_name} flagged as {alert.risk_level}"
    
    body = f"""
Chess Observer Cheater Detection Alert

A player you've faced has been flagged for suspicious behavior:

Player: {alert.player_name}
Platform: {alert.platform}
Risk Level: {alert.risk_level.upper()}
Suspicion Score: {alert.ensemble_score}/100
Games Analyzed: {alert.games_analyzed}

Summary:
{alert.summary}

---
View full report: https://chess.observer/reports
Manage notifications: https://chess.observer/settings

© 2026 Chess Observer
"""
    
    return send_email(alert.recipient, subject, body)


def send_weekly_digest(email: str, stats: dict) -> bool:
    """Send weekly digest email."""
    subject = "📊 Your Chess Observer Weekly Digest"
    
    body = f"""
Chess Observer Weekly Digest

Here's your week in review:

Games Analyzed: {stats.get('games_analyzed', 0)}
Opponents Scanned: {stats.get('opponents_scanned', 0)}
Suspicious Players Found: {stats.get('suspicious_found', 0)}
Usage: {stats.get('usage_pct', 0):.0f}% of monthly limit

{'🎉 Clean week! No confirmed cheaters in your games.' if stats.get('suspicious_found', 0) == 0 else '⚠️ Check your dashboard for details on flagged players.'}

---
View dashboard: https://chess.observer/dashboard

© 2026 Chess Observer
"""
    
    return send_email(email, subject, body)


def send_trial_ending_reminder(email: str, days_left: int) -> bool:
    """Send reminder that trial is ending."""
    subject = f"⏰ Your Chess Observer trial ends in {days_left} day{'s' if days_left != 1 else ''}"
    
    body = f"""
Your Free Trial is Almost Over!

Hi there,

Your Chess Observer free trial ends in {days_left} day{'s' if days_left != 1 else ''}. 

To keep detecting cheaters in your games:
• Unlimited game analysis
• Real-time opponent scanning  
• Detailed cheat reports with AI explanations

Upgrade now: https://chess.observer/pricing

Questions? Reply to this email.

---
© 2026 Chess Observer
"""
    
    return send_email(email, subject, body)
