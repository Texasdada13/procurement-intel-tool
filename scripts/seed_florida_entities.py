#!/usr/bin/env python
"""
Seed all Florida government entities into the database.
Includes all 67 counties, school boards, and major cities.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db

# All 67 Florida counties with population estimates
FLORIDA_COUNTIES = [
    ('Alachua', 278364),
    ('Baker', 29210),
    ('Bay', 175216),
    ('Bradford', 28520),
    ('Brevard', 606612),
    ('Broward', 1944375),
    ('Calhoun', 14105),
    ('Charlotte', 188910),
    ('Citrus', 154483),
    ('Clay', 219252),
    ('Collier', 393388),
    ('Columbia', 71686),
    ('DeSoto', 38001),
    ('Dixie', 17120),
    ('Duval', 995567),
    ('Escambia', 321555),
    ('Flagler', 117910),
    ('Franklin', 12364),
    ('Gadsden', 44512),
    ('Gilchrist', 18582),
    ('Glades', 13363),
    ('Gulf', 15575),
    ('Hamilton', 14428),
    ('Hardee', 26937),
    ('Hendry', 42022),
    ('Hernando', 197644),
    ('Highlands', 106221),
    ('Hillsborough', 1459762),
    ('Holmes', 19617),
    ('Indian River', 165955),
    ('Jackson', 47414),
    ('Jefferson', 14761),
    ('Lafayette', 8493),
    ('Lake', 393618),
    ('Lee', 760822),
    ('Leon', 293582),
    ('Levy', 42613),
    ('Liberty', 8354),
    ('Madison', 18493),
    ('Manatee', 403253),
    ('Marion', 375908),
    ('Martin', 161000),
    ('Miami-Dade', 2701767),
    ('Monroe', 82874),
    ('Nassau', 91113),
    ('Okaloosa', 213054),
    ('Okeechobee', 42108),
    ('Orange', 1393452),
    ('Osceola', 388656),
    ('Palm Beach', 1492191),
    ('Pasco', 561891),
    ('Pinellas', 959107),
    ('Polk', 725046),
    ('Putnam', 74521),
    ('Santa Rosa', 188564),
    ('Sarasota', 434006),
    ('Seminole', 470856),
    ('St. Johns', 273425),
    ('St. Lucie', 340927),
    ('Sumter', 132420),
    ('Suwannee', 45423),
    ('Taylor', 21569),
    ('Union', 16104),
    ('Volusia', 553543),
    ('Wakulla', 33575),
    ('Walton', 79543),
    ('Washington', 25473),
]

# Major Florida cities (population > 50,000)
FLORIDA_CITIES = [
    ('Jacksonville', 'Duval', 949611),
    ('Miami', 'Miami-Dade', 442241),
    ('Tampa', 'Hillsborough', 384959),
    ('Orlando', 'Orange', 307573),
    ('St. Petersburg', 'Pinellas', 258308),
    ('Hialeah', 'Miami-Dade', 223109),
    ('Port St. Lucie', 'St. Lucie', 204851),
    ('Cape Coral', 'Lee', 194016),
    ('Tallahassee', 'Leon', 196169),
    ('Fort Lauderdale', 'Broward', 182760),
    ('Pembroke Pines', 'Broward', 171178),
    ('Hollywood', 'Broward', 153067),
    ('Gainesville', 'Alachua', 141085),
    ('Miramar', 'Broward', 134721),
    ('Coral Springs', 'Broward', 134394),
    ('Clearwater', 'Pinellas', 117292),
    ('Miami Gardens', 'Miami-Dade', 111640),
    ('Palm Bay', 'Brevard', 119760),
    ('Pompano Beach', 'Broward', 112046),
    ('West Palm Beach', 'Palm Beach', 111398),
    ('Lakeland', 'Polk', 112641),
    ('Davie', 'Broward', 105691),
    ('Boca Raton', 'Palm Beach', 97422),
    ('Sunrise', 'Broward', 97335),
    ('Deltona', 'Volusia', 95027),
    ('Plantation', 'Broward', 94580),
    ('Fort Myers', 'Lee', 92245),
    ('Deerfield Beach', 'Broward', 86859),
    ('Palm Coast', 'Flagler', 91875),
    ('Melbourne', 'Brevard', 86426),
    ('Boynton Beach', 'Palm Beach', 80380),
    ('Largo', 'Pinellas', 84666),
    ('Kissimmee', 'Osceola', 79226),
    ('Homestead', 'Miami-Dade', 78546),
    ('Doral', 'Miami-Dade', 74259),
    ('Tamarac', 'Broward', 71897),
    ('Delray Beach', 'Palm Beach', 69451),
    ('Daytona Beach', 'Volusia', 68866),
    ('Weston', 'Broward', 68388),
    ('North Port', 'Sarasota', 74793),
    ('Wellington', 'Palm Beach', 65242),
    ('North Miami', 'Miami-Dade', 62468),
    ('Jupiter', 'Palm Beach', 65791),
    ('Ocala', 'Marion', 63591),
    ('Port Orange', 'Volusia', 63815),
    ('Margate', 'Broward', 58712),
    ('Coconut Creek', 'Broward', 57833),
    ('Sanford', 'Seminole', 60926),
    ('Sarasota', 'Sarasota', 57738),
    ('Pensacola', 'Escambia', 54312),
    ('Bradenton', 'Manatee', 55437),
    ('St. Cloud', 'Osceola', 53889),
    ('Winter Haven', 'Polk', 51934),
    ('Apopka', 'Orange', 57513),
    ('Altamonte Springs', 'Seminole', 51012),
]

# Special districts and authorities
SPECIAL_DISTRICTS = [
    ('South Florida Water Management District', 'water_district', None),
    ('Southwest Florida Water Management District', 'water_district', None),
    ('St. Johns River Water Management District', 'water_district', None),
    ('Suwannee River Water Management District', 'water_district', None),
    ('Northwest Florida Water Management District', 'water_district', None),
    ('Florida Department of Transportation', 'state_agency', None),
    ('Florida Turnpike Enterprise', 'state_agency', None),
    ('JEA (Jacksonville)', 'utility', 'Duval'),
    ('Orlando Utilities Commission', 'utility', 'Orange'),
    ('Tampa Electric Company', 'utility', 'Hillsborough'),
    ('Florida Power & Light', 'utility', None),
    ('Reedy Creek Improvement District', 'special_district', 'Orange'),
    ('Central Florida Expressway Authority', 'authority', 'Orange'),
    ('Tampa-Hillsborough Expressway Authority', 'authority', 'Hillsborough'),
    ('Miami-Dade Expressway Authority', 'authority', 'Miami-Dade'),
    ('Greater Orlando Aviation Authority', 'authority', 'Orange'),
    ('Hillsborough Area Regional Transit', 'transit', 'Hillsborough'),
    ('Miami-Dade Transit', 'transit', 'Miami-Dade'),
    ('Jacksonville Transportation Authority', 'transit', 'Duval'),
    ('Broward County Transit', 'transit', 'Broward'),
    ('Palm Tran', 'transit', 'Palm Beach'),
]


def seed_counties():
    """Seed all Florida counties."""
    print("Seeding Florida counties...")
    count = 0
    for name, population in FLORIDA_COUNTIES:
        db.create_entity(
            name=name,
            entity_type='county',
            state='FL',
            county=name,
            population=population
        )
        count += 1
    print(f"  Added {count} counties")
    return count


def seed_school_boards():
    """Seed all Florida school boards (one per county)."""
    print("Seeding Florida school boards...")
    count = 0
    for name, population in FLORIDA_COUNTIES:
        db.create_entity(
            name=f"{name} County",
            entity_type='school_board',
            state='FL',
            county=name,
            population=population
        )
        count += 1
    print(f"  Added {count} school boards")
    return count


def seed_cities():
    """Seed major Florida cities."""
    print("Seeding Florida cities...")
    count = 0
    for name, county, population in FLORIDA_CITIES:
        db.create_entity(
            name=name,
            entity_type='city',
            state='FL',
            county=county,
            population=population
        )
        count += 1
    print(f"  Added {count} cities")
    return count


def seed_special_districts():
    """Seed special districts and authorities."""
    print("Seeding special districts and authorities...")
    count = 0
    for name, entity_type, county in SPECIAL_DISTRICTS:
        db.create_entity(
            name=name,
            entity_type=entity_type,
            state='FL',
            county=county
        )
        count += 1
    print(f"  Added {count} special districts/authorities")
    return count


def main():
    print("=" * 60)
    print("Seeding Florida Government Entities")
    print("=" * 60)

    total = 0
    total += seed_counties()
    total += seed_school_boards()
    total += seed_cities()
    total += seed_special_districts()

    print("=" * 60)
    print(f"Total entities added: {total}")
    print("=" * 60)


if __name__ == '__main__':
    main()
