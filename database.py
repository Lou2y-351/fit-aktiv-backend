"""
Fit & Aktiv – Datenbankschicht
SQLite Setup, Schema-Erstellung und Seed-Daten
"""

import sqlite3
import os
from flask import g

DATABASE = os.path.join(os.path.dirname(__file__), "fitaktiv.db")


def get_db():
    """Gibt die Datenbankverbindung des aktuellen Request-Kontexts zurück."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row   # Spalten als dict-ähnliche Objekte
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Erstellt alle Tabellen und befüllt sie mit Beispieldaten (falls leer)."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    _create_tables(db)
    _seed(db)
    db.close()


def _create_tables(db):
    db.executescript("""
    -- ── Studios ────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS studios (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT NOT NULL,
        adresse TEXT NOT NULL
    );

    -- ── Räume ──────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS raeume (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        studio_id  INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        kapazitaet INTEGER NOT NULL DEFAULT 20
    );

    -- ── Kurstypen ──────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS kurstypen (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL,
        qualifikation  TEXT NOT NULL  -- Pflichtqualifikation für Trainer
    );

    -- ── Mitarbeiter ────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS mitarbeiter (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT    NOT NULL,
        rolle            TEXT    NOT NULL DEFAULT 'Trainer',
        email            TEXT    UNIQUE,
        passwort         TEXT    DEFAULT 'passwort123',   -- Nur Demo!
        modell           TEXT    NOT NULL DEFAULT 'Vollzeit',  -- Vollzeit / Teilzeit
        qualifikationen  TEXT    NOT NULL DEFAULT '',
        wochenstunden    INTEGER NOT NULL DEFAULT 40,
        max_kurse_woche  INTEGER NOT NULL DEFAULT 20,
        verfuegbar       INTEGER NOT NULL DEFAULT 1,       -- 1 = verfügbar, 0 = krank/abwesend
        mehrere_studios  INTEGER NOT NULL DEFAULT 0        -- 1 = pendelt zwischen Studios
    );

    -- ── Mitarbeiter ↔ Studios (N:M) ────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS mitarbeiter_studios (
        mitarbeiter_id INTEGER NOT NULL REFERENCES mitarbeiter(id) ON DELETE CASCADE,
        studio_id      INTEGER NOT NULL REFERENCES studios(id)     ON DELETE CASCADE,
        PRIMARY KEY (mitarbeiter_id, studio_id)
    );

    -- ── Verfügbarkeiten ────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS verfuegbarkeiten (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        mitarbeiter_id INTEGER NOT NULL REFERENCES mitarbeiter(id) ON DELETE CASCADE,
        wochentag      INTEGER NOT NULL,  -- 0 = Mo, 1 = Di, ..., 4 = Fr
        von            TEXT    NOT NULL,  -- 'HH:MM'
        bis            TEXT    NOT NULL   -- 'HH:MM'
    );

    -- ── Abwesenheiten (Krankmeldungen) ─────────────────────────────────────
    CREATE TABLE IF NOT EXISTS abwesenheiten (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        mitarbeiter_id INTEGER NOT NULL REFERENCES mitarbeiter(id) ON DELETE CASCADE,
        von            TEXT    NOT NULL,  -- 'YYYY-MM-DD'
        bis            TEXT    NOT NULL,
        grund          TEXT    NOT NULL DEFAULT 'Krankheit'
    );

    -- ── Kurse ──────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS kurse (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT    NOT NULL,
        kurstyp_id         INTEGER NOT NULL REFERENCES kurstypen(id),
        datum              TEXT    NOT NULL,  -- 'YYYY-MM-DD'
        uhrzeit            TEXT    NOT NULL,  -- 'HH:MM'
        dauer              INTEGER NOT NULL DEFAULT 60,  -- Minuten
        studio_id          INTEGER NOT NULL REFERENCES studios(id),
        trainer_id         INTEGER          REFERENCES mitarbeiter(id),
        status             TEXT    NOT NULL DEFAULT 'aktiv',  -- aktiv / ausgefallen
        sonderveranstaltung INTEGER NOT NULL DEFAULT 0
    );

    -- ── Mitglieder ─────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS mitglieder (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL
    );

    -- ── Buchungen ──────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS buchungen (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        mitglied_id INTEGER NOT NULL REFERENCES mitglieder(id) ON DELETE CASCADE,
        kurs_id     INTEGER NOT NULL REFERENCES kurse(id)      ON DELETE CASCADE,
        datum       TEXT    NOT NULL,
        status      TEXT    NOT NULL DEFAULT 'aktiv'  -- aktiv / storniert
    );

    -- ── Benachrichtigungen ─────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS benachrichtigungen (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        empfaenger_id INTEGER,   -- NULL = System-Nachricht
        inhalt        TEXT    NOT NULL,
        kanal         TEXT    NOT NULL DEFAULT 'email',  -- email / push / system
        gelesen       INTEGER NOT NULL DEFAULT 0,
        erstellt_am   TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    """)
    db.commit()


def _seed(db):
    """Befüllt die Datenbank mit Beispieldaten – nur wenn noch leer."""
    if db.execute("SELECT COUNT(*) FROM studios").fetchone()[0] > 0:
        return  # Bereits befüllt

    # ── Studios ────────────────────────────────────────────────────────────
    studios_data = [
        ("Studio 01 – Krefeld Mitte",      "Hauptstr. 10, 47798 Krefeld"),
        ("Studio 02 – Krefeld Nord",        "Nordstr. 25, 47809 Krefeld"),
        ("Studio 03 – Krefeld Süd",         "Südring 5, 47803 Krefeld"),
        ("Studio 04 – Krefeld West",        "Westwall 18, 47798 Krefeld"),
        ("Studio 05 – Krefeld Ost",         "Ostwall 7, 47798 Krefeld"),
        ("Studio 06 – Krefeld Uerdingen",   "Uerdinger Str. 42, 47800 Krefeld"),
        ("Studio 07 – Krefeld Bockum",      "Bockumer Str. 15, 47809 Krefeld"),
        ("Studio 08 – Krefeld Hüls",        "Hülser Str. 33, 47839 Krefeld"),
        ("Studio 09 – Krefeld Fischeln",    "Fischelner Str. 8, 47807 Krefeld"),
        ("Studio 10 – Krefeld Oppum",       "Oppumer Str. 22, 47804 Krefeld"),
        ("Studio 11 – Krefeld Linn",        "Linner Str. 11, 47809 Krefeld"),
        ("Studio 12 – Krefeld Gartenstadt", "Gartenstr. 50, 47802 Krefeld"),
        ("Studio 13 – Krefeld Dießem",      "Dießemer Str. 3, 47805 Krefeld"),
        ("Studio 14 – Krefeld Elfrath",     "Elfrather Weg 9, 47800 Krefeld"),
        ("Studio 15 – Krefeld Traar",       "Traarer Str. 17, 47839 Krefeld"),
        ("Studio 16 – Duisburg Zentrum",    "Königstr. 30, 47051 Duisburg"),
        ("Studio 17 – Mönchengladbach",     "Hindenburgstr. 12, 41061 Mönchengladbach"),
        ("Studio 18 – Neuss Innenstadt",    "Breite Str. 5, 41460 Neuss"),
        ("Studio 19 – Viersen",             "Hauptstr. 44, 41747 Viersen"),
        ("Studio 20 – Willich",             "Stadtring 7, 47877 Willich"),
        ("Studio 21 – Kempen",              "Engerstr. 20, 47906 Kempen"),
        ("Studio 22 – Tönisvorst",          "Hochstr. 3, 47918 Tönisvorst"),
    ]
    for name, adresse in studios_data:
        db.execute("INSERT INTO studios (name, adresse) VALUES (?, ?)", (name, adresse))

    # ── Räume für alle 22 Studios ──────────────────────────────────────────
    for studio_id in range(1, 23):
        db.execute("INSERT INTO raeume (studio_id, name, kapazitaet) VALUES (?,?,20)", (studio_id, "Kursraum A"))
        db.execute("INSERT INTO raeume (studio_id, name, kapazitaet) VALUES (?,?,15)", (studio_id, "Kursraum B"))

    # ── Kurstypen ──────────────────────────────────────────────────────────
    # ... keep original code from here down unchanged ...
    # Kurstypen
    kurstypen = [
        ("Yoga",           "Yoga"),
        ("Pilates",        "Pilates"),
        ("Spinning",       "Spinning"),
        ("Krafttraining",  "Krafttraining"),
        ("Functional Fit", "Functional Fit"),
    ]
    for name, quali in kurstypen:
        db.execute("INSERT INTO kurstypen (name, qualifikation) VALUES (?,?)", (name, quali))

    # Mitarbeiter
    mitarbeiter = [
        ("Max Müller",     "Trainer",  "max@fit-aktiv.de",   "Vollzeit", "Yoga, Functional Fit",  40, 20, 1, 1),
        ("Anna Weber",     "Trainerin","anna@fit-aktiv.de",  "Vollzeit", "Spinning, Pilates",      40, 20, 1, 1),
        ("Jonas Klein",    "Coach",    "jonas@fit-aktiv.de", "Vollzeit", "Krafttraining, Functional Fit", 40, 20, 1, 0),
        ("Sara Bauer",     "Trainerin","sara@fit-aktiv.de",  "Vollzeit", "Pilates, Yoga",          40, 20, 1, 1),
        ("Tim Schulz",     "Trainer",  "tim@fit-aktiv.de",   "Teilzeit", "Spinning",               10,  8, 0, 0),
        ("Lisa Hoffmann",  "Trainerin","lisa.h@fit-aktiv.de","Teilzeit", "Yoga, Pilates",          10,  8, 1, 0),
    ]
    for name, rolle, email, modell, quali, std, max_k, verf, mehr in mitarbeiter:
        db.execute("""
            INSERT INTO mitarbeiter
                (name, rolle, email, modell, qualifikationen, wochenstunden, max_kurse_woche, verfuegbar, mehrere_studios)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (name, rolle, email, modell, quali, std, max_k, verf, mehr))

    # Mitarbeiter ↔ Studios
    studio_map = {1:[1,2], 2:[1,2], 3:[1], 4:[1,2,3], 5:[2], 6:[3]}
    for ma_id, studios in studio_map.items():
        for s in studios:
            db.execute("INSERT INTO mitarbeiter_studios VALUES (?,?)", (ma_id, s))

    # Verfügbarkeiten (Mo–Fr, 07:00–20:00 für alle)
    for ma_id in range(1, 7):
        for tag in range(5):
            db.execute(
                "INSERT INTO verfuegbarkeiten (mitarbeiter_id, wochentag, von, bis) VALUES (?,?,?,?)",
                (ma_id, tag, "07:00", "20:00")
            )

    # Kurse (Woche 09.06. – 13.06.2026)
    kurse = [
        ("Yoga Basic",      1, "2026-06-09", "08:00", 60, 1, 1),
        ("Pilates",         2, "2026-06-09", "10:00", 60, 1, 4),
        ("Spinning",        3, "2026-06-10", "09:00", 60, 1, 2),
        ("Yoga Flow",       1, "2026-06-10", "17:00", 60, 2, 2),
        ("Kraft & Fit",     4, "2026-06-11", "11:00", 60, 1, 3),
        ("Functional Fit",  5, "2026-06-12", "08:00", 60, 1, 1),
        ("Spinning Pro",    3, "2026-06-12", "18:00", 60, 2, 5),
        ("Pilates Adv.",    2, "2026-06-13", "12:00", 60, 2, 4),
    ]
    for name, typ_id, datum, uhr, dauer, studio_id, trainer_id in kurse:
        db.execute("""
            INSERT INTO kurse (name, kurstyp_id, datum, uhrzeit, dauer, studio_id, trainer_id, status)
            VALUES (?,?,?,?,?,?,?,'aktiv')
        """, (name, typ_id, datum, uhr, dauer, studio_id, trainer_id))

    # Spinning Pro als ausgefallen markieren (Tim ist krank)
    db.execute("UPDATE kurse SET status='ausgefallen' WHERE name='Spinning Pro'")
    db.execute("UPDATE mitarbeiter SET verfuegbar=0 WHERE name='Tim Schulz'")

    # Beispiel-Mitglieder
    mitglieder = [
        ("Klaus Schmidt", "klaus@email.de"),
        ("Maria Braun",   "maria@email.de"),
        ("Peter Lange",   "peter@email.de"),
    ]
    for name, email in mitglieder:
        db.execute("INSERT INTO mitglieder (name, email) VALUES (?,?)", (name, email))

    # Beispiel-Buchungen
    for mitglied_id in [1, 2, 3]:
        db.execute(
            "INSERT INTO buchungen (mitglied_id, kurs_id, datum, status) VALUES (?,1,'2026-06-09','aktiv')",
            (mitglied_id,)
        )

    # Beispiel-Benachrichtigungen
    db.execute("INSERT INTO benachrichtigungen (empfaenger_id, inhalt, kanal, gelesen) VALUES (NULL,'Krankmeldung: Tim Schulz (Krankheit). 1 Kurs betroffen.','system',0)")
    db.execute("INSERT INTO benachrichtigungen (empfaenger_id, inhalt, kanal, gelesen) VALUES (NULL,'Spinning Pro am 12.06.2026 ausgefallen. 0 Mitglieder informiert.','system',0)")
    db.execute("INSERT INTO benachrichtigungen (empfaenger_id, inhalt, kanal, gelesen) VALUES (1,'Neue Kurszuweisung: Yoga Basic am 2026-06-09 um 08:00.','email',1)")

    db.commit()
    print("✅ Datenbank initialisiert mit Beispieldaten.")
