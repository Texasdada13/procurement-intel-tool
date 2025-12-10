#!/usr/bin/env python
"""
Run comprehensive Florida-wide discovery.
Searches across all major Florida regions for procurement opportunities.
"""

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db
from src.discovery import DiscoveryEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_comprehensive_florida_queries():
    """Get comprehensive Florida-wide search queries."""
    queries = []

    # General statewide searches
    statewide_terms = [
        'Florida county procurement violation',
        'Florida school board bid rigging',
        'Florida county audit findings',
        'Florida city contract scandal',
        'Florida government corruption investigation',
        'Florida inspector general report',
        'Florida county budget mismanagement',
        'Florida school district construction',
        'Florida grand jury government',
        'Florida ethics commission violation',
        'Florida auditor general findings',
        'Florida municipal corruption',
        'Florida public works scandal',
        'Florida construction contract fraud',
        'Florida vendor kickback',
        'Florida no-bid contract controversy',
        'Florida change order abuse',
        'Florida whistleblower government',
        'Florida FDLE investigation government',
        'Florida FBI public corruption',
    ]
    queries.extend(statewide_terms)

    # Major metro area searches
    metro_searches = [
        # South Florida
        'Miami-Dade County procurement scandal',
        'Broward County bid rigging',
        'Palm Beach County contract fraud',
        'Miami city corruption investigation',
        'Fort Lauderdale contract scandal',
        # Central Florida
        'Orange County Florida procurement',
        'Orlando city contract investigation',
        'Seminole County audit findings',
        'Osceola County bid rigging',
        # Tampa Bay
        'Hillsborough County procurement scandal',
        'Tampa city contract fraud',
        'Pinellas County audit findings',
        'Pasco County corruption',
        'St. Petersburg city procurement',
        # Jacksonville
        'Duval County procurement scandal',
        'Jacksonville city contract fraud',
        'JEA scandal investigation',
        # Other major counties
        'Lee County Florida procurement',
        'Polk County contract scandal',
        'Brevard County bid rigging',
        'Volusia County audit findings',
        'Sarasota County corruption',
        'Collier County contract fraud',
        'Leon County procurement scandal',
        'Escambia County bid rigging',
        'Alachua County contract investigation',
        'Marion County procurement scandal',
        'St. Johns County audit findings',
        'Manatee County corruption',
        'Lake County Florida procurement',
    ]
    queries.extend(metro_searches)

    # School district specific searches
    school_searches = [
        'Miami-Dade schools construction scandal',
        'Broward County schools bid rigging',
        'Hillsborough schools contract fraud',
        'Orange County schools procurement',
        'Duval County schools construction',
        'Palm Beach schools audit findings',
        'Polk County schools contract scandal',
        'Pinellas County schools procurement',
        'Lee County schools construction bid',
        'Brevard County schools contract',
        'Volusia County schools procurement',
        'Pasco County schools bid rigging',
        'Seminole County schools construction',
        'Sarasota County schools contract',
        'Collier County schools procurement',
        'Marion County schools construction investigation',
        'Osceola County schools contract fraud',
        'Manatee County schools bid scandal',
        'St. Lucie County schools procurement',
        'Escambia County schools construction',
    ]
    queries.extend(school_searches)

    # Issue-specific searches
    issue_searches = [
        'Florida school construction cost overrun',
        'Florida county FEMA fraud',
        'Florida hurricane recovery contract scandal',
        'Florida road construction bid rigging',
        'Florida water utility corruption',
        'Florida fire department procurement fraud',
        'Florida sheriff office contract scandal',
        'Florida library construction bid',
        'Florida park construction contract',
        'Florida courthouse construction scandal',
        'Florida jail construction bid rigging',
        'Florida affordable housing contract fraud',
        'Florida IT contract scandal government',
        'Florida consulting contract abuse',
        'Florida legal services contract government',
    ]
    queries.extend(issue_searches)

    return queries


def run_comprehensive_discovery():
    """Run comprehensive Florida-wide discovery."""
    print("=" * 70)
    print("COMPREHENSIVE FLORIDA-WIDE PROCUREMENT INTELLIGENCE DISCOVERY")
    print("=" * 70)

    # Initialize
    engine = DiscoveryEngine()
    queries = get_comprehensive_florida_queries()

    print(f"\nTotal search queries: {len(queries)}")
    print("This may take a while...\n")

    all_results = []
    processed_urls = set()

    for i, query in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] Searching: {query}")

        try:
            urls = engine.search_google_news(query, num_results=5)
            print(f"    Found {len(urls)} articles")

            for url in urls:
                if url in processed_urls:
                    continue
                processed_urls.add(url)

                try:
                    results = engine.process_article(url)
                    if results:
                        all_results.extend(results)
                        for r in results:
                            print(f"    + {r['entity']['name']} ({r['entity']['entity_type']}) - Score: {r['heat_score']}")
                except Exception as e:
                    logger.debug(f"Error processing {url}: {e}")

                # Be nice to servers
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error with query '{query}': {e}")

        # Progress update every 10 queries
        if (i + 1) % 10 == 0:
            print(f"\n--- Progress: {i+1}/{len(queries)} queries, {len(all_results)} opportunities found ---\n")

    print("\n" + "=" * 70)
    print(f"DISCOVERY COMPLETE")
    print(f"Total opportunities found: {len(all_results)}")
    print(f"Total unique articles processed: {len(processed_urls)}")
    print("=" * 70)

    # Summary by entity type
    entity_types = {}
    for r in all_results:
        et = r['entity']['entity_type']
        entity_types[et] = entity_types.get(et, 0) + 1

    print("\nOpportunities by entity type:")
    for et, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {et}: {count}")

    # Summary by issue type
    issue_types = {}
    for r in all_results:
        it = r.get('issue_type', 'unknown')
        issue_types[it] = issue_types.get(it, 0) + 1

    print("\nOpportunities by issue type:")
    for it, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {it}: {count}")

    return all_results


if __name__ == '__main__':
    run_comprehensive_discovery()
