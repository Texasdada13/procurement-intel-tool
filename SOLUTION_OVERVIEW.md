# Procurement Intelligence Tool
## Solution Overview

---

## Executive Summary

The Procurement Intelligence Tool is a comprehensive web-based platform designed to automate the discovery, tracking, and management of government RFP (Request for Proposal) opportunities. Built specifically for consulting firms targeting Florida government contracts, the system streamlines the entire procurement lifecycle from opportunity identification to bid submission and competitive analysis.

**Access URL:** http://localhost:5003

---

## Key Features

### 1. Automated RFP Discovery

**What it does:**
- Continuously monitors 15+ Florida government procurement portals
- Scrapes RFP listings from sources including SAM.gov, Florida VBS, DemandStar, and county-specific portals
- Handles both static HTML pages and JavaScript-rendered sites using Playwright browser automation

**Benefits:**
- Eliminates hours of manual searching across multiple websites
- Never miss an opportunity due to oversight
- Covers state, county, and municipal procurement sources

**Supported Sources:**
| Portal | Type | Coverage |
|--------|------|----------|
| SAM.gov | Federal | National opportunities |
| Florida VBS | State | All state agencies |
| MyFloridaMarketPlace | State | State contracts |
| DemandStar | Aggregator | Multi-jurisdictional |
| BidNet Direct | Aggregator | Government-wide |
| County Portals | Local | Miami-Dade, Broward, Palm Beach, etc. |

---

### 2. AI-Powered Relevance Scoring

**What it does:**
- Automatically scores each RFP on a 0-100 relevance scale
- Uses keyword matching with TF-IDF weighting
- Optional semantic similarity analysis (sentence-transformers)
- Optional GPT integration for natural language analysis

**Scoring Categories:**
- **High Value (70-100):** IT consulting, digital transformation, cybersecurity assessments
- **Medium Value (40-69):** General consulting, technology projects, studies
- **Low Value (0-39):** Construction, physical services, commodities

**Benefits:**
- Focus on opportunities that match your expertise
- Reduce noise from irrelevant RFPs
- Automatic categorization (IT Consulting, Cybersecurity, Software, Cloud, Data, Professional Services)

---

### 3. Bid Response Tracker

**What it does:**
- Track bid submissions through their entire lifecycle
- Record proposal values, submission dates, and outcomes
- Capture win/loss data and lessons learned

**Bid Statuses:**
| Status | Description |
|--------|-------------|
| Reviewing | Evaluating the opportunity |
| Pursuing | Actively preparing response |
| Submitted | Proposal sent |
| Won | Contract awarded to us |
| Lost | Contract awarded to competitor |
| No Bid | Decision not to pursue |

**Benefits:**
- Centralized view of all active bids
- Win rate analytics and performance tracking
- Historical data for strategic planning

---

### 4. Competitor Intelligence

**What it does:**
- Maintain profiles of competing firms
- Track competitor wins with contract values
- Record competitor strengths and weaknesses (SWOT)

**Tracked Metrics:**
- Win count and win rate
- Total contract value won
- Average bid margin differential
- Common agencies where they compete

**Benefits:**
- Understand competitive landscape
- Identify pricing patterns
- Develop counter-strategies for specific competitors

---

### 5. Email Notifications & Alerts

**What it does:**
- Sends alerts for new high-relevance RFPs
- Daily digest emails with opportunity summary
- Deadline reminders (7-day, 3-day, 1-day warnings)

**Notification Types:**
| Type | Frequency | Content |
|------|-----------|---------|
| New RFP Alert | Real-time | High-relevance opportunities |
| Daily Digest | Daily (8 AM) | Summary of all new RFPs |
| Deadline Alert | As needed | Upcoming due dates |

**Benefits:**
- Never miss critical deadlines
- Stay informed without constant monitoring
- Configurable alert preferences

---

### 6. Automated Scheduling

**What it does:**
- Runs discovery scans on configurable intervals
- Automatic deadline checking and alerting
- Background processing that doesn't interrupt workflow

**Default Schedule:**
- Discovery: Every 6 hours
- Deadline Check: Daily at 7 AM
- Daily Digest: Daily at 8 AM

**Benefits:**
- Set-and-forget automation
- Consistent monitoring coverage
- Reduced manual effort

---

### 7. Calendar Integration

**What it does:**
- Export RFP deadlines to ICS calendar format
- Compatible with Outlook, Google Calendar, Apple Calendar
- Individual or bulk export options

**Export Options:**
- All open RFP deadlines
- Bid submission deadlines
- Single RFP deadline

**Benefits:**
- Integrate deadlines into existing workflow
- Automatic reminders through calendar apps
- Team-wide visibility via shared calendars

---

### 8. Document Auto-Download

**What it does:**
- Automatically downloads RFP attachments and specifications
- Organizes documents by RFP in dedicated folders
- Supports PDF, DOC, DOCX, XLS, XLSX, ZIP formats

**Features:**
- Automatic filename detection
- Duplicate prevention
- File size limits (50MB max)
- MD5 checksums for integrity

**Benefits:**
- All documents in one place
- No manual downloading required
- Organized folder structure

---

### 9. Response Templates

**What it does:**
- Store reusable proposal content
- Categorize templates by type
- Track template usage

**Template Categories:**
- Executive Summary
- Company Overview
- Technical Approach
- Past Performance
- Pricing Sections

**Benefits:**
- Faster proposal preparation
- Consistent messaging
- Best practices preservation

---

### 10. Analytics Dashboard

**What it does:**
- Visual overview of opportunity pipeline
- Bid performance charts
- Trend analysis

**Dashboard Metrics:**
| Metric | Description |
|--------|-------------|
| Total RFPs | All discovered opportunities |
| Open RFPs | Currently active opportunities |
| High Relevance | Score 70+ opportunities |
| Due This Week | Urgent deadlines |
| Win Rate | Percentage of bids won |
| Pipeline Value | Total value of active bids |

**Visualizations:**
- RFP status distribution (doughnut chart)
- Bid outcomes by status (bar chart)
- Category breakdown (pie chart)

---

## Technical Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    Web Interface                         │
│                 (Flask + Bootstrap 5)                    │
│                   Port 5003                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Discovery   │  │   Scoring    │  │ Notifications│  │
│  │   Engine     │  │   Engine     │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Browser     │  │  Document    │  │   Calendar   │  │
│  │  Scraper     │  │  Downloader  │  │   Export     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                   SQLite Database                        │
│                  (data/rfp_intel.db)                     │
└─────────────────────────────────────────────────────────┘
```

### Database Tables

| Table | Purpose |
|-------|---------|
| rfps | RFP opportunities |
| bid_responses | Bid tracking |
| competitors | Competitor profiles |
| competitor_wins | Win history |
| response_templates | Proposal templates |
| opportunities | Market intelligence |
| sources | Procurement portals |
| keywords | Search terms |

### Technology Stack

- **Backend:** Python 3.x, Flask
- **Frontend:** Bootstrap 5, Chart.js
- **Database:** SQLite
- **Scraping:** Requests, BeautifulSoup, Playwright
- **Email:** SMTP (Gmail compatible)
- **AI/ML:** Optional sentence-transformers, OpenAI

---

## Installation & Setup

### Prerequisites

```bash
# Required
pip install flask requests beautifulsoup4

# Optional - for browser scraping
pip install playwright
playwright install chromium

# Optional - for AI scoring
pip install sentence-transformers
pip install openai
```

### Environment Variables

```bash
# Email notifications
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAIL=mukhopadhyay.shuva@gmail.com

# Optional AI features
OPENAI_API_KEY=your-openai-key
```

### Running the Application

```bash
cd procurement-intel-tool
python web/app.py
```

Access at: **http://localhost:5003**

---

## User Guide

### Quick Start

1. **Dashboard** - View overview and urgent items
2. **RFPs** - Browse and filter opportunities
3. **Run Discovery** - Manually trigger new RFP search
4. **Track Bids** - Create bid responses for opportunities
5. **Settings** - Configure scheduler and notifications

### Navigation

| Menu Item | Function |
|-----------|----------|
| Dashboard | Overview and analytics |
| Opportunities | Market intelligence |
| RFPs | Government opportunities |
| Bidding > Bid Tracker | Active bids |
| Bidding > Competitors | Competitor profiles |
| Bidding > Templates | Response templates |
| Settings | Configuration |

### Key Workflows

**Discovering New RFPs:**
1. Go to Settings
2. Click "Run Discovery Now" or enable scheduler
3. View new RFPs on dashboard or RFPs page

**Tracking a Bid:**
1. Find RFP on RFPs page
2. Click "Start Bid" button
3. Update status as bid progresses
4. Record outcome and lessons learned

**Adding a Competitor:**
1. Go to Bidding > Competitors
2. Click "Add Competitor"
3. Enter company details and notes
4. Track their wins when you lose bids

---

## Benefits Summary

| Benefit | Impact |
|---------|--------|
| **Time Savings** | 10+ hours/week on manual searching |
| **No Missed Opportunities** | Automated monitoring 24/7 |
| **Better Targeting** | AI scoring focuses effort on best fits |
| **Competitive Edge** | Systematic competitor tracking |
| **Faster Responses** | Templates and organized documents |
| **Deadline Management** | Automated alerts prevent late submissions |
| **Data-Driven Strategy** | Analytics reveal patterns and trends |

---

## Future Enhancements

Potential additions for future versions:

- [ ] Multi-user support with role-based access
- [ ] Integration with CRM systems (Salesforce, HubSpot)
- [ ] Automated proposal generation with AI
- [ ] Mobile app for on-the-go access
- [ ] API for third-party integrations
- [ ] Advanced analytics and forecasting
- [ ] Document OCR and content extraction
- [ ] Slack/Teams notifications

---

## Support

For issues or questions:
- GitHub: https://github.com/anthropics/claude-code/issues
- Email: mukhopadhyay.shuva@gmail.com

---

*Document generated for Procurement Intelligence Tool v1.0*
*Last updated: December 2024*
