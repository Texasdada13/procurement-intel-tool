#!/usr/bin/env python
"""
Initialize the database for Procurement Intelligence Tool.
Run this script to set up the database with initial data.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db


def main():
    print("Initializing Procurement Intelligence Tool database...")

    # Initialize database schema
    db.init_database()
    print("Database schema created.")

    # Seed keywords
    db.seed_keywords()
    print("Keywords seeded.")

    # Seed sources
    db.seed_sources()
    print("News sources seeded.")

    print("\nDatabase initialization complete!")
    print(f"Database location: {db.DB_PATH}")


if __name__ == '__main__':
    main()
