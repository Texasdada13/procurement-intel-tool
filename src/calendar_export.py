"""
Calendar export functionality for RFP deadlines.
Generates ICS files for importing into calendar applications.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db


def generate_uid() -> str:
    """Generate a unique identifier for calendar events."""
    return f"{uuid.uuid4()}@procurement-intel"


def escape_ics_text(text: str) -> str:
    """Escape special characters for ICS format."""
    if not text:
        return ""
    text = text.replace('\\', '\\\\')
    text = text.replace('\n', '\\n')
    text = text.replace(',', '\\,')
    text = text.replace(';', '\\;')
    return text


def format_ics_datetime(dt: datetime) -> str:
    """Format datetime for ICS file (UTC format)."""
    return dt.strftime('%Y%m%dT%H%M%SZ')


def format_ics_date(date_str: str) -> str:
    """Format date string for ICS file (all-day event)."""
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%Y%m%d')
    except (ValueError, TypeError):
        return None


def create_rfp_event(rfp: Dict, reminder_hours: int = 24) -> str:
    """Create an ICS event for an RFP deadline."""
    if not rfp.get('due_date'):
        return None

    due_date = format_ics_date(rfp['due_date'])
    if not due_date:
        return None

    uid = generate_uid()
    now = format_ics_datetime(datetime.utcnow())
    title = escape_ics_text(f"RFP Due: {rfp['title'][:80]}")

    description_parts = []
    if rfp.get('entity_name'):
        description_parts.append(f"Agency: {rfp['entity_name']}")
    if rfp.get('solicitation_number'):
        description_parts.append(f"Solicitation: {rfp['solicitation_number']}")
    if rfp.get('category'):
        description_parts.append(f"Category: {rfp['category']}")
    if rfp.get('source_url'):
        description_parts.append(f"URL: {rfp['source_url']}")
    if rfp.get('description'):
        description_parts.append(f"\\n{rfp['description'][:500]}")

    description = escape_ics_text("\\n".join(description_parts))

    location = escape_ics_text(rfp.get('entity_name', ''))

    # Calculate alarm time (default 24 hours before)
    alarm_trigger = f"-PT{reminder_hours}H"

    event = f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
DTSTART;VALUE=DATE:{due_date}
DTEND;VALUE=DATE:{due_date}
SUMMARY:{title}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
CATEGORIES:RFP,Procurement
PRIORITY:5
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:RFP deadline reminder
TRIGGER:{alarm_trigger}
END:VALARM
END:VEVENT"""

    return event


def create_bid_event(bid: Dict) -> str:
    """Create an ICS event for a bid submission."""
    if not bid.get('due_date'):
        return None

    due_date = format_ics_date(bid['due_date'])
    if not due_date:
        return None

    uid = generate_uid()
    now = format_ics_datetime(datetime.utcnow())

    status_text = bid.get('status', 'pending').replace('_', ' ').title()
    title = escape_ics_text(f"[{status_text}] {bid.get('rfp_title', 'Bid')[:60]}")

    description_parts = []
    if bid.get('entity_name'):
        description_parts.append(f"Agency: {bid['entity_name']}")
    if bid.get('solicitation_number'):
        description_parts.append(f"Solicitation: {bid['solicitation_number']}")
    if bid.get('proposal_value'):
        description_parts.append(f"Our Proposal: ${bid['proposal_value']:,.0f}")
    if bid.get('notes'):
        description_parts.append(f"Notes: {bid['notes'][:300]}")

    description = escape_ics_text("\\n".join(description_parts))

    event = f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
DTSTART;VALUE=DATE:{due_date}
DTEND;VALUE=DATE:{due_date}
SUMMARY:{title}
DESCRIPTION:{description}
STATUS:CONFIRMED
CATEGORIES:Bid,Proposal
PRIORITY:3
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Bid deadline reminder
TRIGGER:-PT48H
END:VALARM
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Bid deadline - 24 hours remaining
TRIGGER:-PT24H
END:VALARM
END:VEVENT"""

    return event


def generate_rfp_calendar(rfps: List[Dict], calendar_name: str = "RFP Deadlines") -> str:
    """Generate a complete ICS calendar for RFP deadlines."""
    events = []
    for rfp in rfps:
        event = create_rfp_event(rfp)
        if event:
            events.append(event)

    calendar = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Procurement Intel//RFP Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:{escape_ics_text(calendar_name)}
X-WR-TIMEZONE:America/New_York
{chr(10).join(events)}
END:VCALENDAR"""

    return calendar


def generate_bid_calendar(bids: List[Dict], calendar_name: str = "Bid Deadlines") -> str:
    """Generate a complete ICS calendar for bid deadlines."""
    events = []
    for bid in bids:
        event = create_bid_event(bid)
        if event:
            events.append(event)

    calendar = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Procurement Intel//Bid Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:{escape_ics_text(calendar_name)}
X-WR-TIMEZONE:America/New_York
{chr(10).join(events)}
END:VCALENDAR"""

    return calendar


def export_rfp_deadlines(relevant_only: bool = True,
                          status: str = 'open') -> str:
    """Export all RFP deadlines to ICS format."""
    rfps = db.get_all_rfps(status=status, relevant_only=relevant_only)
    return generate_rfp_calendar(rfps)


def export_bid_deadlines(status: str = None) -> str:
    """Export all bid deadlines to ICS format."""
    bids = db.get_all_bid_responses(status=status)
    return generate_bid_calendar(bids)


def export_single_rfp(rfp_id: int) -> str:
    """Export a single RFP deadline to ICS format."""
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return None
    return generate_rfp_calendar([rfp], f"RFP: {rfp['title'][:50]}")


def save_calendar_file(content: str, filename: str) -> str:
    """Save calendar content to a file."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'calendars')
    os.makedirs(data_dir, exist_ok=True)

    filepath = os.path.join(data_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath


if __name__ == '__main__':
    # Test calendar generation
    print("Generating RFP calendar...")
    rfp_cal = export_rfp_deadlines()
    filepath = save_calendar_file(rfp_cal, 'rfp_deadlines.ics')
    print(f"Saved to: {filepath}")

    print("\nGenerating Bid calendar...")
    bid_cal = export_bid_deadlines()
    filepath = save_calendar_file(bid_cal, 'bid_deadlines.ics')
    print(f"Saved to: {filepath}")
