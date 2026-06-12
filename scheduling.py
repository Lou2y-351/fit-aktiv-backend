"""
Fit & Aktiv – Scheduling-Logik
Konfliktprüfung, Vertretungssuche, Fahrtzeit-Puffer
"""

from datetime import datetime, timedelta


FAHRTZEIT_MINUTEN = 60  # Puffer zwischen Studios laut Anforderung A14


def pruefe_konflikte(db, trainer_id, datum, uhrzeit, dauer, studio_id,
                     kurs_id_ausschliessen=None):
    """
    Prüft ob ein Trainer zum angegebenen Zeitpunkt verfügbar ist.

    Prüft:
    1. Doppelbelegung (gleicher Kurs zur gleichen Zeit)
    2. Fahrtzeit (1h Puffer bei Studioübergreifendem Einsatz)
    3. Wochenkontingent nicht überschritten

    Gibt Liste von Konfliktbeschreibungen zurück (leer = kein Konflikt).
    """
    konflikte = []

    kurs_start = datetime.strptime(f"{datum} {uhrzeit}", "%Y-%m-%d %H:%M")
    kurs_ende  = kurs_start + timedelta(minutes=dauer)

    # Alle Kurse des Trainers an diesem Tag laden
    query = """
        SELECT k.*, s.id AS studio_id_val
        FROM kurse k
        JOIN studios s ON s.id = k.studio_id
        WHERE k.trainer_id=? AND k.datum=? AND k.status='aktiv'
    """
    params = [trainer_id, datum]
    if kurs_id_ausschliessen:
        query += " AND k.id != ?"
        params.append(kurs_id_ausschliessen)

    bestehende = db.execute(query, params).fetchall()

    for k in bestehende:
        k_start = datetime.strptime(f"{k['datum']} {k['uhrzeit']}", "%Y-%m-%d %H:%M")
        k_ende  = k_start + timedelta(minutes=k["dauer"])

        # Verschiedene Studios → Fahrtzeit-Puffer einrechnen
        if k["studio_id_val"] != studio_id:
            k_start_puffer = k_start - timedelta(minutes=FAHRTZEIT_MINUTEN)
            k_ende_puffer  = k_ende  + timedelta(minutes=FAHRTZEIT_MINUTEN)
        else:
            k_start_puffer = k_start
            k_ende_puffer  = k_ende

        # Zeitüberschneidung prüfen
        if kurs_start < k_ende_puffer and kurs_ende > k_start_puffer:
            if k["studio_id_val"] != studio_id:
                konflikte.append(
                    f"Dieser Trainer ist zu diesem Zeitpunkt bereits eingeteilt "
                    f"({k['name']} um {k['uhrzeit']}) und hat keine ausreichende "
                    f"Fahrtzeit (1 Stunde Puffer benötigt)."
                )
            else:
                konflikte.append(
                    f"Dieser Trainer ist zu diesem Zeitpunkt bereits eingeteilt "
                    f"({k['name']} um {k['uhrzeit']})."
                )

    # Wochenkontingent prüfen
    ma = db.execute(
        "SELECT max_kurse_woche FROM mitarbeiter WHERE id=?", (trainer_id,)
    ).fetchone()
    if ma:
        # Montag dieser Woche berechnen
        kurs_dt   = datetime.strptime(datum, "%Y-%m-%d")
        mo_dieser_woche = kurs_dt - timedelta(days=kurs_dt.weekday())
        fr_dieser_woche = mo_dieser_woche + timedelta(days=4)

        kurse_woche = db.execute("""
            SELECT COUNT(*) FROM kurse
            WHERE trainer_id=? AND status='aktiv'
              AND datum BETWEEN ? AND ?
        """, (
            trainer_id,
            mo_dieser_woche.strftime("%Y-%m-%d"),
            fr_dieser_woche.strftime("%Y-%m-%d")
        )).fetchone()[0]

        if kurs_id_ausschliessen:
            pass  # Beim Update zählt der aktuelle Kurs nicht dazu
        else:
            if kurse_woche >= ma["max_kurse_woche"]:
                konflikte.append(
                    f"Wochenkontingent erreicht: Trainer hat bereits "
                    f"{kurse_woche}/{ma['max_kurse_woche']} Kurse diese Woche."
                )

    return konflikte


def finde_ersatztrainer(db, kurs: dict) -> list:
    """
    Findet alle geeigneten Ersatztrainer für einen ausgefallenen Kurs.

    Prüft für jeden verfügbaren Trainer:
    1. Verfügbarkeit (nicht krank)
    2. Qualifikation für den Kurstyp
    3. Wochenkontingent nicht überschritten
    4. Keine Zeitkonflikte (inkl. Fahrtzeit)
    5. Ist für das jeweilige Studio eingeplant

    Gibt sortierte Liste zurück (weniger Kurse = bevorzugt).
    """
    benoetigte_quali = kurs.get("benoetigte_quali", "")
    datum     = kurs["datum"]
    uhrzeit   = kurs["uhrzeit"]
    dauer     = kurs.get("dauer", 60)
    studio_id = kurs.get("studio_id")

    # Alle verfügbaren Trainer laden
    alle_trainer = db.execute("""
        SELECT m.*, GROUP_CONCAT(ms.studio_id) AS studio_ids
        FROM mitarbeiter m
        LEFT JOIN mitarbeiter_studios ms ON ms.mitarbeiter_id = m.id
        WHERE m.verfuegbar = 1
        GROUP BY m.id
    """).fetchall()

    kandidaten = []

    for trainer in alle_trainer:
        ma = dict(trainer)
        studios_des_trainers = [
            int(x) for x in (ma.get("studio_ids") or "").split(",") if x
        ]

        # 1. Qualifikation prüfen
        if benoetigte_quali and benoetigte_quali not in ma["qualifikationen"]:
            continue

        # 2. Prüfen ob Trainer für dieses Studio vorgesehen ist
        if studio_id and studio_id not in studios_des_trainers:
            continue

        # 3. Konflikte prüfen (Doppelbelegung + Fahrtzeit + Kontingent)
        konflikte = pruefe_konflikte(
            db, ma["id"], datum, uhrzeit, dauer, studio_id,
            kurs_id_ausschliessen=kurs.get("id")
        )
        if konflikte:
            continue

        # 4. Kurse dieser Woche zählen (für Sortierung)
        kurs_dt = datetime.strptime(datum, "%Y-%m-%d")
        mo = kurs_dt - timedelta(days=kurs_dt.weekday())
        fr = mo + timedelta(days=4)
        kurse_woche = db.execute("""
            SELECT COUNT(*) FROM kurse
            WHERE trainer_id=? AND status='aktiv' AND datum BETWEEN ? AND ?
        """, (ma["id"], mo.strftime("%Y-%m-%d"), fr.strftime("%Y-%m-%d"))).fetchone()[0]

        kandidaten.append({
            "id":              ma["id"],
            "name":            ma["name"],
            "rolle":           ma["rolle"],
            "modell":          ma["modell"],
            "qualifikationen": ma["qualifikationen"],
            "kurse_diese_woche": kurse_woche,
            "max_kurse_woche": ma["max_kurse_woche"],
            "studios":         studios_des_trainers,
        })

    # Sortierung: Trainer mit wenigsten Kursen zuerst (ausgewogene Verteilung)
    kandidaten.sort(key=lambda x: x["kurse_diese_woche"])
    return kandidaten
