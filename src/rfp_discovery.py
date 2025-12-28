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

    def scrape_mfmp(self, max_results: int = 100) -> List[Dict]:
        """
        Scrape MyFloridaMarketPlace (MFMP) - the official Florida state procurement system.
        This is where state agencies post their solicitations.
        """
        results = []

        logger.info("Scraping MyFloridaMarketPlace (MFMP)...")

        # MFMP Advertisement Search
        mfmp_urls = [
            ('MFMP Advertisements', 'https://vendor.myfloridamarketplace.com/search/advertisements'),
            ('MFMP Solicitations', 'https://vendor.myfloridamarketplace.com/search/solicitations'),
            ('MFMP State Term Contracts', 'https://www.dms.myflorida.com/business_operations/state_purchasing/state_contracts_and_agreements'),
            ('DMS Procurement', 'https://www.dms.myflorida.com/business_operations/state_purchasing/vendor_resources/current_solicitations'),
        ]

        for source_name, url in mfmp_urls:
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Try multiple selectors for MFMP's various page formats
                    items = soup.find_all('div', class_='advertisement') or \
                           soup.find_all('tr', class_='solicitation-row') or \
                           soup.find_all('div', class_='solicitation-item') or \
                           soup.find_all('table', class_='solicitations')

                    if items:
                        for item in items[:max_results]:
                            rfp_data = self._parse_mfmp_item(item, url)
                            if rfp_data:
                                results.append(rfp_data)
                    else:
                        # Try parsing as a table
                        tables = soup.find_all('table')
                        for table in tables:
                            rows = table.find_all('tr')[1:]  # Skip header
                            for row in rows[:max_results]:
                                rfp_data = self._parse_mfmp_table_row(row, url)
                                if rfp_data:
                                    results.append(rfp_data)

                        # Also try finding links with solicitation-related text
                        links = soup.find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            text = link.get_text(strip=True)
                            if ('solicitation' in href.lower() or 'bid' in href.lower() or
                                'rfp' in href.lower() or 'itb' in href.lower() or 'itn' in href.lower()):
                                if text and len(text) > 15:
                                    is_relevant, score, category = self.calculate_relevance(text)
                                    full_url = href if href.startswith('http') else urljoin(url, href)
                                    results.append({
                                        'title': text,
                                        'description': '',
                                        'solicitation_number': None,
                                        'rfp_type': 'RFP',
                                        'category': category,
                                        'agency_name': 'State of Florida',
                                        'posted_date': datetime.now().isoformat(),
                                        'due_date': None,
                                        'source_url': full_url,
                                        'source_portal': 'mfmp',
                                        'is_relevant': is_relevant,
                                        'relevance_score': score
                                    })

            except Exception as e:
                logger.debug(f"Error scraping {source_name}: {e}")

        # Also scrape individual state agency procurement pages
        state_agency_urls = [
            ('FL Dept of Transportation', 'https://www.fdot.gov/contracts/procurement.shtm'),
            ('FL Dept of Education', 'https://www.fldoe.org/finance/contracts-grants-procurement/'),
            ('FL Dept of Health', 'https://www.floridahealth.gov/about/administrative-functions/purchasing/index.html'),
            ('FL Dept of Children & Families', 'https://www.myflfamilies.com/general-information/procurement-contracts'),
            ('FL Dept of Environmental Protection', 'https://floridadep.gov/admin/business-services/content/bids-awards'),
            ('FL Dept of Revenue', 'https://floridarevenue.com/opengovfl/pages/publicdocuments.aspx'),
            ('FL Dept of Corrections', 'http://www.dc.state.fl.us/ci/bids.html'),
            ('FL Dept of Agriculture', 'https://www.fdacs.gov/Business-Services/Procurement'),
            ('FL Fish & Wildlife', 'https://myfwc.com/about/inside-fwc/business/procurement/'),
            ('FL Lottery', 'https://www.flalottery.com/procurement'),
            ('FL Highway Patrol', 'https://www.flhsmv.gov/resources/procurement/'),
            ('FL Agency for Healthcare Admin', 'https://ahca.myflorida.com/procurements/'),
            ('FL Housing Finance Corp', 'https://www.floridahousing.org/about-florida-housing/procurement'),
            ('Enterprise Florida', 'https://www.enterpriseflorida.com/about-us/procurement/'),
        ]

        for agency_name, url in state_agency_urls:
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    rfps = self._parse_state_agency_page(soup, agency_name, url)
                    results.extend(rfps)
            except Exception as e:
                logger.debug(f"Error scraping {agency_name}: {e}")

        return results

    def _parse_mfmp_item(self, item, base_url: str) -> Optional[Dict]:
        """Parse an MFMP advertisement/solicitation item."""
        try:
            title_elem = item.find('a') or item.find('h3') or item.find('span', class_='title')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 10:
                return None

            url = base_url
            link = item.find('a')
            if link and link.get('href'):
                href = link.get('href')
                url = href if href.startswith('http') else urljoin(base_url, href)

            # Try to extract solicitation number
            sol_num = None
            sol_elem = item.find('span', class_='solicitation-number') or item.find('td', class_='number')
            if sol_elem:
                sol_num = sol_elem.get_text(strip=True)

            # Try to get due date
            due_date = None
            date_elem = item.find('span', class_='due-date') or item.find('td', class_='closing')
            if date_elem:
                due_date = date_elem.get_text(strip=True)

            # Get agency
            agency = 'State of Florida'
            agency_elem = item.find('span', class_='agency') or item.find('td', class_='agency')
            if agency_elem:
                agency = agency_elem.get_text(strip=True)

            is_relevant, score, category = self.calculate_relevance(title)

            return {
                'title': title,
                'description': '',
                'solicitation_number': sol_num,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': agency,
                'posted_date': datetime.now().isoformat(),
                'due_date': due_date,
                'source_url': url,
                'source_portal': 'mfmp',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing MFMP item: {e}")
            return None

    def _parse_mfmp_table_row(self, row, base_url: str) -> Optional[Dict]:
        """Parse an MFMP table row."""
        try:
            cells = row.find_all('td')
            if len(cells) < 2:
                return None

            title_cell = cells[0]
            link = title_cell.find('a')
            title = link.get_text(strip=True) if link else title_cell.get_text(strip=True)

            if not title or len(title) < 10:
                return None

            url = base_url
            if link and link.get('href'):
                href = link.get('href')
                url = href if href.startswith('http') else urljoin(base_url, href)

            sol_num = cells[1].get_text(strip=True) if len(cells) > 1 else None
            due_date = cells[2].get_text(strip=True) if len(cells) > 2 else None
            agency = cells[3].get_text(strip=True) if len(cells) > 3 else 'State of Florida'

            is_relevant, score, category = self.calculate_relevance(title)

            return {
                'title': title,
                'description': '',
                'solicitation_number': sol_num,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': agency,
                'posted_date': datetime.now().isoformat(),
                'due_date': due_date,
                'source_url': url,
                'source_portal': 'mfmp',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing MFMP table row: {e}")
            return None

    def _parse_state_agency_page(self, soup: BeautifulSoup, agency_name: str, base_url: str) -> List[Dict]:
        """Parse a state agency procurement page."""
        results = []

        # Look for links to solicitations/bids
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Filter for procurement-related links
            keywords = ['rfp', 'rfq', 'itb', 'itn', 'solicitation', 'bid', 'procurement', 'contract']
            if any(kw in href.lower() or kw in text.lower() for kw in keywords):
                if text and len(text) > 15 and len(text) < 300:
                    # Skip navigation/menu links
                    if any(skip in text.lower() for skip in ['click here', 'read more', 'learn more', 'view all']):
                        continue

                    is_relevant, score, category = self.calculate_relevance(text)
                    full_url = href if href.startswith('http') else urljoin(base_url, href)

                    results.append({
                        'title': text,
                        'description': '',
                        'solicitation_number': None,
                        'rfp_type': 'RFP',
                        'category': category,
                        'agency_name': agency_name,
                        'posted_date': datetime.now().isoformat(),
                        'due_date': None,
                        'source_url': full_url,
                        'source_portal': 'mfmp',
                        'is_relevant': is_relevant,
                        'relevance_score': score
                    })

        # Also look for table rows
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows[:30]:
                cells = row.find_all('td')
                if len(cells) >= 1:
                    title_cell = cells[0]
                    link = title_cell.find('a')
                    title = link.get_text(strip=True) if link else title_cell.get_text(strip=True)

                    if title and len(title) > 15:
                        is_relevant, score, category = self.calculate_relevance(title)
                        url = base_url
                        if link and link.get('href'):
                            href = link.get('href')
                            url = href if href.startswith('http') else urljoin(base_url, href)

                        results.append({
                            'title': title,
                            'description': '',
                            'solicitation_number': None,
                            'rfp_type': 'RFP',
                            'category': category,
                            'agency_name': agency_name,
                            'posted_date': datetime.now().isoformat(),
                            'due_date': None,
                            'source_url': url,
                            'source_portal': 'mfmp',
                            'is_relevant': is_relevant,
                            'relevance_score': score
                        })

        return results[:30]  # Limit per agency

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
            ('Miami-Dade County', 'https://miamidade.bonfirehub.com/opportunities'),
            ('Duval County', 'https://duval.bonfirehub.com/opportunities'),
            ('Pinellas County', 'https://pinellas.bonfirehub.com/opportunities'),
            ('Pasco County', 'https://pasco.bonfirehub.com/opportunities'),
            ('Manatee County', 'https://manatee.bonfirehub.com/opportunities'),
            ('St. Lucie County', 'https://stlucie.bonfirehub.com/opportunities'),
            ('Martin County', 'https://martin.bonfirehub.com/opportunities'),
            ('Indian River County', 'https://indianriver.bonfirehub.com/opportunities'),
            ('Osceola County', 'https://osceola.bonfirehub.com/opportunities'),
            ('Lake County', 'https://lakecountyfl.bonfirehub.com/opportunities'),
            ('City of Orlando', 'https://cityoforlando.bonfirehub.com/opportunities'),
            ('City of Tampa', 'https://tampa.bonfirehub.com/opportunities'),
            ('City of Jacksonville', 'https://jacksonville.bonfirehub.com/opportunities'),
            ('City of Miami', 'https://miami.bonfirehub.com/opportunities'),
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

    def scrape_bidnet(self, max_results: int = 100) -> List[Dict]:
        """
        Scrape BidNet Direct for Florida government bids.
        BidNet is one of the largest procurement platforms in the US.
        """
        results = []

        logger.info("Scraping BidNet Direct for Florida bids...")

        # BidNet search URL for Florida
        search_url = 'https://www.bidnetdirect.com/florida/bids'

        try:
            response = requests.get(search_url, headers=HEADERS, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # BidNet uses various card/list formats
                bid_items = soup.find_all('div', class_='bid-item') or \
                           soup.find_all('div', class_='search-result') or \
                           soup.find_all('tr', class_='bid-row') or \
                           soup.find_all('article', class_='bid')

                for item in bid_items[:max_results]:
                    rfp_data = self._parse_bidnet_item(item, search_url)
                    if rfp_data:
                        results.append(rfp_data)

                # Also try to find bids in a table format
                if not results:
                    tables = soup.find_all('table')
                    for table in tables:
                        rows = table.find_all('tr')[1:]  # Skip header
                        for row in rows[:max_results]:
                            rfp_data = self._parse_bidnet_table_row(row, search_url)
                            if rfp_data:
                                results.append(rfp_data)

        except Exception as e:
            logger.error(f"Error scraping BidNet: {e}")

        # Also scrape BidNet agency-specific pages
        bidnet_agencies = [
            ('Alachua County', 'https://www.bidnetdirect.com/florida/alachuacounty'),
            ('Bay County', 'https://www.bidnetdirect.com/florida/baycounty'),
            ('Charlotte County', 'https://www.bidnetdirect.com/florida/charlottecounty'),
            ('Citrus County', 'https://www.bidnetdirect.com/florida/citruscounty'),
            ('Clay County', 'https://www.bidnetdirect.com/florida/claycounty'),
            ('Flagler County', 'https://www.bidnetdirect.com/florida/flaglercounty'),
            ('Hernando County', 'https://www.bidnetdirect.com/florida/hernandocounty'),
            ('Highlands County', 'https://www.bidnetdirect.com/florida/highlandscounty'),
            ('Monroe County', 'https://www.bidnetdirect.com/florida/monroecounty'),
            ('Nassau County', 'https://www.bidnetdirect.com/florida/nassaucounty'),
            ('Okaloosa County', 'https://www.bidnetdirect.com/florida/okaloosacounty'),
            ('Santa Rosa County', 'https://www.bidnetdirect.com/florida/santarosacounty'),
            ('St. Johns County', 'https://www.bidnetdirect.com/florida/stjohnscounty'),
            ('Sumter County', 'https://www.bidnetdirect.com/florida/sumtercounty'),
            ('Walton County', 'https://www.bidnetdirect.com/florida/waltoncounty'),
        ]

        for agency_name, url in bidnet_agencies:
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    bid_items = soup.find_all('div', class_='bid-item') or \
                               soup.find_all('div', class_='search-result') or \
                               soup.find_all('a', href=lambda x: x and 'bid' in x.lower())

                    for item in bid_items[:20]:
                        rfp_data = self._parse_bidnet_item(item, url, agency_name)
                        if rfp_data:
                            results.append(rfp_data)
            except Exception as e:
                logger.debug(f"Error scraping BidNet for {agency_name}: {e}")

        return results

    def _parse_bidnet_item(self, item, base_url: str, agency_name: str = None) -> Optional[Dict]:
        """Parse a BidNet bid item."""
        try:
            # Try to find title
            title_elem = item.find('h3') or item.find('h4') or item.find('a', class_='title') or item.find('a')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 10:
                return None

            # Get URL
            url = base_url
            link = item.find('a')
            if link and link.get('href'):
                href = link.get('href')
                if href.startswith('http'):
                    url = href
                else:
                    url = urljoin(base_url, href)

            # Try to get agency name from item if not provided
            if not agency_name:
                agency_elem = item.find('span', class_='agency') or item.find('div', class_='agency')
                if agency_elem:
                    agency_name = agency_elem.get_text(strip=True)

            # Try to get due date
            due_date = None
            date_elem = item.find('span', class_='due-date') or item.find('div', class_='closing')
            if date_elem:
                due_date = date_elem.get_text(strip=True)

            # Get description
            description = ''
            desc_elem = item.find('p') or item.find('div', class_='description')
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            is_relevant, score, category = self.calculate_relevance(title, description)

            return {
                'title': title,
                'description': description,
                'solicitation_number': None,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': agency_name,
                'posted_date': datetime.now().isoformat(),
                'due_date': due_date,
                'source_url': url,
                'source_portal': 'bidnet',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing BidNet item: {e}")
            return None

    def _parse_bidnet_table_row(self, row, base_url: str) -> Optional[Dict]:
        """Parse a BidNet table row."""
        try:
            cells = row.find_all('td')
            if len(cells) < 2:
                return None

            # First cell usually has title/link
            title_cell = cells[0]
            link = title_cell.find('a')
            if not link:
                return None

            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                return None

            url = base_url
            if link.get('href'):
                href = link.get('href')
                if href.startswith('http'):
                    url = href
                else:
                    url = urljoin(base_url, href)

            # Try to get agency and due date from other cells
            agency_name = cells[1].get_text(strip=True) if len(cells) > 1 else None
            due_date = cells[2].get_text(strip=True) if len(cells) > 2 else None

            is_relevant, score, category = self.calculate_relevance(title)

            return {
                'title': title,
                'description': '',
                'solicitation_number': None,
                'rfp_type': 'RFP',
                'category': category,
                'agency_name': agency_name,
                'posted_date': datetime.now().isoformat(),
                'due_date': due_date,
                'source_url': url,
                'source_portal': 'bidnet',
                'is_relevant': is_relevant,
                'relevance_score': score
            }
        except Exception as e:
            logger.debug(f"Error parsing BidNet table row: {e}")
            return None

    def scrape_school_districts(self, max_results: int = 50) -> List[Dict]:
        """
        Scrape Florida school district procurement portals.
        School districts have separate procurement from county governments.
        """
        results = []

        logger.info("Scraping Florida school district procurement sites...")

        # Florida school district procurement pages
        school_districts = [
            # Large districts
            ('Miami-Dade County Public Schools', 'https://procurement.dadeschools.net/'),
            ('Broward County Public Schools', 'https://www.browardschools.com/Page/32196'),
            ('Palm Beach County School District', 'https://www.palmbeachschools.org/departments/purchasing'),
            ('Hillsborough County Public Schools', 'https://www.hillsboroughschools.org/domain/150'),
            ('Orange County Public Schools', 'https://www.ocps.net/departments/procurement_services'),
            ('Duval County Public Schools', 'https://dcps.duvalschools.org/Page/9897'),
            ('Pinellas County Schools', 'https://www.pcsb.org/domain/124'),
            ('Polk County Public Schools', 'https://www.polk-fl.net/districtinfo/departments/purchasing/'),
            ('Lee County School District', 'https://www.leeschools.net/our_district/departments/purchasing'),
            ('Volusia County Schools', 'https://www.vcsedu.org/departments/purchasing-services'),
            # Medium districts
            ('Brevard Public Schools', 'https://www.brevardschools.org/domain/56'),
            ('Seminole County Public Schools', 'https://www.scps.k12.fl.us/departments/finance/purchasing'),
            ('Pasco County Schools', 'https://www.pasco.k12.fl.us/purchasing'),
            ('Sarasota County Schools', 'https://www.sarasotacountyschools.net/Page/2419'),
            ('Manatee County School District', 'https://www.manateeschools.net/domain/80'),
            ('Lake County Schools', 'https://www.lake.k12.fl.us/Page/1191'),
            ('Osceola County School District', 'https://www.osceolaschools.net/Page/2148'),
            ('Marion County Public Schools', 'https://www.marionschools.net/domain/75'),
            ('Collier County Public Schools', 'https://www.collierschools.com/domain/76'),
            ('Escambia County School District', 'https://ecsd-fl.schoolloop.com/purchasing'),
            ('St. Johns County School District', 'https://www.stjohns.k12.fl.us/purchasing/'),
            ('Alachua County Public Schools', 'https://www.sbac.edu/Page/1187'),
            ('Leon County Schools', 'https://www.leonschools.net/Page/2080'),
            ('Clay County District Schools', 'https://www.oneclay.net/Page/1392'),
            ('St. Lucie Public Schools', 'https://www.stlucie.k12.fl.us/departments/purchasing'),
            ('Okaloosa County School District', 'https://www.okaloosaschools.com/site/Default.aspx?PageID=1091'),
            ('Santa Rosa County District Schools', 'https://www.santarosa.k12.fl.us/departments/purchasing/'),
            ('Charlotte County Public Schools', 'https://www.yourcharlotteschools.net/Page/720'),
            ('Indian River County School District', 'https://www.indianriverschools.org/departments/purchasing'),
            ('Martin County School District', 'https://www.martinschools.org/domain/92'),
            # Smaller districts
            ('Hernando County Schools', 'https://www.hernandoschools.org/domain/69'),
            ('Citrus County Schools', 'https://www.citrusschools.org/departments/purchasing'),
            ('Sumter County Schools', 'https://www.sumter.k12.fl.us/domain/75'),
            ('Flagler County Schools', 'https://flaglerschools.com/departments/purchasing'),
            ('Nassau County School District', 'https://www.nassau.k12.fl.us/Page/320'),
            ('Putnam County School District', 'https://www.putnamschools.org/Page/1104'),
            ('Bay District Schools', 'https://www.bay.k12.fl.us/departments/purchasing'),
            ('Walton County School District', 'https://www.walton.k12.fl.us/Page/1129'),
            ('Monroe County School District', 'https://www.keysschools.com/domain/75'),
            ('Highlands County School District', 'https://www.highlands.k12.fl.us/Page/1149'),
        ]

        for district_name, url in school_districts:
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    rfps = self._parse_school_district_page(soup, district_name, url)
                    results.extend(rfps)
            except Exception as e:
                logger.debug(f"Error scraping {district_name}: {e}")

        return results

    def _parse_school_district_page(self, soup: BeautifulSoup, district_name: str, base_url: str) -> List[Dict]:
        """Parse a school district procurement page."""
        results = []

        # School districts often use various CMS systems, so try multiple approaches

        # Look for bid/RFP links
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Filter for procurement-related links
            keywords = ['rfp', 'rfq', 'itb', 'itn', 'bid', 'solicitation', 'procurement', 'proposal', 'quote']
            if any(kw in href.lower() or kw in text.lower() for kw in keywords):
                if text and len(text) > 10 and len(text) < 300:
                    # Skip navigation links
                    skip_words = ['click here', 'read more', 'learn more', 'view all', 'back to', 'home', 'menu']
                    if any(skip in text.lower() for skip in skip_words):
                        continue

                    is_relevant, score, category = self.calculate_relevance(text)
                    full_url = href if href.startswith('http') else urljoin(base_url, href)

                    results.append({
                        'title': text,
                        'description': '',
                        'solicitation_number': None,
                        'rfp_type': 'RFP',
                        'category': category,
                        'agency_name': district_name,
                        'posted_date': datetime.now().isoformat(),
                        'due_date': None,
                        'source_url': full_url,
                        'source_portal': 'school_district',
                        'is_relevant': is_relevant,
                        'relevance_score': score
                    })

        # Try to find tables with bids
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows[:30]:
                cells = row.find_all('td')
                if len(cells) >= 1:
                    title_cell = cells[0]
                    link = title_cell.find('a')
                    title = link.get_text(strip=True) if link else title_cell.get_text(strip=True)

                    if title and len(title) > 10:
                        is_relevant, score, category = self.calculate_relevance(title)
                        url = base_url
                        if link and link.get('href'):
                            href = link.get('href')
                            url = href if href.startswith('http') else urljoin(base_url, href)

                        results.append({
                            'title': title,
                            'description': '',
                            'solicitation_number': None,
                            'rfp_type': 'RFP',
                            'category': category,
                            'agency_name': district_name,
                            'posted_date': datetime.now().isoformat(),
                            'due_date': None,
                            'source_url': url,
                            'source_portal': 'school_district',
                            'is_relevant': is_relevant,
                            'relevance_score': score
                        })

        # Also look for list items that might be bids
        list_items = soup.find_all('li')
        for li in list_items:
            link = li.find('a')
            if link:
                text = link.get_text(strip=True)
                href = link.get('href', '')

                keywords = ['rfp', 'rfq', 'itb', 'itn', 'bid', 'solicitation']
                if any(kw in text.lower() or kw in href.lower() for kw in keywords):
                    if len(text) > 10 and len(text) < 300:
                        is_relevant, score, category = self.calculate_relevance(text)
                        full_url = href if href.startswith('http') else urljoin(base_url, href)

                        results.append({
                            'title': text,
                            'description': '',
                            'solicitation_number': None,
                            'rfp_type': 'RFP',
                            'category': category,
                            'agency_name': district_name,
                            'posted_date': datetime.now().isoformat(),
                            'due_date': None,
                            'source_url': full_url,
                            'source_portal': 'school_district',
                            'is_relevant': is_relevant,
                            'relevance_score': score
                        })

        # Look for divs with bid-related classes
        bid_divs = soup.find_all('div', class_=lambda x: x and any(kw in x.lower() for kw in ['bid', 'rfp', 'solicitation']))
        for div in bid_divs:
            title_elem = div.find('h3') or div.find('h4') or div.find('a') or div.find('strong')
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 10:
                    is_relevant, score, category = self.calculate_relevance(title)
                    url = base_url
                    link = div.find('a')
                    if link and link.get('href'):
                        href = link.get('href')
                        url = href if href.startswith('http') else urljoin(base_url, href)

                    results.append({
                        'title': title,
                        'description': '',
                        'solicitation_number': None,
                        'rfp_type': 'RFP',
                        'category': category,
                        'agency_name': district_name,
                        'posted_date': datetime.now().isoformat(),
                        'due_date': None,
                        'source_url': url,
                        'source_portal': 'school_district',
                        'is_relevant': is_relevant,
                        'relevance_score': score
                    })

        return results[:30]  # Limit per district

    def scrape_quick_quotes(self, max_results: int = 100) -> List[Dict]:
        """
        Scrape quick quote and small purchase opportunities.
        These are faster-turnaround opportunities that don't require full RFP responses:
        - Quotes (RFQ) - typically 3-7 day response
        - Informal bids - often same day or 24-48 hours
        - Micro-purchases - under threshold, immediate
        - Emergency procurements - urgent needs
        """
        results = []

        logger.info("Scraping Quick Quote and Small Purchase opportunities...")

        # Quick quote keywords to look for
        quick_keywords = [
            'quote', 'quotation', 'rfq', 'request for quote',
            'informal bid', 'informal quote', 'quick quote',
            'micro-purchase', 'micropurchase', 'small purchase',
            'emergency', 'urgent', 'expedited',
            'sole source', 'single source',
            'price quote', 'competitive quote'
        ]

        # County quick quote pages (many have separate informal bid sections)
        quick_quote_sources = [
            # Counties with dedicated quick quote / informal bid pages
            ('Orange County Quotes', 'https://www.orangecountyfl.net/FinancialServices/InformalQuotes.aspx'),
            ('Hillsborough Quotes', 'https://www.hillsboroughcounty.org/en/residents/property-owners-and-renters/purchasing/informal-quotes'),
            ('Broward Quick Quotes', 'https://www.broward.org/Purchasing/Pages/QuickQuotes.aspx'),
            ('Miami-Dade Small Purchase', 'https://www.miamidade.gov/global/service.page?Mduid_service=ser1510865562461500'),
            ('Palm Beach Quotes', 'https://discover.pbcgov.org/Purchasing/Pages/Quotes.aspx'),
            ('Pinellas Informal Bids', 'https://www.pinellascounty.org/purchase/informalBids.htm'),
            ('Duval Quick Quotes', 'https://www.coj.net/departments/finance/procurement/quick-quotes'),
            ('Lee County Quotes', 'https://www.leegov.com/procurement/quotes'),
            ('Polk County Quotes', 'https://www.polk-county.net/purchasing/informal-quotes'),
            ('Brevard Quotes', 'https://www.brevardfl.gov/CentralServices/Purchasing/Quotes'),
            ('Volusia Quotes', 'https://www.volusia.org/services/government/purchasing-contracts/informal-quotes/'),
            ('Sarasota Quotes', 'https://www.scgov.net/government/procurement-services/informal-quotes'),
            ('Seminole Quotes', 'https://www.seminolecountyfl.gov/departments-services/county-manager/purchasing-contracts/informal-quotes.stml'),
            ('Osceola Quotes', 'https://www.osceola.org/agencies-departments/procurement-services/quotes/'),
            ('Lake County Quotes', 'https://www.lakecountyfl.gov/offices/procurement_services/informal_quotes.aspx'),
            ('Manatee Quotes', 'https://www.mymanatee.org/departments/procurement/quick_quotes'),
            ('Collier Quotes', 'https://www.colliercountyfl.gov/your-government/divisions-a-e/administrative-services/procurement-services/quotes'),
            ('St. Lucie Quotes', 'https://www.stlucieco.gov/departments-services/a-z/purchasing-contracting/quotes'),
            ('Martin Quotes', 'https://www.martin.fl.us/informal-quotes'),
            ('Alachua Quotes', 'https://procurement.alachuacounty.us/quotes'),
            ('Leon Quotes', 'https://cms.leoncountyfl.gov/coadmin/Purchasing/Informal-Quotes'),
            ('Escambia Quotes', 'https://myescambia.com/our-services/purchasing/informal-quotes'),
            ('Bay Quotes', 'https://www.baycountyfl.gov/182/Informal-Quotes'),
            ('Marion Quotes', 'https://www.marioncountyfl.org/departments-agencies/purchasing-contracts/quotes'),
            ('Pasco Quotes', 'https://www.pascocountyfl.net/177/Informal-Quotes'),
        ]

        for source_name, url in quick_quote_sources:
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    agency_name = source_name.replace(' Quotes', '').replace(' Quick Quotes', '').replace(' Informal Bids', '').replace(' Small Purchase', '')

                    # Look for quote-related links and content
                    quotes = self._parse_quick_quote_page(soup, agency_name, url, quick_keywords)
                    results.extend(quotes)

            except Exception as e:
                logger.debug(f"Error scraping {source_name}: {e}")

        # Also search existing portal results for quick-response indicators
        # Look through regular bids for urgency keywords
        for source_name, url in quick_quote_sources[:10]:  # Sample from main portals
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    text_content = soup.get_text().lower()

                    # Check if page mentions quotes or quick turnaround
                    if any(kw in text_content for kw in quick_keywords):
                        agency_name = source_name.replace(' Quotes', '')
                        quotes = self._parse_quick_quote_page(soup, agency_name, url, quick_keywords)
                        results.extend(quotes)

            except Exception as e:
                logger.debug(f"Error checking {source_name} for quotes: {e}")

        return results

    def _parse_quick_quote_page(self, soup: BeautifulSoup, agency_name: str, base_url: str, quick_keywords: List[str]) -> List[Dict]:
        """Parse a page for quick quote opportunities."""
        results = []

        # Look for links that might be quotes
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '').lower()
            text = link.get_text(strip=True)
            text_lower = text.lower()

            # Check if this looks like a quote opportunity
            is_quote = any(kw in text_lower or kw in href for kw in quick_keywords)

            if is_quote and text and len(text) > 10 and len(text) < 300:
                # Skip navigation links
                skip_words = ['click here', 'read more', 'learn more', 'view all', 'back to', 'home', 'menu', 'contact']
                if any(skip in text_lower for skip in skip_words):
                    continue

                is_relevant, score, category = self.calculate_relevance(text)
                full_url = link.get('href')
                if not full_url.startswith('http'):
                    full_url = urljoin(base_url, full_url)

                # Determine RFP type based on keywords
                rfp_type = 'Quote'
                if 'emergency' in text_lower or 'urgent' in text_lower:
                    rfp_type = 'Emergency'
                elif 'sole source' in text_lower or 'single source' in text_lower:
                    rfp_type = 'Sole Source'
                elif 'micro' in text_lower:
                    rfp_type = 'Micro-Purchase'
                elif 'rfq' in text_lower:
                    rfp_type = 'RFQ'
                elif 'informal' in text_lower:
                    rfp_type = 'Informal Bid'

                # Estimate response deadline
                response_hours = 72  # Default 3 days for quotes
                if 'emergency' in text_lower or 'urgent' in text_lower:
                    response_hours = 24
                elif 'same day' in text_lower:
                    response_hours = 8
                elif 'micro' in text_lower:
                    response_hours = 24

                results.append({
                    'title': text,
                    'description': '',
                    'solicitation_number': None,
                    'rfp_type': rfp_type,
                    'category': category,
                    'agency_name': agency_name,
                    'posted_date': datetime.now().isoformat(),
                    'due_date': None,
                    'source_url': full_url,
                    'source_portal': 'quick_quote',
                    'is_relevant': is_relevant,
                    'relevance_score': score,
                    'is_quick_response': True,
                    'response_deadline_hours': response_hours
                })

        # Also check tables
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows[:30]:
                cells = row.find_all('td')
                if len(cells) >= 1:
                    cell_text = cells[0].get_text(strip=True)
                    cell_text_lower = cell_text.lower()

                    is_quote = any(kw in cell_text_lower for kw in quick_keywords)

                    if is_quote and cell_text and len(cell_text) > 10:
                        link = cells[0].find('a')
                        url = base_url
                        if link and link.get('href'):
                            href = link.get('href')
                            url = href if href.startswith('http') else urljoin(base_url, href)

                        is_relevant, score, category = self.calculate_relevance(cell_text)

                        results.append({
                            'title': cell_text,
                            'description': '',
                            'solicitation_number': None,
                            'rfp_type': 'Quote',
                            'category': category,
                            'agency_name': agency_name,
                            'posted_date': datetime.now().isoformat(),
                            'due_date': None,
                            'source_url': url,
                            'source_portal': 'quick_quote',
                            'is_relevant': is_relevant,
                            'relevance_score': score,
                            'is_quick_response': True,
                            'response_deadline_hours': 72
                        })

        return results[:20]  # Limit per source

    def scrape_florida_bids_direct(self) -> List[Dict]:
        """
        Scrape direct from Florida county bid pages.
        This covers counties that don't use major procurement platforms.
        """
        results = []

        # Direct county bid pages
        county_bid_urls = [
            # Original 10 counties
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
            # Additional counties
            ('Escambia County', 'https://myescambia.com/our-services/purchasing/current-bids'),
            ('Santa Rosa County', 'https://www.santarosa.fl.gov/bids.aspx'),
            ('Bay County', 'https://www.baycountyfl.gov/181/Current-Bids'),
            ('Okaloosa County', 'https://www.myokaloosa.com/purchasing/bids'),
            ('Walton County', 'https://www.co.walton.fl.us/195/Current-Bids'),
            ('Jackson County', 'https://www.jacksoncountyfl.gov/departments/purchasing'),
            ('Gadsden County', 'https://www.gadsdencountyfl.gov/purchasing'),
            ('Wakulla County', 'https://www.mywakulla.com/government/purchasing'),
            ('Jefferson County', 'https://www.jeffersoncountyfl.gov/purchasing'),
            ('Madison County', 'https://www.madisoncountyfl.com/purchasing'),
            ('Taylor County', 'https://www.taylorcountygov.com/purchasing'),
            ('Suwannee County', 'https://www.suwanneecountyfl.gov/purchasing'),
            ('Columbia County', 'https://www.columbiacountyfla.com/purchasing'),
            ('Baker County', 'https://www.bakercountyfl.org/purchasing'),
            ('Nassau County', 'https://www.nassaucountyfl.com/151/Purchasing'),
            ('Putnam County', 'https://www.putnam-fl.com/purchasing/'),
            ('Flagler County', 'https://www.flaglercounty.gov/government/county-departments/purchasing-division/current-bids'),
            ('St. Johns County', 'https://www.sjcfl.us/Purchasing/CurrentBids.aspx'),
            ('Clay County', 'https://www.claycountygov.com/government/purchasing/current-bids'),
            ('Bradford County', 'https://www.bradfordcountyfl.gov/purchasing'),
            ('Union County', 'https://www.unioncounty-fl.gov/purchasing'),
            ('Gilchrist County', 'https://www.gilchrist.fl.us/purchasing'),
            ('Levy County', 'https://www.levycounty.org/purchasing'),
            ('Dixie County', 'https://www.dixiecounty.org/purchasing'),
            ('Citrus County', 'https://www.citrusbocc.com/purchasing'),
            ('Hernando County', 'https://www.hernandocounty.us/departments/purchasing'),
            ('Pasco County', 'https://www.pascocountyfl.net/176/Purchasing'),
            ('Sumter County', 'https://www.sumtercountyfl.gov/193/Purchasing'),
            ('Lake County', 'https://www.lakecountyfl.gov/offices/procurement_services/current_bids.aspx'),
            ('Orange County', 'https://www.orangecountyfl.net/FinancialServices/Procurement.aspx'),
            ('Osceola County', 'https://www.osceola.org/agencies-departments/procurement-services/bids-and-quotes/'),
            ('Indian River County', 'https://www.ircgov.com/departments/general_services/purchasing/solicitations.htm'),
            ('St. Lucie County', 'https://www.stlucieco.gov/departments-services/a-z/purchasing-contracting/solicitations'),
            ('Martin County', 'https://www.martin.fl.us/current-solicitations'),
            ('Okeechobee County', 'https://www.co.okeechobee.fl.us/purchasing'),
            ('Glades County', 'https://www.gladescountyfl.gov/purchasing'),
            ('Hendry County', 'https://www.hendryfla.net/purchasing/'),
            ('Charlotte County', 'https://www.charlottecountyfl.gov/departments/purchasing/solicitations.html'),
            ('DeSoto County', 'https://www.desotobocc.com/departments/purchasing'),
            ('Hardee County', 'https://www.hardeecounty.net/purchasing'),
            ('Highlands County', 'https://www.highlandsfl.gov/125/Purchasing'),
            ('Manatee County', 'https://www.mymanatee.org/departments/procurement/current_bids'),
            ('Monroe County', 'https://www.monroecounty-fl.gov/411/Current-Solicitations'),
            ('Miami-Dade County', 'https://www.miamidade.gov/global/service.page?Mduid_service=ser1510865562461499'),
            ('Broward County', 'https://www.broward.org/Purchasing/Pages/CurrentSolicitations.aspx'),
            ('Palm Beach County', 'https://discover.pbcgov.org/Purchasing/Pages/default.aspx'),
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
                relevance_score=rfp_data.get('relevance_score', 0),
                is_quick_response=1 if rfp_data.get('is_quick_response') else 0,
                response_deadline_hours=rfp_data.get('response_deadline_hours')
            )

            if rfp_id:
                saved_count += 1
                if rfp_data.get('is_quick_response'):
                    logger.info(f"  + QUICK: {rfp_data['title'][:50]}... ({rfp_data.get('rfp_type', 'Quote')})")
                elif rfp_data.get('is_relevant'):
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
            ('BidNet', self.scrape_bidnet),
            ('MFMP', self.scrape_mfmp),
            ('School Districts', self.scrape_school_districts),
            ('Quick Quotes', self.scrape_quick_quotes),
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
