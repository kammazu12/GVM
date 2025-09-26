#!/usr/bin/env python3
# Adds latitude and longitude columns to the cargo_location table if missing.
import sqlite3
import os
import argparse

# Default candidates (in order) to look for the SQLite DB file
ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_CANDIDATES = [
    os.path.join(ROOT, 'app.db'),
    os.path.join(ROOT, 'instances', 'app.db'),
    os.path.join(ROOT, 'instance', 'app.db'),
]


def choose_db_path(cli_path: str | None) -> str | None:
    """Return the first existing DB path based on CLI override or defaults.

    If cli_path is provided and exists, return it. Otherwise return the first
    candidate that exists. If none exist return None.
    """
    if cli_path:
        if os.path.exists(cli_path):
            return cli_path
        return None
    for p in DEFAULT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

def table_has_column(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def main():
    parser = argparse.ArgumentParser(description='Add latitude/longitude to cargo_location table')
    parser.add_argument('--db', help='Path to SQLite DB file (overrides default search)')
    args = parser.parse_args()

    db_path = choose_db_path(args.db)
    if not db_path:
        print('Database not found. Searched:')
        for c in DEFAULT_CANDIDATES:
            print('  -', c)
        if args.db:
            print('\nYou passed --db but that file does not exist:', args.db)
        print('\nRun this script with --db <path-to-db> or place your DB at one of the locations above.')
        return

    print('Using database:', db_path)
    conn = sqlite3.connect(db_path)
    try:
        added = False
        if not table_has_column(conn, 'cargo_location', 'latitude'):
            print('Adding cargo_location.latitude')
            conn.execute("ALTER TABLE cargo_location ADD COLUMN latitude REAL")
            added = True
        else:
            print('cargo_location.latitude already exists')

        if not table_has_column(conn, 'cargo_location', 'longitude'):
            print('Adding cargo_location.longitude')
            conn.execute("ALTER TABLE cargo_location ADD COLUMN longitude REAL")
            added = True
        else:
            print('cargo_location.longitude already exists')

        if added:
            conn.commit()
            print('Done — columns added.')
        else:
            print('No changes needed.')
    except Exception as e:
        print('Error:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
