#!/usr/bin/env python3

import sqlite3
import sys


DB_FILENAME = "pauper.db"


def create_tables(cursor):

    # TODO short circuit if tables exist

    cursor.execute( \
        "CREATE TABLE event ( \
            eid INTEGER PRIMARY KEY, \
            date DATE, \
            name TEXT, \
            type TEXT, \
            num_players INTEGER, \
            source TEXT \
        )" \
    )

    cursor.execute( \
        "CREATE TABLE deck ( \
            did INTEGER PRIMARY KEY, \
            date DATE, \
            player TEXT, \
            finish INTEGER, \
            num_players INTEGER, \
            url TEXT, \
            mainboard TEXT, \
            sideboard TEXT, \
            eid INTEGER, \
            FOREIGN KEY (eid) REFERENCES event (eid) \
        )" \
    )


def main():
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    create_tables(cursor)


if __name__ == "__main__":
    main()

