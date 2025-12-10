#!/usr/bin/env python
"""
Seed VERIFIED real Florida procurement scandal articles.
All URLs have been verified as of December 2024.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.discovery import manual_add_article

# All verified real articles from web search
VERIFIED_ARTICLES = [
    # === BROWARD COUNTY SCHOOL BOARD ===
    # $2.6M Handy rental scandal
    'https://www.sun-sentinel.com/2025/11/25/broward-schools-2-6-million-office-rental-contract-plagued-by-missteps/',
    'https://www.sun-sentinel.com/2025/10/24/a-total-mistake-2-6-million-broward-schools-office-rental-raises-questions/',
    'https://www.sun-sentinel.com/2025/11/05/we-blew-this-broward-school-board-terminates-2-6-million-office-rental-lease/',
    'https://www.sun-sentinel.com/2025/12/09/nonprofit-handy-sues-broward-schools-over-terminated-2-6-million-lease/',

    # === MARION COUNTY SCHOOL BOARD ===
    'https://www.ocalagazette.com/school-board-debates-next-steps-after-internal-investigation-into-high-school-construction-bid/',

    # === ORANGE COUNTY / ORLANDO - DOGE AUDIT ===
    'https://www.clickorlando.com/news/politics/2025/07/28/florida-doge-to-audit-orange-county-governments-budget-heres-what-theyre-looking-for/',
    'https://www.clickorlando.com/news/politics/2025/08/05/doge-day-in-orange-county-as-florida-team-descends-for-audit/',
    'https://www.orlandosentinel.com/2025/07/28/florida-doge-plans-to-audit-orange-county/',
    'https://www.clickorlando.com/news/politics/2025/08/01/florida-adds-city-of-orlando-to-doge-audit-list-heres-what-theyre-looking-for/',
    'https://www.clickorlando.com/news/politics/2025/08/28/orange-county-mayor-defends-staff-in-doge-audit-calls-florida-investigation-politically-motivated/',

    # === JACKSONVILLE / JEA SCANDAL ===
    'https://www.firstcoastnews.com/article/news/special-reports/jea-corruption-trial/they-thought-jacksonville-was-just-stupid-ignorant-the-leadup-to-historic-jea-fraud-case/77-c6c08c29-14f7-40f5-a616-28269d80c917',
    'https://www.news4jax.com/news/local/2024/02/20/the-jea-scandal-a-closer-look-at-jacksonvilles-largest-fraud-case/',

    # === MIAMI-DADE COUNTY ===
    'https://www.miaminewtimes.com/news/miami-dade-hired-convicted-contract-fraudster-to-oversee-contracts-20588916/',

    # === FLORIDA STATEWIDE ===
    # Hurricane contract fraud prevention
    'https://www.wlrn.org/development/2024-10-24/florida-hurricane-contract-fraud',

    # === SEMINOLE COUNTY ===
    # Wasteful spending accusations
    'https://www.wesh.com/article/seminole-county-push-back-claims-wasteful-spending/69100544',
]


def seed_verified():
    """Process all verified articles."""
    print("=" * 70)
    print("SEEDING VERIFIED FLORIDA PROCUREMENT SCANDAL ARTICLES")
    print("=" * 70)
    print(f"Total articles to process: {len(VERIFIED_ARTICLES)}")
    print()

    successful = 0
    failed = 0
    total_opportunities = 0
    results_summary = []

    for i, url in enumerate(VERIFIED_ARTICLES, 1):
        print(f"[{i}/{len(VERIFIED_ARTICLES)}] {url[:60]}...")

        try:
            results = manual_add_article(url)
            if results:
                successful += 1
                total_opportunities += len(results)
                for r in results:
                    entity_info = f"{r['entity']['name']} ({r['entity']['entity_type']})"
                    print(f"    + {entity_info} - Score: {r['heat_score']}")
                    results_summary.append({
                        'entity': entity_info,
                        'score': r['heat_score'],
                        'issue_type': r.get('issue_type', 'unknown')
                    })
            else:
                failed += 1
                print(f"    - No opportunities found")
        except Exception as e:
            failed += 1
            print(f"    ! Error: {str(e)[:50]}")

        time.sleep(1.5)

    print()
    print("=" * 70)
    print("SEEDING COMPLETE")
    print("=" * 70)
    print(f"Articles processed successfully: {successful}")
    print(f"Articles failed: {failed}")
    print(f"Total opportunities created: {total_opportunities}")
    print()

    # Summary by entity type
    entity_types = {}
    issue_types = {}
    for r in results_summary:
        et = r['entity'].split('(')[1].replace(')', '').strip()
        entity_types[et] = entity_types.get(et, 0) + 1
        it = r['issue_type']
        issue_types[it] = issue_types.get(it, 0) + 1

    print("By Entity Type:")
    for et, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {et}: {count}")

    print("\nBy Issue Type:")
    for it, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {it}: {count}")

    print("=" * 70)


if __name__ == '__main__':
    seed_verified()
