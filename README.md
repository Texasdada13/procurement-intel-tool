# Procurement Intelligence Tool

A lead generation and market intelligence tool that identifies government entities under public scrutiny for procurement/budgetary issues.

## Purpose

Finds counties, school boards, cities, and other government entities that are:
- Under investigation for procurement violations
- Experiencing public scrutiny over contract awards
- Dealing with audit findings or inspector general reports
- Facing media coverage of budget mismanagement

These entities are prime candidates for contract oversight solutions.

## Features

- **Discovery Engine**: Crawls news sources and public records for procurement scandals
- **Opportunity Dashboard**: Ranked list of leads with heat scores
- **Attack Briefs**: Auto-generated talking points based on each entity's specific issues
- **Status Tracking**: CRM-like pipeline management

## Setup

```bash
pip install -r requirements.txt
python scripts/init_db.py
python web/app.py
```

## Architecture

- `src/` - Core business logic (scrapers, scoring, database)
- `web/` - Flask dashboard application
- `data/` - SQLite database
- `scripts/` - Utility scripts for initialization and data import
