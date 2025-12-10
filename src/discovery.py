"""
Discovery Engine for Procurement Intelligence Tool.
Handles scraping news sources and identifying potential opportunities.
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import time

from . import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Request headers to appear as a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Florida counties for entity extraction
FLORIDA_COUNTIES = [
    'Alachua', 'Baker', 'Bay', 'Bradford', 'Brevard', 'Broward', 'Calhoun',
    'Charlotte', 'Citrus', 'Clay', 'Collier', 'Columbia', 'DeSoto', 'Dixie',
    'Duval', 'Escambia', 'Flagler', 'Franklin', 'Gadsden', 'Gilchrist',
    'Glades', 'Gulf', 'Hamilton', 'Hardee', 'Hendry', 'Hernando', 'Highlands',
    'Hillsborough', 'Holmes', 'Indian River', 'Jackson', 'Jefferson', 'Lafayette',
    'Lake', 'Lee', 'Leon', 'Levy', 'Liberty', 'Madison', 'Manatee', 'Marion',
    'Martin', 'Miami-Dade', 'Monroe', 'Nassau', 'Okaloosa', 'Okeechobee',
    'Orange', 'Osceola', 'Palm Beach', 'Pasco', 'Pinellas', 'Polk', 'Putnam',
    'Santa Rosa', 'Sarasota', 'Seminole', 'St. Johns', 'St. Lucie', 'Sumter',
    'Suwannee', 'Taylor', 'Union', 'Volusia', 'Wakulla', 'Walton', 'Washington'
]

# Entity type patterns - improved for better extraction
ENTITY_PATTERNS = [
    (r'(\w+(?:-\w+)?(?:\s+\w+)?)\s+(?:County\s+)?School\s+Board', 'school_board'),
    (r'(\w+(?:-\w+)?(?:\s+\w+)?)\s+County\s+Commission', 'county'),
    (r'(\w+(?:-\w+)?(?:\s+\w+)?)\s+County\s+Board', 'county'),
    (r'(\w+(?:-\w+)?(?:\s+\w+)?)\s+County\s+Government', 'county'),
    (r'(\w+(?:-\w+)?(?:\s+\w+)?)\s+County(?:\s|,|\.)', 'county'),
    (r'City\s+of\s+(\w+(?:\s+\w+)?)', 'city'),
    (r'(\w+(?:\s+\w+)?)\s+City\s+Council', 'city'),
    (r'(\w+(?:\s+\w+)?)\s+City\s+Commission', 'city'),
    (r'(\w+(?:-\w+)?(?:\s+\w+)?)\s+School\s+District', 'school_board'),
    (r'(\w+(?:\s+\w+)?)\s+Water\s+(?:Management\s+)?District', 'utility'),
    (r'JEA', 'utility'),  # Jacksonville Electric Authority
    (r'FPL|Florida\s+Power', 'utility'),
]

# Major Florida cities for direct matching
FLORIDA_CITIES = [
    'Jacksonville', 'Miami', 'Tampa', 'Orlando', 'St. Petersburg', 'Hialeah',
    'Port St. Lucie', 'Cape Coral', 'Tallahassee', 'Fort Lauderdale',
    'Pembroke Pines', 'Hollywood', 'Gainesville', 'Miramar', 'Coral Springs',
    'Clearwater', 'Miami Gardens', 'Palm Bay', 'Pompano Beach', 'West Palm Beach',
    'Lakeland', 'Davie', 'Boca Raton', 'Sunrise', 'Deltona', 'Plantation',
    'Fort Myers', 'Deerfield Beach', 'Palm Coast', 'Melbourne', 'Boynton Beach',
    'Largo', 'Kissimmee', 'Homestead', 'Doral', 'Tamarac', 'Delray Beach',
    'Daytona Beach', 'Weston', 'North Port', 'Wellington', 'North Miami',
    'Jupiter', 'Ocala', 'Port Orange', 'Margate', 'Coconut Creek', 'Sanford',
    'Sarasota', 'Pensacola', 'Bradenton', 'St. Cloud', 'Winter Haven', 'Apopka',
]


class DiscoveryEngine:
    """Engine for discovering procurement-related opportunities from news sources."""

    def __init__(self):
        self.keywords = db.get_all_keywords()
        self.keyword_patterns = self._compile_keyword_patterns()

    def _compile_keyword_patterns(self) -> List[Tuple[re.Pattern, Dict]]:
        """Compile keyword patterns for efficient matching."""
        patterns = []
        for kw in self.keywords:
            # Create case-insensitive pattern for each keyword
            pattern = re.compile(r'\b' + re.escape(kw['keyword']) + r'\b', re.IGNORECASE)
            patterns.append((pattern, kw))
        return patterns

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a web page and return its HTML content."""
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_article_content(self, html: str, url: str) -> Dict:
        """Extract article title, content, and metadata from HTML."""
        soup = BeautifulSoup(html, 'lxml')

        # Try to find the title
        title = None
        title_candidates = [
            soup.find('h1', class_=re.compile(r'title|headline', re.I)),
            soup.find('h1'),
            soup.find('meta', property='og:title'),
            soup.find('title'),
        ]
        for candidate in title_candidates:
            if candidate:
                title = candidate.get('content') if candidate.name == 'meta' else candidate.get_text()
                if title:
                    title = title.strip()
                    break

        # Try to find the main content
        content = ''
        content_candidates = [
            soup.find('article'),
            soup.find('div', class_=re.compile(r'article|content|story|post', re.I)),
            soup.find('main'),
        ]
        for candidate in content_candidates:
            if candidate:
                # Remove script and style elements
                for script in candidate(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()
                content = candidate.get_text(separator=' ', strip=True)
                break

        # Try to find published date
        published_date = None
        date_candidates = [
            soup.find('meta', property='article:published_time'),
            soup.find('meta', property='og:published_time'),
            soup.find('time'),
            soup.find(class_=re.compile(r'date|time|published', re.I)),
        ]
        for candidate in date_candidates:
            if candidate:
                date_str = candidate.get('content') or candidate.get('datetime') or candidate.get_text()
                if date_str:
                    try:
                        # Try parsing various date formats
                        from dateutil import parser
                        published_date = parser.parse(date_str)
                        break
                    except:
                        pass

        return {
            'title': title or 'Unknown Title',
            'content': content,
            'published_date': published_date,
            'url': url,
        }

    def analyze_content(self, content: str) -> Tuple[float, List[Dict], str]:
        """
        Analyze content for procurement-related keywords.
        Returns (score, matched_keywords, issue_type).
        """
        if not content:
            return 0, [], None

        matched_keywords = []
        total_score = 0
        category_scores = {}

        for pattern, kw in self.keyword_patterns:
            matches = pattern.findall(content)
            if matches:
                match_count = len(matches)
                score = kw['weight'] * match_count
                total_score += score
                matched_keywords.append({
                    'keyword': kw['keyword'],
                    'category': kw['category'],
                    'count': match_count,
                    'score': score
                })
                category_scores[kw['category']] = category_scores.get(kw['category'], 0) + score

        # Determine primary issue type based on highest category score
        issue_type = None
        if category_scores:
            issue_type = max(category_scores, key=category_scores.get)

        # Normalize score to 0-100 scale
        heat_score = min(100, total_score * 5)  # Adjust multiplier as needed

        return heat_score, matched_keywords, issue_type

    def extract_entities(self, content: str, title: str = '') -> List[Dict]:
        """Extract government entities mentioned in the content."""
        full_text = f"{title} {content}"
        entities = []
        seen = set()

        # First, check for specific utilities
        if 'JEA' in full_text or 'Jacksonville Electric Authority' in full_text:
            key = ('JEA (Jacksonville)', 'utility')
            if key not in seen:
                seen.add(key)
                entities.append({
                    'name': 'JEA (Jacksonville)',
                    'entity_type': 'utility',
                    'state': 'FL'
                })
                # Also add Jacksonville/Duval
                if ('Jacksonville', 'city') not in seen:
                    seen.add(('Jacksonville', 'city'))
                    entities.append({'name': 'Jacksonville', 'entity_type': 'city', 'state': 'FL'})
                if ('Duval', 'county') not in seen:
                    seen.add(('Duval', 'county'))
                    entities.append({'name': 'Duval', 'entity_type': 'county', 'state': 'FL'})

        # Check for county patterns
        for pattern_str, entity_type in ENTITY_PATTERNS:
            if entity_type == 'utility' and 'JEA' in pattern_str:
                continue  # Already handled above
            pattern = re.compile(pattern_str, re.IGNORECASE)
            matches = pattern.findall(full_text)
            for match in matches:
                name = match.strip() if isinstance(match, str) else match
                # Skip common false positives
                if name.lower() in ['the', 'a', 'an', 'by', 'to', 'in', 'for', 'and', 'or', 'this']:
                    continue

                # Validate it's a real Florida county if county-related
                if entity_type in ['county', 'school_board']:
                    county_match = None
                    for county in FLORIDA_COUNTIES:
                        if county.lower() in name.lower():
                            county_match = county
                            break
                    if not county_match:
                        continue
                    name = county_match

                key = (name, entity_type)
                if key not in seen:
                    seen.add(key)
                    entities.append({
                        'name': name,
                        'entity_type': entity_type,
                        'state': 'FL'
                    })

        # Also check for major city mentions
        for city in FLORIDA_CITIES:
            if city in full_text:
                key = (city, 'city')
                if key not in seen:
                    seen.add(key)
                    entities.append({
                        'name': city,
                        'entity_type': 'city',
                        'state': 'FL'
                    })

        return entities

    def generate_attack_brief(self, title: str, summary: str, matched_keywords: List[Dict],
                              entity_name: str, issue_type: str) -> str:
        """Generate talking points for sales outreach based on the opportunity."""
        brief_parts = []

        brief_parts.append(f"## Opportunity: {entity_name}")
        brief_parts.append(f"\n### Issue Summary\n{summary or title}")

        # Key talking points based on issue type
        brief_parts.append("\n### Key Talking Points")

        if issue_type == 'procurement':
            brief_parts.append("- Their procurement process has been publicly questioned")
            brief_parts.append("- A contract oversight system could prevent future bid manipulation")
            brief_parts.append("- Automated vendor scoring removes human bias from selection")
            brief_parts.append("- Audit trail provides transparency for public records requests")

        elif issue_type == 'audit':
            brief_parts.append("- Audit findings indicate gaps in financial oversight")
            brief_parts.append("- Our system provides real-time monitoring to catch issues early")
            brief_parts.append("- Comprehensive reporting simplifies compliance")
            brief_parts.append("- Reduces risk of future audit findings")

        elif issue_type == 'ethics':
            brief_parts.append("- Ethics concerns highlight need for transparent processes")
            brief_parts.append("- Our system creates clear separation between vendors and evaluators")
            brief_parts.append("- All interactions are logged and auditable")
            brief_parts.append("- Helps restore public trust through accountability")

        elif issue_type == 'budget':
            brief_parts.append("- Budget pressures make efficient spending critical")
            brief_parts.append("- Our system identifies cost-saving opportunities")
            brief_parts.append("- Prevents wasteful spending through better oversight")
            brief_parts.append("- ROI through reduced change orders and overruns")

        elif issue_type == 'legal':
            brief_parts.append("- Legal exposure creates urgency for better controls")
            brief_parts.append("- Documented processes reduce liability")
            brief_parts.append("- Proactive monitoring prevents future legal issues")
            brief_parts.append("- Shows good faith effort at reform")

        # Keywords detected
        if matched_keywords:
            brief_parts.append("\n### Keywords Detected")
            top_keywords = sorted(matched_keywords, key=lambda x: x['score'], reverse=True)[:5]
            for kw in top_keywords:
                brief_parts.append(f"- {kw['keyword']} (mentioned {kw['count']}x)")

        brief_parts.append("\n### Recommended Approach")
        brief_parts.append("1. Reference the specific incident in outreach")
        brief_parts.append("2. Position as a solution to prevent recurrence")
        brief_parts.append("3. Emphasize public accountability and transparency")
        brief_parts.append("4. Offer a demo focused on their specific pain points")

        return '\n'.join(brief_parts)

    def process_article(self, url: str, source_id: int = None) -> Optional[Dict]:
        """
        Process a single article URL.
        Returns opportunity data if relevant, None otherwise.
        """
        logger.info(f"Processing article: {url}")

        html = self.fetch_page(url)
        if not html:
            return None

        article_data = self.extract_article_content(html, url)
        full_content = f"{article_data['title']} {article_data['content']}"

        # Analyze for keywords
        heat_score, matched_keywords, issue_type = self.analyze_content(full_content)

        if heat_score < 10:  # Minimum threshold
            logger.info(f"Article below threshold (score: {heat_score})")
            return None

        # Extract entities
        entities = self.extract_entities(full_content, article_data['title'])
        if not entities:
            logger.info("No government entities found in article")
            return None

        # Save article to database
        article_id = db.create_article(
            url=url,
            title=article_data['title'],
            source_id=source_id,
            content=article_data['content'][:10000],  # Truncate for storage
            summary=article_data['content'][:500] if article_data['content'] else None,
            published_date=article_data['published_date']
        )

        # Record keyword matches
        for kw_match in matched_keywords:
            kw_data = next((k for k in self.keywords if k['keyword'] == kw_match['keyword']), None)
            if kw_data:
                db.add_keyword_match(article_id, kw_data['id'], kw_match['count'])

        results = []
        for entity in entities:
            # Create or get entity
            entity_id = db.create_entity(
                name=entity['name'],
                entity_type=entity['entity_type'],
                state=entity['state'],
                county=entity['name'] if entity['entity_type'] in ['county', 'school_board'] else None
            )

            # Generate attack brief
            attack_brief = self.generate_attack_brief(
                title=article_data['title'],
                summary=article_data['content'][:500] if article_data['content'] else '',
                matched_keywords=matched_keywords,
                entity_name=entity['name'],
                issue_type=issue_type
            )

            # Create opportunity
            opp_title = f"{article_data['title'][:100]}"
            opportunity_id = db.create_opportunity(
                entity_id=entity_id,
                title=opp_title,
                summary=article_data['content'][:500] if article_data['content'] else None,
                heat_score=heat_score,
                issue_type=issue_type,
                attack_brief=attack_brief
            )

            # Link article to opportunity
            db.link_article_to_opportunity(article_id, opportunity_id)

            # Add activity log
            db.add_activity_log(
                opportunity_id,
                'opportunity_created',
                f'Opportunity created from article: {url}'
            )

            results.append({
                'opportunity_id': opportunity_id,
                'entity': entity,
                'heat_score': heat_score,
                'issue_type': issue_type,
                'title': opp_title
            })

        return results

    def search_google_news(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search Google News for relevant articles.
        Returns list of article URLs.
        """
        # Use Google News RSS feed
        search_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"

        try:
            import feedparser
            feed = feedparser.parse(search_url)
            urls = []
            for entry in feed.entries[:num_results]:
                # Google News redirects through their URL, try to get the actual URL
                urls.append(entry.link)
            return urls
        except Exception as e:
            logger.error(f"Error searching Google News: {e}")
            return []

    def run_discovery(self, search_queries: List[str] = None) -> List[Dict]:
        """
        Run a full discovery cycle.
        Searches for articles using default or provided queries.
        """
        if search_queries is None:
            search_queries = [
                'Florida county procurement violation',
                'Florida school board bid rigging',
                'Florida county audit findings',
                'Florida city contract scandal',
                'Florida government corruption investigation',
                'Florida inspector general report procurement',
                'Florida county budget mismanagement',
                'Florida school district construction bid',
            ]

        all_results = []
        processed_urls = set()

        for query in search_queries:
            logger.info(f"Searching: {query}")
            urls = self.search_google_news(query, num_results=5)

            for url in urls:
                if url in processed_urls:
                    continue
                processed_urls.add(url)

                try:
                    results = self.process_article(url)
                    if results:
                        all_results.extend(results)
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")

                # Be nice to servers
                time.sleep(1)

        logger.info(f"Discovery complete. Found {len(all_results)} opportunities.")
        return all_results


def manual_add_article(url: str) -> Optional[List[Dict]]:
    """
    Manually add and process an article URL.
    Useful for adding specific articles you've found.
    """
    engine = DiscoveryEngine()
    return engine.process_article(url)


if __name__ == '__main__':
    # Initialize database if needed
    db.init_database()
    db.seed_keywords()
    db.seed_sources()

    # Run discovery
    engine = DiscoveryEngine()
    results = engine.run_discovery()

    for result in results:
        print(f"Found: {result['entity']['name']} ({result['entity']['entity_type']}) - Score: {result['heat_score']}")
