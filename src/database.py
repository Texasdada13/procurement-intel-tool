"""
Database module for Procurement Intelligence Tool.
Handles all database operations for opportunities, entities, sources, and articles.
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'intel.db')


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database with all required tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    # Government entities table (counties, school boards, cities, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,  -- county, school_board, city, utility, etc.
            state TEXT NOT NULL,
            county TEXT,
            population INTEGER,
            annual_budget REAL,
            website TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, entity_type, state)
        )
    ''')

    # News/data sources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,  -- news, rss, audit_portal, ethics_commission, etc.
            url TEXT NOT NULL,
            state TEXT,  -- NULL means national
            scrape_frequency TEXT DEFAULT 'daily',  -- hourly, daily, weekly
            last_scraped TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Articles/reports found
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            content TEXT,
            summary TEXT,
            published_date TIMESTAMP,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    ''')

    # Keywords for matching
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,  -- procurement, audit, ethics, budget, legal
            weight REAL DEFAULT 1.0,  -- importance multiplier for scoring
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Matches between articles and keywords
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS article_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            keyword_id INTEGER NOT NULL,
            match_count INTEGER DEFAULT 1,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (keyword_id) REFERENCES keywords(id),
            UNIQUE(article_id, keyword_id)
        )
    ''')

    # Opportunities (the main lead tracking table)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            heat_score REAL DEFAULT 0,  -- 0-100 score based on severity/recency
            status TEXT DEFAULT 'new',  -- new, researching, contacted, in_discussion, closed_won, closed_lost
            priority TEXT DEFAULT 'medium',  -- low, medium, high, urgent
            issue_type TEXT,  -- procurement_violation, audit_finding, ethics_complaint, budget_crisis, etc.
            first_detected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            attack_brief TEXT,  -- auto-generated talking points
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        )
    ''')

    # Link opportunities to articles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opportunity_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            relevance_score REAL DEFAULT 1.0,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id),
            FOREIGN KEY (article_id) REFERENCES articles(id),
            UNIQUE(opportunity_id, article_id)
        )
    ''')

    # Key people involved (board members, administrators, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            role TEXT,  -- decision_maker, involved_party, whistleblower, etc.
            email TEXT,
            phone TEXT,
            linkedin TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        )
    ''')

    # Activity log for opportunities
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,  -- status_change, note_added, article_linked, contact_made, etc.
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
        )
    ''')

    # RFP/RFQ opportunities table (proactive solicitations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rfps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            solicitation_number TEXT,
            rfp_type TEXT,  -- RFP, RFQ, ITB, ITN, etc.
            category TEXT,  -- IT, consulting, construction, professional_services, etc.
            status TEXT DEFAULT 'open',  -- open, closed, awarded, cancelled
            posted_date TIMESTAMP,
            due_date TIMESTAMP,
            estimated_value REAL,
            source_url TEXT,
            source_portal TEXT,  -- vendorlink, demandstar, bonfire, county_site, etc.
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            attachments_url TEXT,
            is_relevant INTEGER DEFAULT 0,  -- 1 if matches IT/consulting keywords
            relevance_score REAL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(solicitation_number, source_portal),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        )
    ''')

    # RFP categories/keywords for matching
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rfp_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,  -- it_consulting, software, assessment, study, modernization, etc.
            weight REAL DEFAULT 1.0,
            is_active INTEGER DEFAULT 1
        )
    ''')

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def seed_keywords():
    """Seed the database with initial keywords for matching."""
    keywords = [
        # Procurement violations
        ('bid rigging', 'procurement', 2.0),
        ('bid manipulation', 'procurement', 2.0),
        ('procurement violation', 'procurement', 1.8),
        ('cone of silence', 'procurement', 1.5),
        ('no-bid contract', 'procurement', 1.3),
        ('sole source', 'procurement', 1.0),
        ('contract steering', 'procurement', 2.0),
        ('vendor favoritism', 'procurement', 1.8),
        ('kickback', 'procurement', 2.5),
        ('collusion', 'procurement', 2.5),
        ('rigged bid', 'procurement', 2.0),
        ('procurement fraud', 'procurement', 2.5),

        # Audit findings
        ('audit finding', 'audit', 1.5),
        ('audit report', 'audit', 1.0),
        ('inspector general', 'audit', 1.8),
        ('internal investigation', 'audit', 1.5),
        ('financial irregularities', 'audit', 1.8),
        ('misspending', 'audit', 1.5),
        ('misappropriation', 'audit', 2.0),
        ('unaccounted funds', 'audit', 1.8),
        ('missing funds', 'audit', 2.0),
        ('forensic audit', 'audit', 2.0),

        # Ethics issues
        ('ethics violation', 'ethics', 1.8),
        ('ethics complaint', 'ethics', 1.5),
        ('conflict of interest', 'ethics', 1.5),
        ('self-dealing', 'ethics', 2.0),
        ('nepotism', 'ethics', 1.5),
        ('corruption', 'ethics', 2.5),
        ('bribery', 'ethics', 2.5),
        ('misconduct', 'ethics', 1.5),
        ('malfeasance', 'ethics', 2.0),

        # Budget problems
        ('budget crisis', 'budget', 1.5),
        ('budget shortfall', 'budget', 1.3),
        ('cost overrun', 'budget', 1.5),
        ('over budget', 'budget', 1.3),
        ('budget deficit', 'budget', 1.3),
        ('fiscal mismanagement', 'budget', 1.8),
        ('taxpayer waste', 'budget', 1.5),
        ('wasteful spending', 'budget', 1.5),

        # Legal/investigation
        ('grand jury', 'legal', 2.0),
        ('FBI investigation', 'legal', 2.5),
        ('federal investigation', 'legal', 2.5),
        ('FDLE investigation', 'legal', 2.0),
        ('criminal investigation', 'legal', 2.5),
        ('indictment', 'legal', 2.5),
        ('arrested', 'legal', 2.0),
        ('charged with', 'legal', 2.0),
        ('lawsuit', 'legal', 1.3),
        ('whistleblower', 'legal', 1.8),

        # Construction/contracts specific
        ('change order', 'procurement', 1.2),
        ('construction fraud', 'procurement', 2.0),
        ('construction bid', 'procurement', 1.0),
        ('contract award', 'procurement', 0.8),
        ('RFP violation', 'procurement', 1.5),
        ('vendor protest', 'procurement', 1.3),
    ]

    conn = get_connection()
    cursor = conn.cursor()

    for keyword, category, weight in keywords:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO keywords (keyword, category, weight)
                VALUES (?, ?, ?)
            ''', (keyword, category, weight))
        except sqlite3.Error as e:
            logger.error(f"Error inserting keyword {keyword}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Seeded {len(keywords)} keywords")


def seed_sources():
    """Seed initial news sources for Florida."""
    sources = [
        # Florida news sources
        ('Ocala Gazette', 'news', 'https://www.ocalagazette.com/', 'FL'),
        ('Ocala Star Banner', 'news', 'https://www.ocala.com/', 'FL'),
        ('Tampa Bay Times', 'news', 'https://www.tampabay.com/', 'FL'),
        ('Orlando Sentinel', 'news', 'https://www.orlandosentinel.com/', 'FL'),
        ('Miami Herald', 'news', 'https://www.miamiherald.com/', 'FL'),
        ('Sun Sentinel', 'news', 'https://www.sun-sentinel.com/', 'FL'),
        ('Jacksonville Times-Union', 'news', 'https://www.jacksonville.com/', 'FL'),
        ('Gainesville Sun', 'news', 'https://www.gainesville.com/', 'FL'),
        ('Sarasota Herald-Tribune', 'news', 'https://www.heraldtribune.com/', 'FL'),
        ('Palm Beach Post', 'news', 'https://www.palmbeachpost.com/', 'FL'),
        ('News-Press (Fort Myers)', 'news', 'https://www.news-press.com/', 'FL'),
        ('Pensacola News Journal', 'news', 'https://www.pnj.com/', 'FL'),
        ('Florida Politics', 'news', 'https://floridapolitics.com/', 'FL'),
        ('Florida Phoenix', 'news', 'https://floridaphoenix.com/', 'FL'),

        # Official sources
        ('FL Auditor General', 'audit_portal', 'https://flauditor.gov/', 'FL'),
        ('FL Ethics Commission', 'ethics_commission', 'https://ethics.state.fl.us/', 'FL'),
        ('FL Inspector General', 'audit_portal', 'https://www.floridaoig.com/', 'FL'),

        # National sources that cover local government
        ('Government Technology', 'news', 'https://www.govtech.com/', None),
        ('Governing Magazine', 'news', 'https://www.governing.com/', None),
    ]

    conn = get_connection()
    cursor = conn.cursor()

    for name, source_type, url, state in sources:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO sources (name, source_type, url, state)
                VALUES (?, ?, ?, ?)
            ''', (name, source_type, url, state))
        except sqlite3.Error as e:
            logger.error(f"Error inserting source {name}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Seeded {len(sources)} sources")


# ============== Entity Operations ==============

def create_entity(name: str, entity_type: str, state: str, **kwargs) -> int:
    """Create a new entity and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO entities (name, entity_type, state, county, population, annual_budget, website)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, entity_type, state, kwargs.get('county'), kwargs.get('population'),
          kwargs.get('annual_budget'), kwargs.get('website')))

    conn.commit()
    entity_id = cursor.lastrowid

    # If INSERT OR IGNORE didn't insert (duplicate), fetch the existing ID
    if entity_id == 0:
        cursor.execute('SELECT id FROM entities WHERE name = ? AND entity_type = ? AND state = ?',
                      (name, entity_type, state))
        row = cursor.fetchone()
        entity_id = row['id'] if row else None

    conn.close()
    return entity_id


def get_entity(entity_id: int) -> Optional[Dict]:
    """Get entity by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM entities WHERE id = ?', (entity_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_entity_by_name(name: str, entity_type: str, state: str) -> Optional[Dict]:
    """Get entity by name, type, and state."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM entities WHERE name = ? AND entity_type = ? AND state = ?',
                  (name, entity_type, state))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_entities() -> List[Dict]:
    """Get all entities."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM entities ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== Opportunity Operations ==============

def create_opportunity(entity_id: int, title: str, **kwargs) -> int:
    """Create a new opportunity and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO opportunities (entity_id, title, summary, heat_score, status, priority, issue_type, attack_brief)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (entity_id, title, kwargs.get('summary'), kwargs.get('heat_score', 0),
          kwargs.get('status', 'new'), kwargs.get('priority', 'medium'),
          kwargs.get('issue_type'), kwargs.get('attack_brief')))

    conn.commit()
    opportunity_id = cursor.lastrowid
    conn.close()

    return opportunity_id


def get_opportunity(opportunity_id: int) -> Optional[Dict]:
    """Get opportunity by ID with entity info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.*, e.name as entity_name, e.entity_type, e.state, e.county
        FROM opportunities o
        JOIN entities e ON o.entity_id = e.id
        WHERE o.id = ?
    ''', (opportunity_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_opportunities(status: str = None, min_heat_score: float = None) -> List[Dict]:
    """Get all opportunities with optional filtering."""
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT o.*, e.name as entity_name, e.entity_type, e.state, e.county
        FROM opportunities o
        JOIN entities e ON o.entity_id = e.id
        WHERE 1=1
    '''
    params = []

    if status:
        query += ' AND o.status = ?'
        params.append(status)

    if min_heat_score is not None:
        query += ' AND o.heat_score >= ?'
        params.append(min_heat_score)

    query += ' ORDER BY o.heat_score DESC, o.last_activity DESC'

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_opportunity(opportunity_id: int, **kwargs) -> bool:
    """Update an opportunity."""
    conn = get_connection()
    cursor = conn.cursor()

    valid_fields = ['title', 'summary', 'heat_score', 'status', 'priority', 'issue_type', 'notes', 'attack_brief']
    updates = []
    params = []

    for field in valid_fields:
        if field in kwargs:
            updates.append(f'{field} = ?')
            params.append(kwargs[field])

    if not updates:
        return False

    updates.append('last_activity = CURRENT_TIMESTAMP')
    params.append(opportunity_id)

    query = f'UPDATE opportunities SET {", ".join(updates)} WHERE id = ?'
    cursor.execute(query, params)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def add_activity_log(opportunity_id: int, activity_type: str, description: str):
    """Add an activity log entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO activity_log (opportunity_id, activity_type, description)
        VALUES (?, ?, ?)
    ''', (opportunity_id, activity_type, description))
    conn.commit()
    conn.close()


def get_opportunity_activities(opportunity_id: int) -> List[Dict]:
    """Get activity log for an opportunity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM activity_log WHERE opportunity_id = ? ORDER BY created_at DESC
    ''', (opportunity_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== Article Operations ==============

def create_article(url: str, title: str, source_id: int = None, **kwargs) -> int:
    """Create a new article and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO articles (source_id, url, title, content, summary, published_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (source_id, url, title, kwargs.get('content'), kwargs.get('summary'),
              kwargs.get('published_date')))
        conn.commit()
        article_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Article already exists
        cursor.execute('SELECT id FROM articles WHERE url = ?', (url,))
        row = cursor.fetchone()
        article_id = row['id'] if row else None

    conn.close()
    return article_id


def get_article(article_id: int) -> Optional[Dict]:
    """Get article by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.name as source_name
        FROM articles a
        LEFT JOIN sources s ON a.source_id = s.id
        WHERE a.id = ?
    ''', (article_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def link_article_to_opportunity(article_id: int, opportunity_id: int, relevance_score: float = 1.0):
    """Link an article to an opportunity."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO opportunity_articles (opportunity_id, article_id, relevance_score)
            VALUES (?, ?, ?)
        ''', (opportunity_id, article_id, relevance_score))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error linking article {article_id} to opportunity {opportunity_id}: {e}")
    conn.close()


def get_opportunity_articles(opportunity_id: int) -> List[Dict]:
    """Get all articles linked to an opportunity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.name as source_name, oa.relevance_score
        FROM articles a
        LEFT JOIN sources s ON a.source_id = s.id
        JOIN opportunity_articles oa ON a.id = oa.article_id
        WHERE oa.opportunity_id = ?
        ORDER BY a.published_date DESC
    ''', (opportunity_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== Keywords Operations ==============

def get_all_keywords() -> List[Dict]:
    """Get all active keywords."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM keywords WHERE is_active = 1 ORDER BY weight DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_keyword_match(article_id: int, keyword_id: int, match_count: int = 1):
    """Record a keyword match for an article."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO article_keywords (article_id, keyword_id, match_count)
            VALUES (?, ?, ?)
        ''', (article_id, keyword_id, match_count))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error adding keyword match: {e}")
    conn.close()


# ============== Source Operations ==============

def get_all_sources(active_only: bool = True) -> List[Dict]:
    """Get all sources."""
    conn = get_connection()
    cursor = conn.cursor()
    query = 'SELECT * FROM sources'
    if active_only:
        query += ' WHERE is_active = 1'
    query += ' ORDER BY name'
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_source_last_scraped(source_id: int):
    """Update the last_scraped timestamp for a source."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE sources SET last_scraped = CURRENT_TIMESTAMP WHERE id = ?', (source_id,))
    conn.commit()
    conn.close()


# ============== Contact Operations ==============

def create_contact(entity_id: int, name: str, **kwargs) -> int:
    """Create a new contact."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO contacts (entity_id, name, title, role, email, phone, linkedin, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (entity_id, name, kwargs.get('title'), kwargs.get('role'),
          kwargs.get('email'), kwargs.get('phone'), kwargs.get('linkedin'),
          kwargs.get('notes')))

    conn.commit()
    contact_id = cursor.lastrowid
    conn.close()
    return contact_id


def get_entity_contacts(entity_id: int) -> List[Dict]:
    """Get all contacts for an entity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contacts WHERE entity_id = ? ORDER BY name', (entity_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============== Dashboard Stats ==============

def get_dashboard_stats() -> Dict:
    """Get summary statistics for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Total opportunities by status
    cursor.execute('''
        SELECT status, COUNT(*) as count FROM opportunities GROUP BY status
    ''')
    stats['opportunities_by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}

    # Total opportunities
    cursor.execute('SELECT COUNT(*) as count FROM opportunities')
    stats['total_opportunities'] = cursor.fetchone()['count']

    # High heat opportunities (score >= 70)
    cursor.execute('SELECT COUNT(*) as count FROM opportunities WHERE heat_score >= 70')
    stats['high_heat_count'] = cursor.fetchone()['count']

    # New opportunities (last 7 days)
    cursor.execute('''
        SELECT COUNT(*) as count FROM opportunities
        WHERE first_detected >= datetime('now', '-7 days')
    ''')
    stats['new_this_week'] = cursor.fetchone()['count']

    # Total entities tracked
    cursor.execute('SELECT COUNT(*) as count FROM entities')
    stats['total_entities'] = cursor.fetchone()['count']

    # Total articles
    cursor.execute('SELECT COUNT(*) as count FROM articles')
    stats['total_articles'] = cursor.fetchone()['count']

    # Opportunities by type
    cursor.execute('''
        SELECT issue_type, COUNT(*) as count FROM opportunities
        WHERE issue_type IS NOT NULL GROUP BY issue_type
    ''')
    stats['opportunities_by_type'] = {row['issue_type']: row['count'] for row in cursor.fetchall()}

    conn.close()
    return stats


def seed_rfp_keywords():
    """Seed RFP keywords for IT consulting opportunities."""
    keywords = [
        # IT Consulting & Assessment
        ('application rationalization', 'it_consulting', 3.0),
        ('IT assessment', 'it_consulting', 2.5),
        ('technology assessment', 'it_consulting', 2.5),
        ('IT consulting', 'it_consulting', 2.0),
        ('IT strategic plan', 'it_consulting', 2.5),
        ('IT modernization', 'it_consulting', 2.5),
        ('digital transformation', 'it_consulting', 2.5),
        ('systems assessment', 'it_consulting', 2.0),
        ('infrastructure assessment', 'it_consulting', 2.0),
        ('network assessment', 'it_consulting', 2.0),
        ('cybersecurity assessment', 'it_consulting', 2.5),
        ('security audit', 'it_consulting', 2.0),
        ('penetration testing', 'it_consulting', 2.0),
        ('IT audit', 'it_consulting', 2.0),
        ('technology roadmap', 'it_consulting', 2.5),
        ('enterprise architecture', 'it_consulting', 2.5),
        ('cloud migration', 'it_consulting', 2.0),
        ('cloud assessment', 'it_consulting', 2.0),
        ('data center', 'it_consulting', 1.5),

        # Software & Systems
        ('software implementation', 'software', 2.0),
        ('ERP implementation', 'software', 2.5),
        ('ERP assessment', 'software', 2.5),
        ('financial system', 'software', 2.0),
        ('HRIS', 'software', 1.5),
        ('human resources system', 'software', 1.5),
        ('permitting software', 'software', 2.0),
        ('utility billing', 'software', 1.5),
        ('asset management system', 'software', 2.0),
        ('work order system', 'software', 1.5),
        ('GIS', 'software', 1.5),
        ('document management', 'software', 1.5),
        ('records management', 'software', 1.5),

        # Studies & Analysis
        ('feasibility study', 'study', 2.5),
        ('feasibility assessment', 'study', 2.5),
        ('needs assessment', 'study', 2.0),
        ('gap analysis', 'study', 2.0),
        ('business process', 'study', 2.0),
        ('process improvement', 'study', 2.0),
        ('workflow analysis', 'study', 2.0),
        ('cost benefit analysis', 'study', 2.0),
        ('return on investment', 'study', 1.5),
        ('benchmark', 'study', 1.5),
        ('best practices', 'study', 1.5),

        # Professional Services
        ('management consulting', 'professional_services', 2.0),
        ('organizational assessment', 'professional_services', 2.0),
        ('staffing study', 'professional_services', 2.0),
        ('performance audit', 'professional_services', 2.0),
        ('operational review', 'professional_services', 2.0),
        ('efficiency study', 'professional_services', 2.0),
        ('strategic planning', 'professional_services', 2.0),
        ('master plan', 'professional_services', 1.5),
        ('comprehensive plan', 'professional_services', 1.5),

        # Data & Analytics
        ('data analytics', 'data', 2.0),
        ('business intelligence', 'data', 2.0),
        ('dashboard', 'data', 1.5),
        ('reporting system', 'data', 1.5),
        ('data warehouse', 'data', 2.0),
        ('data governance', 'data', 2.0),
        ('data migration', 'data', 2.0),
    ]

    conn = get_connection()
    cursor = conn.cursor()

    for keyword, category, weight in keywords:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO rfp_keywords (keyword, category, weight)
                VALUES (?, ?, ?)
            ''', (keyword, category, weight))
        except sqlite3.Error as e:
            logger.error(f"Error inserting RFP keyword {keyword}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Seeded {len(keywords)} RFP keywords")


# ============== RFP Operations ==============

def create_rfp(title: str, **kwargs) -> int:
    """Create a new RFP and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO rfps (entity_id, title, description, solicitation_number, rfp_type,
                            category, status, posted_date, due_date, estimated_value,
                            source_url, source_portal, contact_name, contact_email,
                            contact_phone, attachments_url, is_relevant, relevance_score, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (kwargs.get('entity_id'), title, kwargs.get('description'),
              kwargs.get('solicitation_number'), kwargs.get('rfp_type'),
              kwargs.get('category'), kwargs.get('status', 'open'),
              kwargs.get('posted_date'), kwargs.get('due_date'),
              kwargs.get('estimated_value'), kwargs.get('source_url'),
              kwargs.get('source_portal'), kwargs.get('contact_name'),
              kwargs.get('contact_email'), kwargs.get('contact_phone'),
              kwargs.get('attachments_url'), kwargs.get('is_relevant', 0),
              kwargs.get('relevance_score', 0), kwargs.get('notes')))
        conn.commit()
        rfp_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # RFP already exists
        cursor.execute('SELECT id FROM rfps WHERE solicitation_number = ? AND source_portal = ?',
                      (kwargs.get('solicitation_number'), kwargs.get('source_portal')))
        row = cursor.fetchone()
        rfp_id = row['id'] if row else None

    conn.close()
    return rfp_id


def get_rfp(rfp_id: int) -> Optional[Dict]:
    """Get RFP by ID with entity info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, e.name as entity_name, e.entity_type, e.state
        FROM rfps r
        LEFT JOIN entities e ON r.entity_id = e.id
        WHERE r.id = ?
    ''', (rfp_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_rfps(status: str = None, relevant_only: bool = False, category: str = None) -> List[Dict]:
    """Get all RFPs with optional filtering."""
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT r.*, e.name as entity_name, e.entity_type, e.state
        FROM rfps r
        LEFT JOIN entities e ON r.entity_id = e.id
        WHERE 1=1
    '''
    params = []

    if status:
        query += ' AND r.status = ?'
        params.append(status)

    if relevant_only:
        query += ' AND r.is_relevant = 1'

    if category:
        query += ' AND r.category = ?'
        params.append(category)

    query += ' ORDER BY r.due_date ASC, r.relevance_score DESC'

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_open_rfps(relevant_only: bool = True) -> List[Dict]:
    """Get all open RFPs, optionally filtered to relevant ones."""
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT r.*, e.name as entity_name, e.entity_type, e.state
        FROM rfps r
        LEFT JOIN entities e ON r.entity_id = e.id
        WHERE r.status = 'open'
        AND (r.due_date IS NULL OR r.due_date >= datetime('now'))
    '''

    if relevant_only:
        query += ' AND r.is_relevant = 1'

    query += ' ORDER BY r.due_date ASC, r.relevance_score DESC'

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_rfp(rfp_id: int, **kwargs) -> bool:
    """Update an RFP."""
    conn = get_connection()
    cursor = conn.cursor()

    valid_fields = ['title', 'description', 'status', 'category', 'due_date',
                   'is_relevant', 'relevance_score', 'notes']
    updates = []
    params = []

    for field in valid_fields:
        if field in kwargs:
            updates.append(f'{field} = ?')
            params.append(kwargs[field])

    if not updates:
        return False

    updates.append('updated_at = CURRENT_TIMESTAMP')
    params.append(rfp_id)

    query = f'UPDATE rfps SET {", ".join(updates)} WHERE id = ?'
    cursor.execute(query, params)
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def get_rfp_keywords() -> List[Dict]:
    """Get all active RFP keywords."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM rfp_keywords WHERE is_active = 1 ORDER BY weight DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_rfp_stats() -> Dict:
    """Get RFP statistics for dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Total RFPs
    cursor.execute('SELECT COUNT(*) as count FROM rfps')
    stats['total_rfps'] = cursor.fetchone()['count']

    # Open RFPs
    cursor.execute("SELECT COUNT(*) as count FROM rfps WHERE status = 'open'")
    stats['open_rfps'] = cursor.fetchone()['count']

    # Relevant RFPs (IT/consulting)
    cursor.execute('SELECT COUNT(*) as count FROM rfps WHERE is_relevant = 1')
    stats['relevant_rfps'] = cursor.fetchone()['count']

    # Closing soon (within 7 days)
    cursor.execute('''
        SELECT COUNT(*) as count FROM rfps
        WHERE status = 'open' AND due_date BETWEEN datetime('now') AND datetime('now', '+7 days')
    ''')
    stats['closing_soon'] = cursor.fetchone()['count']

    # By category
    cursor.execute('''
        SELECT category, COUNT(*) as count FROM rfps
        WHERE category IS NOT NULL AND is_relevant = 1
        GROUP BY category ORDER BY count DESC
    ''')
    stats['by_category'] = {row['category']: row['count'] for row in cursor.fetchall()}

    # By source portal
    cursor.execute('''
        SELECT source_portal, COUNT(*) as count FROM rfps
        WHERE source_portal IS NOT NULL
        GROUP BY source_portal ORDER BY count DESC
    ''')
    stats['by_portal'] = {row['source_portal']: row['count'] for row in cursor.fetchall()}

    conn.close()
    return stats


if __name__ == '__main__':
    init_database()
    seed_keywords()
    seed_sources()
    seed_rfp_keywords()
    print("Database initialized and seeded successfully!")
