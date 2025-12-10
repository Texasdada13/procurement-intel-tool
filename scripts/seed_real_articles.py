#!/usr/bin/env python
"""
Seed REAL verified Florida procurement scandal articles into the database.
These URLs have been verified to work as of December 2024.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.discovery import manual_add_article

# Verified real Florida procurement/corruption articles
REAL_ARTICLES = [
    # Marion County School Board - VERIFIED WORKING
    'https://www.ocalagazette.com/school-board-debates-next-steps-after-internal-investigation-into-high-school-construction-bid/',

    # JEA Jacksonville Scandal
    'https://www.firstcoastnews.com/article/news/special-reports/jea-corruption-trial/they-thought-jacksonville-was-just-stupid-ignorant-the-leadup-to-historic-jea-fraud-case/77-c6c08c29-14f7-40f5-a616-28269d80c917',
    'https://www.firstcoastnews.com/article/news/local/ex-jea-ceo-aaron-zahn-sentenced-years-in-prison-in-largest-fraud-case-in-jacksonville-history/77-2e69f7ee-691c-4a36-87ef-fd2adf310509',
    'https://www.news4jax.com/news/local/2024/02/20/the-jea-scandal-a-closer-look-at-jacksonvilles-largest-fraud-case/',

    # Miami-Dade
    'https://www.miaminewtimes.com/news/miami-dade-hired-convicted-contract-fraudster-to-oversee-contracts-20588916/',

    # Broward County
    'https://www.floridabulldog.org/2023/10/17-bso-deputies-charged-ppp-fraud-south-floridas-broadest-police-scandal-decades/',

    # Florida Hurricane Contract Fraud
    'https://www.wlrn.org/development/2024-10-24/florida-hurricane-contract-fraud',

    # Federal Bid Rigging Case
    'https://www.justice.gov/archives/opa/pr/three-florida-men-indicted-rigging-bids-and-defrauding-us-military',
]


def seed_real_articles():
    """Process real verified articles."""
    print("=" * 70)
    print("Seeding REAL Florida Procurement Scandal Articles")
    print("=" * 70)

    successful = 0
    failed = 0
    total_opportunities = 0

    for url in REAL_ARTICLES:
        print(f"\nProcessing: {url[:70]}...")

        try:
            results = manual_add_article(url)
            if results:
                successful += 1
                total_opportunities += len(results)
                for r in results:
                    print(f"  + {r['entity']['name']} ({r['entity']['entity_type']}) - Score: {r['heat_score']}")
            else:
                failed += 1
                print(f"  - No opportunities found")
        except Exception as e:
            failed += 1
            print(f"  ! Error: {str(e)[:60]}")

        time.sleep(1.5)

    print("\n" + "=" * 70)
    print(f"Seeding Complete")
    print(f"  Articles processed: {successful}")
    print(f"  Articles failed: {failed}")
    print(f"  Total opportunities created: {total_opportunities}")
    print("=" * 70)


if __name__ == '__main__':
    seed_real_articles()
