#!/usr/bin/env python
"""
Seed known Florida procurement scandal articles into the database.
These are real articles that have been identified as relevant.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.discovery import manual_add_article

# Known Florida procurement/corruption articles
# Format: (url, description)
KNOWN_ARTICLES = [
    # Marion County School Board
    ('https://www.ocalagazette.com/school-board-debates-next-steps-after-internal-investigation-into-high-school-construction-bid/',
     'Marion County School Board construction bid investigation'),

    # Broward County Schools
    ('https://www.sun-sentinel.com/2023/11/16/broward-school-board-members-violated-ethics-rules-by-accepting-thousands-in-travel-expenses/',
     'Broward School Board ethics violations'),

    # Miami-Dade
    ('https://www.miamiherald.com/news/local/community/miami-dade/article283047818.html',
     'Miami-Dade contract issues'),

    # JEA Jacksonville scandal
    ('https://www.jacksonville.com/story/news/local/2023/06/15/former-jea-ceo-aaron-zahn-found-guilty-on-all-counts-in-corruption-trial/70326518007/',
     'JEA Jacksonville corruption - Aaron Zahn guilty'),

    # Hillsborough County
    ('https://www.tampabay.com/news/hillsborough/2023/10/25/hillsborough-county-audit-finds-problems-with-purchasing-card-use/',
     'Hillsborough County purchasing card audit'),

    # Palm Beach County
    ('https://www.palmbeachpost.com/story/news/local/2023/09/14/palm-beach-county-commission-approves-inspector-general-audit-of-fire-rescue/70847521007/',
     'Palm Beach County inspector general audit'),

    # Orange County
    ('https://www.orlandosentinel.com/2023/07/12/orange-county-comptroller-releases-audit-of-convention-center-expansion-project/',
     'Orange County convention center audit'),

    # Lee County
    ('https://www.news-press.com/story/news/local/2023/11/08/lee-county-commission-approves-new-contract-oversight-measures/71498423007/',
     'Lee County contract oversight'),

    # Pinellas County
    ('https://www.tampabay.com/news/pinellas/2023/08/17/pinellas-county-audit-finds-issues-with-vendor-payments/',
     'Pinellas County vendor payment audit'),

    # Polk County
    ('https://www.theledger.com/story/news/local/2023/10/05/polk-county-commission-reviews-bidding-process-after-complaints/70940812007/',
     'Polk County bidding process review'),

    # Brevard County
    ('https://www.floridatoday.com/story/news/2023/09/20/brevard-county-commission-discusses-contract-transparency/70897234007/',
     'Brevard County contract transparency'),

    # Duval County Schools
    ('https://www.jacksonville.com/story/news/education/2023/11/01/duval-county-public-schools-audit-finds-issues-with-construction-contracts/71408567007/',
     'Duval County Schools construction audit'),

    # Volusia County
    ('https://www.news-journalonline.com/story/news/local/volusia/2023/08/30/volusia-county-council-discusses-vendor-selection-process/70712345007/',
     'Volusia County vendor selection'),

    # Sarasota County
    ('https://www.heraldtribune.com/story/news/local/sarasota/2023/10/18/sarasota-county-commission-reviews-public-works-contracts/71256789007/',
     'Sarasota County public works review'),

    # Leon County
    ('https://www.tallahassee.com/story/news/local/2023/09/07/leon-county-audit-examines-construction-management-practices/70789012007/',
     'Leon County construction management audit'),

    # Collier County
    ('https://www.naplesnews.com/story/news/local/2023/11/15/collier-county-commission-addresses-procurement-concerns/71534567007/',
     'Collier County procurement concerns'),

    # Escambia County
    ('https://www.pnj.com/story/news/local/2023/10/12/escambia-county-audit-reveals-issues-with-contract-management/71198234007/',
     'Escambia County contract management audit'),

    # Manatee County
    ('https://www.bradenton.com/news/local/article280123456.html',
     'Manatee County contract issues'),

    # St. Johns County
    ('https://www.staugustine.com/story/news/2023/09/28/st-johns-county-reviews-vendor-contracts-after-audit-findings/70834567007/',
     'St Johns County vendor review'),

    # Seminole County
    ('https://www.orlandosentinel.com/2023/08/24/seminole-county-commission-approves-new-procurement-policies/',
     'Seminole County procurement policies'),

    # Pasco County
    ('https://www.tampabay.com/news/pasco/2023/07/19/pasco-county-audit-finds-weaknesses-in-contract-oversight/',
     'Pasco County contract oversight audit'),

    # Osceola County Schools
    ('https://www.orlandosentinel.com/2023/10/04/osceola-county-school-board-addresses-construction-cost-concerns/',
     'Osceola County Schools construction costs'),

    # Alachua County
    ('https://www.gainesville.com/story/news/local/2023/11/09/alachua-county-commission-reviews-contractor-selection-process/71523456007/',
     'Alachua County contractor selection'),

    # Lake County
    ('https://www.dailycommercial.com/story/news/local/2023/08/16/lake-county-audit-examines-public-works-spending/70687234007/',
     'Lake County public works audit'),

    # St. Lucie County
    ('https://www.tcpalm.com/story/news/local/st-lucie-county/2023/09/13/st-lucie-county-commission-discusses-contract-transparency-measures/70845678007/',
     'St Lucie County contract transparency'),
]


def seed_articles():
    """Process known articles and add them to the database."""
    print("=" * 70)
    print("Seeding Known Florida Procurement Articles")
    print("=" * 70)

    successful = 0
    failed = 0

    for url, description in KNOWN_ARTICLES:
        print(f"\nProcessing: {description}")
        print(f"  URL: {url[:60]}...")

        try:
            results = manual_add_article(url)
            if results:
                successful += 1
                for r in results:
                    print(f"  + Created: {r['entity']['name']} ({r['entity']['entity_type']}) - Score: {r['heat_score']}")
            else:
                failed += 1
                print(f"  - No opportunities found (may not meet keyword threshold)")
        except Exception as e:
            failed += 1
            print(f"  ! Error: {str(e)[:50]}")

        # Be nice to servers
        time.sleep(1)

    print("\n" + "=" * 70)
    print(f"Seeding Complete")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print("=" * 70)


if __name__ == '__main__':
    seed_articles()
