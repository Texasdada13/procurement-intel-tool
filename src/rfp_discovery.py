"""
RFP Discovery module for Procurement Intelligence Tool.
Scrapes Florida government procurement portals for RFP/RFQ opportunities.
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

from . import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


class RFPDiscoveryEngine:
    """Engine for discovering RFP/RFQ opportunities from procurement portals."""

    def __init__(self):
        self.keywords = db.get_rfp_keywords()
        self.keyword_patterns = self._compile_keyword_patterns()

    def _compile_keyword_patterns(self) -> Dict:
        """Compile keyword patterns for fast matching."""
        patterns = {}
        for kw in self.keywords:
            pattern = re.compile(re.escape(kw['keyword']), re.IGNORECASE)
            patterns[kw['keyword']] = {
                'pattern': pattern,
                'category': kw['category'],
                'weight': kw['weight']
            }
        return patterns

    def calculate_relevance(self, title: str, description: str = '') -> tuple:
        """Calculate relevance score and determine category based on keyword matches."""
        text = f"{title} {description}".lower()
        total_score = 0
        matched_categories = {}

        for keyword, info in self.keyword_patterns.items():
            if info['pattern'].search(text):
                total_score += info['weight']
                cat = info['category']
                matched_categories[cat] = matched_categories.get(cat, 0) + info['weight']

        # Determine primary category
        primary_category = None
        if matched_categories:
            primary_category = max(matched_categories, key=matched_categories.get)

        is_relevant = total_score >= 2.0  # Threshold for relevance

        return is_relevant, total_score, primary_category

    def match_entity(self, agency_name: str) -> Optional[int]:
        """Try to match agency name to existing entity."""
        if not agency_name:
            return None

        # Get all entities
        entities = db.get_all_entities()

        # Normalize agency name
        agency_lower = agency_name.lower()

        # Try exact match first
        for entity in entities:
            if entity['name'].lower() == agency_lower:
                return entity['id']

        # Try partial match
        for entity in entities:
            entity_lower = entity['name'].lower()
            if entity_lower in agency_lower or agency_lower in entity_lower:
                return entity['id']

            # Try matching county names
            if 'county' in agency_lower:
                county_match = re.search(r'(\w+)\s+county', agency_lower)
                if county_match:
                    county_name = county_match.group(1)
                    if county_name in entity_lower:
                        return entity['id']

        return None

    def scrape_vendorlink(self, max_pages: int = 5) -> List[Dict]:
        """
        Scrape VendorLink Florida (myflorida.com) for solicitations.
        This is the main Florida state procurement portal.
        """
        results = []
        base_url = 'https://vendor.myflorida.com/search/bids'

        logger.info("Scraping VendorLink Florida...")

        try:
            # VendorLink uses a search form, we'll try the public bid listings
            response = requests.get(
                f'{base_url}?status=open',
                headers=HEADERS,
                timeout=30
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find bid listings (structure may vary)
                bid_rows = soup.find_all('tr', class_='bid-row') or soup.find_all('div', class_='bid-item')

                for row in bid_rows[:50]:  # Limit to 50 per run
                    try:
                        rfp_data = self._parse_vendorlink_row(row)
                        if rfp_data:
                            results.append(rfp_data)
                    except Exception as e:
                        logger.debug(f"Error parsing VendorLink row: {e}")

        except Exception as e:
            logger.error(f"Error scraping VendorLink: {e}")

        return results

    def scrape_demandstar(self, max_results: int = 50) -> List[Dict]:
        """
        Scrape DemandStar for Florida government bids.
        DemandStar is a popular platform used by many Florida counties.
        """
        results = []
        base_url = 'https://www.demandstar.com/app/api/bids'

        logger.info("Scraping DemandStar Florida bids...")

        try:
            # DemandStar has an API we can query
            params = {
                'state': 'FL',
                'status': 'open',
                'limit': max_results
            }

            response = requests.get(
                base_url,
                params=params,
                headers=HEADERS,
                timeout=30
            )

            if response.status_code == 200:
                # Try to parse as JSON first
                try:
                    data = response.json()
                    if isinstance(data, list):
                        for bid in data:
                            rfp_data = self._parse_demandstar_bid(bid)
                            if rfp_data:
                                results.append(rfp_data)
                except:
                    # Fall back to HTML parsing
                    soup = BeautifulSoup(response.text, 'html.parser')
                    bid_cards = soup.find_all('div', class_='bid-card')
                    for card in bid_cards[:max_results]:
                        rfp_data = self._parse_demandstar_html(card)
                        if rfp_data:
                            results.append(rfp_data)

        except Exception as e:
            logger.error(f"Error scraping DemandStar: {e}")

        return results

    def scrape_bonfire(self, max_results: int = 50) -> List[Dict]:
        """
        Scrape Bonfire procurement portal.
        Many Florida counties use Bonfire for e-procurement.
        """
        results = []

        # List of Florida agencies using Bonfire
        bonfire_agencies = [
            ('Orange County', 'https://orangecountyfl.bonfirehub.com/opportunities'),
            ('Hillsborough County', 'https://hillsboroughcounty.bonfirehub.com/opportunities'),
            ('Palm Beach County', 'https://pbcgov.bonfirehub.com/opportunities'),
            ('Broward County', 'https://broward.bonfirehub.com/opportunities'),
        ]

        for agency_name, url in bonfire_agencies:
            logger.info(f"Scraping Bonfire for {agency_name}...")
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    opp_cards = soup.find_all('div', class_='opportunity-card') or \
                               soup.find_all('tr', class_='opportunity-row') or \
                               soup.find_all('a', class_='opportunity-link')

                    for card in opp_cards[:max_results]:
                        rfp_data = self._parse_bonfire_opportunity(card, agency_name, url)
                        if rfp_data:
                            results.append(rfp_data)

            except Exception as e:
                logger.debug(f"Error scraping Bonfire for {agency_name}: {e}")

        return results

    def scrape_florida_bids_direct(self) -> List[Dict]:
        """
        Scrape direct from Florida county bid pages.
        This covers counties that don't use major procurement platforms.
        """
        results = []

        # Direct county bid pages
        county_bid_urls = [
            ('Marion County', 'https://www.marioncountyfl.org/departments-agencies/purchasing-contracts/bids-rfps'),
            ('Alachua County', 'https://procurement.alachuacounty.us/'),
            ('Leon County', 'https://cms.leoncountyfl.gov/coadmin/Purchasing/Bids-and-Proposals'),
            ('Volusia County', 'https://www.volusia.org/services/government/purchasing-contracts/current-bids-and-contracts/'),
            ('Brevard County', 'https://www.brevardfl.gov/CentralServices/Purchasing/CurrentBids'),
            ('Sarasota County', 'https://www.scgov.net/government/procurement-services/open-solicitations'),
            ('Collier County', 'https://www.colliercountyfl.gov/your-government/divisions-a-e/administrative-services/procurement-services/bids'),
            ('Lee County', 'https://www.leegov.com/procurement/bids'),
            ('Polk County', 'https://www.polk-county.net/purchasing/current-bids-and-proposals'),
            ('Seminole County', 'https://www.seminolecountyfl.gov/departments-services/county-manager/purchasing-contracts/current-bids-proposals.stml'),
        ]

        for county_name, url in county_bid_urls:
            logger.info(f"Scraping {county_name} bid page...")
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    rfps = self._parse_county_bid_page(soup, county_name, url)
                    results.extend(rfps)
            except Exception as e:
                logger.debug(f"Error scraping {county_name}: {e}")

        return results

    def _parse_vendorlink_row(self, row) -> Optional[Dict]:
        """Parse a VendorLink bid row."""
        try:
            title_elem = row.find('a') or row.find('td', class_='title')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            url = title_elem.get('href', '')

            # Look for other fields
            agency = row.find('td', class_='agency')
            due_date = row.find('td', class_='due-date')
            sol_num = row.find('td', class_='solicitation-number')

            is_relevant, score, category = self.calculate_relevance(title)

            return {
                'title': title,
                'description': '',
                'solicitation_number': sol_num.get_text(strip=True) if sol_num else None,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': agency.get_text(strip=True) if agency else 'State of Florida',
                'posted_date': datetime.now().isoformat(),
                'due_date': due_date.get_text(strip=True) if due_date else None,
                'source_url': url,
                'source_portal': 'vendorlink',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing VendorLink row: {e}")
            return None

    def _parse_demandstar_bid(self, bid: Dict) -> Optional[Dict]:
        """Parse a DemandStar API bid response."""
        try:
            title = bid.get('title', '') or bid.get('name', '')
            description = bid.get('description', '')

            is_relevant, score, category = self.calculate_relevance(title, description)

            return {
                'title': title,
                'description': description,
                'solicitation_number': bid.get('bidNumber') or bid.get('solicitation_number'),
                'rfp_type': bid.get('bidType', 'RFP'),
                'category': category,
                'agency_name': bid.get('agency', {}).get('name') if isinstance(bid.get('agency'), dict) else bid.get('agency'),
                'posted_date': bid.get('publishDate') or bid.get('posted_date'),
                'due_date': bid.get('dueDate') or bid.get('closing_date'),
                'source_url': bid.get('url') or f"https://www.demandstar.com/bids/{bid.get('id')}",
                'source_portal': 'demandstar',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing DemandStar bid: {e}")
            return None

    def _parse_demandstar_html(self, card) -> Optional[Dict]:
        """Parse DemandStar HTML bid card."""
        try:
            title_elem = card.find('h3') or card.find('a', class_='bid-title')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            description = ''
            desc_elem = card.find('p', class_='description')
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            is_relevant, score, category = self.calculate_relevance(title, description)

            url = ''
            link = card.find('a')
            if link:
                url = link.get('href', '')

            return {
                'title': title,
                'description': description,
                'solicitation_number': None,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': None,
                'posted_date': datetime.now().isoformat(),
                'due_date': None,
                'source_url': url,
                'source_portal': 'demandstar',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing DemandStar HTML: {e}")
            return None

    def _parse_bonfire_opportunity(self, card, agency_name: str, base_url: str) -> Optional[Dict]:
        """Parse a Bonfire opportunity card."""
        try:
            title_elem = card.find('h4') or card.find('a') or card.find('span', class_='title')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)

            # Get description if available
            description = ''
            desc_elem = card.find('p') or card.find('div', class_='description')
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            is_relevant, score, category = self.calculate_relevance(title, description)

            # Get URL
            url = base_url
            link = card.find('a')
            if link and link.get('href'):
                url = urljoin(base_url, link.get('href'))

            return {
                'title': title,
                'description': description,
                'solicitation_number': None,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': agency_name,
                'posted_date': datetime.now().isoformat(),
                'due_date': None,
                'source_url': url,
                'source_portal': 'bonfire',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing Bonfire opportunity: {e}")
            return None

    def _parse_county_bid_page(self, soup: BeautifulSoup, county_name: str, base_url: str) -> List[Dict]:
        """Parse a generic county bid page."""
        results = []

        # Look for common patterns in bid listings
        bid_elements = []

        # Try various selectors
        selectors = [
            ('table tr', 'table'),
            ('div.bid', 'div'),
            ('li.bid-item', 'list'),
            ('a[href*="bid"]', 'links'),
            ('a[href*="rfp"]', 'links'),
            ('a[href*="solicitation"]', 'links'),
            ('div.card', 'card'),
            ('article', 'article'),
        ]

        for selector, sel_type in selectors:
            elements = soup.select(selector)
            if elements:
                bid_elements = elements
                break

        # Parse found elements
        for elem in bid_elements[:30]:  # Limit per county
            try:
                # Extract title
                title = ''
                title_elem = elem.find('a') or elem.find('h3') or elem.find('h4') or elem.find('strong')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                elif elem.name == 'a':
                    title = elem.get_text(strip=True)
                elif elem.name == 'tr':
                    cells = elem.find_all('td')
                    if cells:
                        title = cells[0].get_text(strip=True)

                if not title or len(title) < 10:
                    continue

                # Skip header rows
                if 'bid number' in title.lower() or 'solicitation' in title.lower() and len(title) < 20:
                    continue

                # Get URL
                url = base_url
                link = elem.find('a')
                if link and link.get('href'):
                    href = link.get('href')
                    if href.startswith('http'):
                        url = href
                    else:
                        url = urljoin(base_url, href)

                is_relevant, score, category = self.calculate_relevance(title)

                results.append({
                    'title': title,
                    'description': '',
                    'solicitation_number': None,
                    'rfp_type': 'RFP',
                    'category': category,
                    'agency_name': county_name,
                    'posted_date': datetime.now().isoformat(),
                    'due_date': None,
                    'source_url': url,
                    'source_portal': 'county_site',
                    'is_relevant': is_relevant,
                    'relevance_score': score
                })

            except Exception as e:
                logger.debug(f"Error parsing county bid element: {e}")

        return results

    def save_rfps(self, rfps: List[Dict]) -> int:
        """Save discovered RFPs to database."""
        saved_count = 0

        for rfp_data in rfps:
            # Try to match entity
            entity_id = self.match_entity(rfp_data.get('agency_name'))

            # Parse dates
            posted_date = rfp_data.get('posted_date')
            due_date = rfp_data.get('due_date')

            # Create RFP record
            rfp_id = db.create_rfp(
                title=rfp_data['title'],
                entity_id=entity_id,
                description=rfp_data.get('description'),
                solicitation_number=rfp_data.get('solicitation_number'),
                rfp_type=rfp_data.get('rfp_type', 'RFP'),
                category=rfp_data.get('category'),
                posted_date=posted_date,
                due_date=due_date,
                source_url=rfp_data.get('source_url'),
                source_portal=rfp_data.get('source_portal'),
                is_relevant=1 if rfp_data.get('is_relevant') else 0,
                relevance_score=rfp_data.get('relevance_score', 0)
            )

            if rfp_id:
                saved_count += 1
                if rfp_data.get('is_relevant'):
                    logger.info(f"  + RELEVANT: {rfp_data['title'][:60]}... (score: {rfp_data.get('relevance_score', 0):.1f})")

        return saved_count

    def run_discovery(self) -> Dict:
        """Run full RFP discovery across all portals."""
        logger.info("=" * 70)
        logger.info("STARTING RFP DISCOVERY")
        logger.info("=" * 70)

        all_rfps = []
        stats = {
            'total_found': 0,
            'relevant_found': 0,
            'saved': 0,
            'by_portal': {}
        }

        # Scrape each portal
        portals = [
            ('County Sites', self.scrape_florida_bids_direct),
            ('Bonfire', self.scrape_bonfire),
            ('DemandStar', self.scrape_demandstar),
            ('VendorLink', self.scrape_vendorlink),
        ]

        for portal_name, scrape_func in portals:
            logger.info(f"\n--- Scraping {portal_name} ---")
            try:
                rfps = scrape_func()
                stats['by_portal'][portal_name] = len(rfps)
                all_rfps.extend(rfps)
                logger.info(f"Found {len(rfps)} RFPs from {portal_name}")
            except Exception as e:
                logger.error(f"Error scraping {portal_name}: {e}")
                stats['by_portal'][portal_name] = 0

        # Save all RFPs
        stats['total_found'] = len(all_rfps)
        stats['relevant_found'] = sum(1 for r in all_rfps if r.get('is_relevant'))
        stats['saved'] = self.save_rfps(all_rfps)

        logger.info("\n" + "=" * 70)
        logger.info("RFP DISCOVERY COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total RFPs found: {stats['total_found']}")
        logger.info(f"Relevant IT/Consulting RFPs: {stats['relevant_found']}")
        logger.info(f"Saved to database: {stats['saved']}")

        return stats


def manual_add_rfp(url: str, title: str = None, **kwargs) -> Optional[int]:
    """Manually add an RFP by URL."""
    engine = RFPDiscoveryEngine()

    try:
        # Fetch the page to get more details
        response = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try to extract title from page if not provided
        if not title:
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)

        if not title:
            title = "Unknown RFP"

        # Get description
        description = ''
        for tag in ['article', 'main', 'div.content', 'div.description']:
            elem = soup.select_one(tag)
            if elem:
                description = elem.get_text(strip=True)[:2000]
                break

        # Calculate relevance
        is_relevant, score, category = engine.calculate_relevance(title, description)

        # Determine source portal from URL
        domain = urlparse(url).netloc
        source_portal = 'manual'
        if 'bonfire' in domain:
            source_portal = 'bonfire'
        elif 'demandstar' in domain:
            source_portal = 'demandstar'
        elif 'myflorida' in domain:
            source_portal = 'vendorlink'

        # Try to match entity
        agency_name = kwargs.get('agency_name')
        entity_id = engine.match_entity(agency_name) if agency_name else None

        # Create RFP
        rfp_id = db.create_rfp(
            title=title,
            entity_id=entity_id,
            description=description,
            solicitation_number=kwargs.get('solicitation_number'),
            rfp_type=kwargs.get('rfp_type', 'RFP'),
            category=category,
            posted_date=kwargs.get('posted_date', datetime.now().isoformat()),
            due_date=kwargs.get('due_date'),
            source_url=url,
            source_portal=source_portal,
            is_relevant=1 if is_relevant else 0,
            relevance_score=score,
            contact_name=kwargs.get('contact_name'),
            contact_email=kwargs.get('contact_email')
        )

        logger.info(f"Added RFP: {title[:50]}... (relevant: {is_relevant}, score: {score:.1f})")
        return rfp_id

    except Exception as e:
        logger.error(f"Error adding RFP from {url}: {e}")
        return None


if __name__ == '__main__':
    # Initialize database tables
    db.init_database()
    db.seed_rfp_keywords()

    # Run discovery
    engine = RFPDiscoveryEngine()
    stats = engine.run_discovery()
