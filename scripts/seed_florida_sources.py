#!/usr/bin/env python
"""
Seed comprehensive Florida news sources into the database.
Covers all regions of Florida for maximum coverage.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db

# Comprehensive Florida news sources by region
FLORIDA_NEWS_SOURCES = [
    # === SOUTH FLORIDA (Miami-Dade, Broward, Palm Beach) ===
    ('Miami Herald', 'news', 'https://www.miamiherald.com/', 'FL', 'South Florida'),
    ('Sun Sentinel (Fort Lauderdale)', 'news', 'https://www.sun-sentinel.com/', 'FL', 'South Florida'),
    ('Palm Beach Post', 'news', 'https://www.palmbeachpost.com/', 'FL', 'South Florida'),
    ('South Florida Business Journal', 'news', 'https://www.bizjournals.com/southflorida/', 'FL', 'South Florida'),
    ('WPLG Local 10', 'news', 'https://www.local10.com/', 'FL', 'South Florida'),
    ('WSVN 7 News', 'news', 'https://wsvn.com/', 'FL', 'South Florida'),
    ('CBS Miami', 'news', 'https://www.cbsnews.com/miami/', 'FL', 'South Florida'),
    ('NBC 6 South Florida', 'news', 'https://www.nbcmiami.com/', 'FL', 'South Florida'),
    ('Boca Raton News', 'news', 'https://bocanewsnow.com/', 'FL', 'South Florida'),

    # === CENTRAL FLORIDA (Orange, Osceola, Seminole, Lake, Volusia) ===
    ('Orlando Sentinel', 'news', 'https://www.orlandosentinel.com/', 'FL', 'Central Florida'),
    ('Orlando Business Journal', 'news', 'https://www.bizjournals.com/orlando/', 'FL', 'Central Florida'),
    ('WFTV Channel 9', 'news', 'https://www.wftv.com/', 'FL', 'Central Florida'),
    ('WESH 2 News', 'news', 'https://www.wesh.com/', 'FL', 'Central Florida'),
    ('Daytona Beach News-Journal', 'news', 'https://www.news-journalonline.com/', 'FL', 'Central Florida'),
    ('West Orange Times', 'news', 'https://www.orangeobserver.com/', 'FL', 'Central Florida'),
    ('Osceola News-Gazette', 'news', 'https://www.aroundosceola.com/', 'FL', 'Central Florida'),

    # === TAMPA BAY (Hillsborough, Pinellas, Pasco) ===
    ('Tampa Bay Times', 'news', 'https://www.tampabay.com/', 'FL', 'Tampa Bay'),
    ('Tampa Bay Business Journal', 'news', 'https://www.bizjournals.com/tampabay/', 'FL', 'Tampa Bay'),
    ('WTSP 10 Tampa Bay', 'news', 'https://www.wtsp.com/', 'FL', 'Tampa Bay'),
    ('WFLA News Channel 8', 'news', 'https://www.wfla.com/', 'FL', 'Tampa Bay'),
    ('Bay News 9', 'news', 'https://www.baynews9.com/', 'FL', 'Tampa Bay'),
    ('St. Pete Catalyst', 'news', 'https://stpetecatalyst.com/', 'FL', 'Tampa Bay'),
    ('Creative Loafing Tampa Bay', 'news', 'https://www.cltampa.com/', 'FL', 'Tampa Bay'),

    # === NORTH FLORIDA / JACKSONVILLE ===
    ('Florida Times-Union (Jacksonville)', 'news', 'https://www.jacksonville.com/', 'FL', 'North Florida'),
    ('Jacksonville Business Journal', 'news', 'https://www.bizjournals.com/jacksonville/', 'FL', 'North Florida'),
    ('WJXT News4Jax', 'news', 'https://www.news4jax.com/', 'FL', 'North Florida'),
    ('First Coast News', 'news', 'https://www.firstcoastnews.com/', 'FL', 'North Florida'),
    ('Jax Daily Record', 'news', 'https://www.jaxdailyrecord.com/', 'FL', 'North Florida'),
    ('St. Augustine Record', 'news', 'https://www.staugustine.com/', 'FL', 'North Florida'),

    # === NORTH CENTRAL FLORIDA (Alachua, Marion, etc.) ===
    ('Gainesville Sun', 'news', 'https://www.gainesville.com/', 'FL', 'North Central Florida'),
    ('Ocala Gazette', 'news', 'https://www.ocalagazette.com/', 'FL', 'North Central Florida'),
    ('Ocala Star-Banner', 'news', 'https://www.ocala.com/', 'FL', 'North Central Florida'),
    ('WCJB TV20', 'news', 'https://www.wcjb.com/', 'FL', 'North Central Florida'),
    ('Alachua Chronicle', 'news', 'https://alachuachronicle.com/', 'FL', 'North Central Florida'),

    # === TALLAHASSEE / BIG BEND ===
    ('Tallahassee Democrat', 'news', 'https://www.tallahassee.com/', 'FL', 'Big Bend'),
    ('WCTV Tallahassee', 'news', 'https://www.wctv.tv/', 'FL', 'Big Bend'),
    ('WTXL ABC 27', 'news', 'https://www.wtxl.com/', 'FL', 'Big Bend'),
    ('Florida Capital Star', 'news', 'https://floridacapitalstar.com/', 'FL', 'Big Bend'),

    # === PANHANDLE / NORTHWEST FLORIDA ===
    ('Pensacola News Journal', 'news', 'https://www.pnj.com/', 'FL', 'Panhandle'),
    ('Northwest Florida Daily News', 'news', 'https://www.nwfdailynews.com/', 'FL', 'Panhandle'),
    ('Panama City News Herald', 'news', 'https://www.newsherald.com/', 'FL', 'Panhandle'),
    ('WEAR ABC 3', 'news', 'https://weartv.com/', 'FL', 'Panhandle'),
    ('WKRG News 5', 'news', 'https://www.wkrg.com/', 'FL', 'Panhandle'),

    # === SOUTHWEST FLORIDA (Lee, Collier, Charlotte, Sarasota) ===
    ('News-Press (Fort Myers)', 'news', 'https://www.news-press.com/', 'FL', 'Southwest Florida'),
    ('Naples Daily News', 'news', 'https://www.naplesnews.com/', 'FL', 'Southwest Florida'),
    ('Sarasota Herald-Tribune', 'news', 'https://www.heraldtribune.com/', 'FL', 'Southwest Florida'),
    ('Charlotte Sun', 'news', 'https://www.yoursun.com/', 'FL', 'Southwest Florida'),
    ('WINK News', 'news', 'https://www.winknews.com/', 'FL', 'Southwest Florida'),
    ('NBC 2 (WBBH)', 'news', 'https://nbc-2.com/', 'FL', 'Southwest Florida'),
    ('Business Observer (Sarasota)', 'news', 'https://www.businessobserverfl.com/', 'FL', 'Southwest Florida'),

    # === TREASURE COAST (St. Lucie, Martin, Indian River) ===
    ('TC Palm (Treasure Coast)', 'news', 'https://www.tcpalm.com/', 'FL', 'Treasure Coast'),
    ('WPTV News Channel 5', 'news', 'https://www.wptv.com/', 'FL', 'Treasure Coast'),
    ('Vero Beach 32963', 'news', 'https://www.verobeach32963.com/', 'FL', 'Treasure Coast'),

    # === SPACE COAST (Brevard) ===
    ('Florida Today (Brevard)', 'news', 'https://www.floridatoday.com/', 'FL', 'Space Coast'),
    ('Brevard Business News', 'news', 'https://brevardbusinessnews.com/', 'FL', 'Space Coast'),

    # === STATEWIDE / POLITICAL NEWS ===
    ('Florida Politics', 'news', 'https://floridapolitics.com/', 'FL', 'Statewide'),
    ('Florida Phoenix', 'news', 'https://floridaphoenix.com/', 'FL', 'Statewide'),
    ('Florida Trend', 'news', 'https://www.floridatrend.com/', 'FL', 'Statewide'),
    ('Florida Bulldog', 'news', 'https://www.floridabulldog.org/', 'FL', 'Statewide'),
    ('WFSU Public Media', 'news', 'https://news.wfsu.org/', 'FL', 'Statewide'),
    ('WUSF Public Media', 'news', 'https://wusfnews.wusf.usf.edu/', 'FL', 'Statewide'),
    ('WLRN Public Media', 'news', 'https://www.wlrn.org/', 'FL', 'Statewide'),

    # === OFFICIAL GOVERNMENT SOURCES ===
    ('Florida Auditor General', 'audit_portal', 'https://flauditor.gov/', 'FL', 'Official'),
    ('Florida Commission on Ethics', 'ethics_commission', 'https://ethics.state.fl.us/', 'FL', 'Official'),
    ('Florida Office of Inspector General', 'audit_portal', 'https://www.floridaoig.com/', 'FL', 'Official'),
    ('Florida Department of Financial Services', 'audit_portal', 'https://www.myfloridacfo.com/', 'FL', 'Official'),
    ('Florida Grand Jury', 'legal', 'https://www.flcourts.org/', 'FL', 'Official'),
    ('Florida Office of Program Policy Analysis', 'audit_portal', 'https://oppaga.fl.gov/', 'FL', 'Official'),

    # === NATIONAL SOURCES WITH FL COVERAGE ===
    ('Government Technology', 'news', 'https://www.govtech.com/', None, 'National'),
    ('Governing Magazine', 'news', 'https://www.governing.com/', None, 'National'),
    ('Route Fifty', 'news', 'https://www.route-fifty.com/', None, 'National'),
    ('Ballotpedia', 'reference', 'https://ballotpedia.org/', None, 'National'),
]


def seed_sources():
    """Seed all Florida news sources."""
    conn = db.get_connection()
    cursor = conn.cursor()

    count = 0
    for name, source_type, url, state, region in FLORIDA_NEWS_SOURCES:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO sources (name, source_type, url, state)
                VALUES (?, ?, ?, ?)
            ''', (name, source_type, url, state))
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            print(f"Error adding {name}: {e}")

    conn.commit()
    conn.close()
    return count


def main():
    print("=" * 60)
    print("Seeding Florida News Sources")
    print("=" * 60)

    count = seed_sources()

    print(f"Added {count} new news sources")
    print("=" * 60)

    # Print summary by region
    print("\nSources by Region:")
    regions = {}
    for name, source_type, url, state, region in FLORIDA_NEWS_SOURCES:
        regions[region] = regions.get(region, 0) + 1
    for region, count in sorted(regions.items()):
        print(f"  {region}: {count}")


if __name__ == '__main__':
    main()
