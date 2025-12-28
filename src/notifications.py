"""
Email Notification Service for Procurement Intelligence Tool.
Sends alerts for new RFPs, deadline reminders, and daily digests.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from jinja2 import Template

from src import database as db

logger = logging.getLogger(__name__)

# Email configuration - uses environment variables for security
EMAIL_CONFIG = {
    'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.environ.get('SMTP_PORT', 587)),
    'sender_email': os.environ.get('SENDER_EMAIL', ''),
    'sender_password': os.environ.get('SENDER_PASSWORD', ''),  # Use App Password for Gmail
    'recipient_email': os.environ.get('RECIPIENT_EMAIL', 'mukhopadhyay.shuva@gmail.com'),
}

# Email templates
NEW_RFPS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #2563eb; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .rfp-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; }
        .rfp-card.urgent { border-left: 4px solid #dc2626; }
        .rfp-card.quick { border-left: 4px solid #f59e0b; }
        .rfp-card.relevant { border-left: 4px solid #10b981; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-right: 5px; }
        .badge-danger { background: #fee2e2; color: #dc2626; }
        .badge-warning { background: #fef3c7; color: #d97706; }
        .badge-success { background: #d1fae5; color: #059669; }
        .badge-info { background: #dbeafe; color: #2563eb; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: #f3f4f6; padding: 15px; border-radius: 8px; text-align: center; flex: 1; }
        .stat-number { font-size: 24px; font-weight: bold; color: #2563eb; }
        .footer { background: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #666; }
        a { color: #2563eb; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
    </div>

    <div class="content">
        {% if stats %}
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{{ stats.new_rfps }}</div>
                <div>New RFPs</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ stats.relevant }}</div>
                <div>Relevant</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ stats.urgent }}</div>
                <div>Urgent</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ stats.quick }}</div>
                <div>Quick Response</div>
            </div>
        </div>
        {% endif %}

        {% if urgent_rfps %}
        <h2 style="color: #dc2626;">Urgent - Due Soon!</h2>
        {% for rfp in urgent_rfps %}
        <div class="rfp-card urgent">
            <h3><a href="{{ rfp.source_url }}">{{ rfp.title }}</a></h3>
            <p>
                <span class="badge badge-danger">Due: {{ rfp.due_date[:10] if rfp.due_date else 'TBD' }}</span>
                {% if rfp.days_until_due is not none %}
                <span class="badge badge-danger">{{ rfp.days_until_due }} days left</span>
                {% endif %}
                <span class="badge badge-info">{{ rfp.entity_name or 'Unknown Agency' }}</span>
                <span class="badge badge-info">{{ rfp.rfp_type or 'RFP' }}</span>
            </p>
            {% if rfp.description %}
            <p>{{ rfp.description[:200] }}...</p>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}

        {% if quick_rfps %}
        <h2 style="color: #f59e0b;">Quick Response Opportunities</h2>
        {% for rfp in quick_rfps %}
        <div class="rfp-card quick">
            <h3><a href="{{ rfp.source_url }}">{{ rfp.title }}</a></h3>
            <p>
                <span class="badge badge-warning">{{ rfp.rfp_type or 'Quote' }}</span>
                <span class="badge badge-warning">~{{ rfp.response_deadline_hours or 72 }}h turnaround</span>
                <span class="badge badge-info">{{ rfp.entity_name or 'Unknown Agency' }}</span>
            </p>
        </div>
        {% endfor %}
        {% endif %}

        {% if relevant_rfps %}
        <h2 style="color: #10b981;">New Relevant RFPs</h2>
        {% for rfp in relevant_rfps %}
        <div class="rfp-card relevant">
            <h3><a href="{{ rfp.source_url }}">{{ rfp.title }}</a></h3>
            <p>
                <span class="badge badge-success">Score: {{ "%.1f"|format(rfp.relevance_score) }}</span>
                <span class="badge badge-info">{{ rfp.category|replace('_', ' ')|title if rfp.category else 'Uncategorized' }}</span>
                <span class="badge badge-info">{{ rfp.entity_name or 'Unknown Agency' }}</span>
                {% if rfp.due_date %}
                <span class="badge badge-info">Due: {{ rfp.due_date[:10] }}</span>
                {% endif %}
            </p>
            {% if rfp.description %}
            <p>{{ rfp.description[:200] }}...</p>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}

        {% if other_rfps %}
        <h2>Other New RFPs</h2>
        <ul>
        {% for rfp in other_rfps[:20] %}
            <li><a href="{{ rfp.source_url }}">{{ rfp.title[:80] }}</a> - {{ rfp.entity_name or 'Unknown' }}</li>
        {% endfor %}
        {% if other_rfps|length > 20 %}
            <li>...and {{ other_rfps|length - 20 }} more</li>
        {% endif %}
        </ul>
        {% endif %}

        <p style="margin-top: 30px;">
            <a href="http://127.0.0.1:5003/rfps" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                View All RFPs in Dashboard
            </a>
        </p>
    </div>

    <div class="footer">
        <p>Procurement Intelligence Tool - Automated Alert</p>
        <p>Generated at {{ generated_at }}</p>
    </div>
</body>
</html>
"""

DEADLINE_REMINDER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #dc2626; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .rfp-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; border-left: 4px solid #dc2626; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-right: 5px; }
        .badge-danger { background: #fee2e2; color: #dc2626; }
        .badge-info { background: #dbeafe; color: #2563eb; }
        .footer { background: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #666; }
        a { color: #2563eb; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Deadline Reminder</h1>
        <p>{{ rfps|length }} RFP(s) due within {{ days }} day(s)</p>
    </div>

    <div class="content">
        {% for rfp in rfps %}
        <div class="rfp-card">
            <h3><a href="{{ rfp.source_url }}">{{ rfp.title }}</a></h3>
            <p>
                <span class="badge badge-danger">Due: {{ rfp.due_date[:10] if rfp.due_date else 'TBD' }}</span>
                {% if rfp.days_until_due == 0 %}
                <span class="badge badge-danger">DUE TODAY!</span>
                {% elif rfp.days_until_due == 1 %}
                <span class="badge badge-danger">Due Tomorrow!</span>
                {% else %}
                <span class="badge badge-danger">{{ rfp.days_until_due }} days left</span>
                {% endif %}
                <span class="badge badge-info">{{ rfp.entity_name or 'Unknown Agency' }}</span>
            </p>
        </div>
        {% endfor %}

        <p style="margin-top: 30px;">
            <a href="http://127.0.0.1:5003/rfps?urgency=urgent" style="background: #dc2626; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                View Urgent RFPs
            </a>
        </p>
    </div>

    <div class="footer">
        <p>Procurement Intelligence Tool - Deadline Reminder</p>
        <p>Generated at {{ generated_at }}</p>
    </div>
</body>
</html>
"""


class NotificationService:
    """Handles email notifications for RFP alerts."""

    def __init__(self, recipient_email: str = None):
        self.config = EMAIL_CONFIG.copy()
        if recipient_email:
            self.config['recipient_email'] = recipient_email

    def send_email(self, subject: str, html_content: str, recipient: str = None) -> bool:
        """Send an HTML email."""
        if not self.config['sender_email'] or not self.config['sender_password']:
            logger.warning("Email not configured. Set SENDER_EMAIL and SENDER_PASSWORD environment variables.")
            logger.info(f"Would send email: {subject}")
            # Save to file for testing
            self._save_email_to_file(subject, html_content)
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config['sender_email']
            msg['To'] = recipient or self.config['recipient_email']

            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['sender_email'], self.config['sender_password'])
                server.send_message(msg)

            logger.info(f"Email sent successfully: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            self._save_email_to_file(subject, html_content)
            return False

    def _save_email_to_file(self, subject: str, html_content: str):
        """Save email to file for testing when SMTP not configured."""
        email_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'emails')
        os.makedirs(email_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{subject[:30].replace(' ', '_')}.html"
        filepath = os.path.join(email_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Email saved to: {filepath}")

    def send_new_rfps_alert(self, rfps: List[Dict], discovery_stats: Dict = None) -> bool:
        """Send alert for newly discovered RFPs."""
        if not rfps:
            logger.info("No new RFPs to notify about")
            return False

        today = datetime.now().date()

        # Calculate days until due for each RFP
        for rfp in rfps:
            if rfp.get('due_date'):
                try:
                    due = datetime.strptime(rfp['due_date'][:10], '%Y-%m-%d').date()
                    rfp['days_until_due'] = (due - today).days
                except (ValueError, TypeError):
                    rfp['days_until_due'] = None
            else:
                rfp['days_until_due'] = None

        # Categorize RFPs
        urgent_rfps = [r for r in rfps if r.get('days_until_due') is not None and 0 <= r['days_until_due'] <= 3]
        quick_rfps = [r for r in rfps if r.get('is_quick_response')]
        relevant_rfps = [r for r in rfps if r.get('is_relevant') and r not in urgent_rfps and r not in quick_rfps]
        other_rfps = [r for r in rfps if r not in urgent_rfps and r not in quick_rfps and r not in relevant_rfps]

        stats = {
            'new_rfps': len(rfps),
            'relevant': len([r for r in rfps if r.get('is_relevant')]),
            'urgent': len(urgent_rfps),
            'quick': len(quick_rfps),
        }

        template = Template(NEW_RFPS_TEMPLATE)
        html_content = template.render(
            title="New RFP Opportunities Found!",
            subtitle=f"Discovery completed at {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            stats=stats,
            urgent_rfps=urgent_rfps[:10],
            quick_rfps=quick_rfps[:10],
            relevant_rfps=relevant_rfps[:15],
            other_rfps=other_rfps,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        subject = f"[Procurement Alert] {len(rfps)} New RFPs Found"
        if urgent_rfps:
            subject = f"[URGENT] {len(urgent_rfps)} RFPs Due Soon + {len(rfps) - len(urgent_rfps)} New"

        return self.send_email(subject, html_content)

    def send_deadline_reminder(self, days: int = 3) -> bool:
        """Send reminder for RFPs due within specified days."""
        today = datetime.now().date()

        # Get open RFPs
        rfps = db.get_all_rfps(status='open')

        upcoming = []
        for rfp in rfps:
            if rfp.get('due_date'):
                try:
                    due = datetime.strptime(rfp['due_date'][:10], '%Y-%m-%d').date()
                    days_until = (due - today).days
                    if 0 <= days_until <= days:
                        rfp['days_until_due'] = days_until
                        upcoming.append(rfp)
                except (ValueError, TypeError):
                    pass

        if not upcoming:
            logger.info(f"No RFPs due within {days} days")
            return False

        # Sort by due date
        upcoming.sort(key=lambda x: x.get('days_until_due', 999))

        template = Template(DEADLINE_REMINDER_TEMPLATE)
        html_content = template.render(
            rfps=upcoming,
            days=days,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        subject = f"[Deadline Reminder] {len(upcoming)} RFPs due within {days} days"
        if any(r.get('days_until_due') == 0 for r in upcoming):
            subject = f"[DUE TODAY] {len([r for r in upcoming if r.get('days_until_due') == 0])} RFP(s) + {len(upcoming)} total due soon"

        return self.send_email(subject, html_content)

    def send_daily_digest(self) -> bool:
        """Send daily digest of RFP activity."""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        # Get all RFPs
        all_rfps = db.get_all_rfps()

        # Filter for recently added (last 24 hours)
        new_rfps = []
        for rfp in all_rfps:
            if rfp.get('created_at'):
                try:
                    created = datetime.strptime(rfp['created_at'][:10], '%Y-%m-%d').date()
                    if created >= yesterday:
                        new_rfps.append(rfp)
                except (ValueError, TypeError):
                    pass

        # Calculate days until due
        for rfp in new_rfps:
            if rfp.get('due_date'):
                try:
                    due = datetime.strptime(rfp['due_date'][:10], '%Y-%m-%d').date()
                    rfp['days_until_due'] = (due - today).days
                except (ValueError, TypeError):
                    rfp['days_until_due'] = None
            else:
                rfp['days_until_due'] = None

        # Get upcoming deadlines
        upcoming_deadlines = []
        for rfp in all_rfps:
            if rfp.get('due_date') and rfp.get('status') == 'open':
                try:
                    due = datetime.strptime(rfp['due_date'][:10], '%Y-%m-%d').date()
                    days_until = (due - today).days
                    if 0 <= days_until <= 7:
                        rfp['days_until_due'] = days_until
                        upcoming_deadlines.append(rfp)
                except (ValueError, TypeError):
                    pass

        upcoming_deadlines.sort(key=lambda x: x.get('days_until_due', 999))

        # Categorize new RFPs
        urgent_rfps = [r for r in new_rfps if r.get('days_until_due') is not None and 0 <= r['days_until_due'] <= 3]
        quick_rfps = [r for r in new_rfps if r.get('is_quick_response')]
        relevant_rfps = [r for r in new_rfps if r.get('is_relevant') and r not in urgent_rfps and r not in quick_rfps]

        stats = {
            'new_rfps': len(new_rfps),
            'relevant': len([r for r in new_rfps if r.get('is_relevant')]),
            'urgent': len(upcoming_deadlines),
            'quick': len(quick_rfps),
        }

        template = Template(NEW_RFPS_TEMPLATE)
        html_content = template.render(
            title="Daily RFP Digest",
            subtitle=f"Summary for {today.strftime('%B %d, %Y')}",
            stats=stats,
            urgent_rfps=upcoming_deadlines[:10],
            quick_rfps=quick_rfps[:10],
            relevant_rfps=relevant_rfps[:15],
            other_rfps=[],
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        subject = f"[Daily Digest] {len(new_rfps)} New RFPs, {len(upcoming_deadlines)} Due This Week"

        return self.send_email(subject, html_content)


def send_discovery_notification(new_rfps: List[Dict], stats: Dict = None) -> bool:
    """Convenience function to send notification after discovery."""
    service = NotificationService()
    return service.send_new_rfps_alert(new_rfps, stats)


def send_deadline_alerts(days: int = 3) -> bool:
    """Convenience function to send deadline reminders."""
    service = NotificationService()
    return service.send_deadline_reminder(days)


def send_daily_digest() -> bool:
    """Convenience function to send daily digest."""
    service = NotificationService()
    return service.send_daily_digest()


if __name__ == '__main__':
    # Test notifications
    logging.basicConfig(level=logging.INFO)

    # Test daily digest
    print("Sending test daily digest...")
    send_daily_digest()

    # Test deadline reminder
    print("Sending test deadline reminder...")
    send_deadline_alerts(days=7)
