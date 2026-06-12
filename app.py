"""
Fit & Aktiv – Kursplanungs- und Mitarbeiterverwaltungssystem
Flask REST API – Hauptanwendung
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from database import init_db, get_db
import scheduling

app = Flask(__name__)
CORS(app)  # Erlaubt React-Frontend (localhost:5173) den Zugriff

# ─── Datenbank initialisieren ─────────────────────────────────────────────────

@app.before_request
def setup():
    init_db()


# ══════════════════════════════════════════════════════════════════════════════
# STUDIOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/studios", methods=["GET"])
def get_studios():
    db = get_db()
    studios = db.execute("SELECT * FROM studios").fetchall()
    return jsonify([dict(s) for s in studios])


@app.route("/api/studios", methods=["POST"])
def create_studio():
    data = request.get_json()
    db = get_db()
    cur = db.execute(
        "INSERT INTO studios (name, adresse) VALUES (?, ?)",
        (data["name"], data["adresse"])
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, **data}), 201


@app.route("/api/studios/<int:studio_id>", methods=["PUT"])
def update_studio(studio_id):
    data = request.get_json()
    db = get_db()
    db.execute(
        "UPDATE studios SET name=?, adresse=? WHERE id=?",
        (data["name"], data["adresse"], studio_id)
    )
    db.commit()
    return jsonify({"id": studio_id, **data})


@app.route("/api/studios/<int:studio_id>", methods=["DELETE"])
def delete_studio(studio_id):
    db = get_db()
    db.execute("DELETE FROM studios WHERE id=?", (studio_id,))
    db.commit()
    return jsonify({"deleted": studio_id})


# ══════════════════════════════════════════════════════════════════════════════
# KURSTYPEN
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/kurstypen", methods=["GET"])
def get_kurstypen():
    db = get_db()
    typen = db.execute("SELECT * FROM kurstypen").fetchall()
    return jsonify([dict(t) for t in typen])


@app.route("/api/kurstypen", methods=["POST"])
def create_kurstyp():
    data = request.get_json()
    db = get_db()
    cur = db.execute(
        "INSERT INTO kurstypen (name, qualifikation) VALUES (?, ?)",
        (data["name"], data["qualifikation"])
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, **data}), 201


# ══════════════════════════════════════════════════════════════════════════════
# MITARBEITER
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/mitarbeiter", methods=["GET"])
def get_mitarbeiter():
    db = get_db()
    rows = db.execute("""
        SELECT m.*, GROUP_CONCAT(ms.studio_id) AS studio_ids
        FROM mitarbeiter m
        LEFT JOIN mitarbeiter_studios ms ON ms.mitarbeiter_id = m.id
        GROUP BY m.id
    """).fetchall()

    result = []
    for row in rows:
        ma = dict(row)
        ma["studios"] = [int(x) for x in ma["studio_ids"].split(",")] if ma["studio_ids"] else []
        del ma["studio_ids"]
        result.append(ma)
    return jsonify(result)


@app.route("/api/mitarbeiter/<int:ma_id>", methods=["GET"])
def get_mitarbeiter_single(ma_id):
    db = get_db()
    row = db.execute("SELECT * FROM mitarbeiter WHERE id=?", (ma_id,)).fetchone()
    if not row:
        return jsonify({"error": "Nicht gefunden"}), 404
    ma = dict(row)
    studios = db.execute(
        "SELECT studio_id FROM mitarbeiter_studios WHERE mitarbeiter_id=?", (ma_id,)
    ).fetchall()
    ma["studios"] = [s["studio_id"] for s in studios]
    return jsonify(ma)


@app.route("/api/mitarbeiter", methods=["POST"])
def create_mitarbeiter():
    data = request.get_json()
    db = get_db()
    cur = db.execute("""
        INSERT INTO mitarbeiter (name, rolle, email, modell, qualifikationen,
                                 wochenstunden, max_kurse_woche, verfuegbar, mehrere_studios)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        data["name"], data["rolle"], data.get("email", ""),
        data["modell"], data["qualifikationen"],
        data.get("wochenstunden", 40),
        data.get("max_kurse_woche", 20 if data["modell"] == "Vollzeit" else 8),
        1 if len(data.get("studios", [])) > 1 else 0
    ))
    ma_id = cur.lastrowid

    for studio_id in data.get("studios", []):
        db.execute(
            "INSERT INTO mitarbeiter_studios (mitarbeiter_id, studio_id) VALUES (?, ?)",
            (ma_id, studio_id)
        )
    db.commit()
    return jsonify({"id": ma_id, **data}), 201


@app.route("/api/mitarbeiter/<int:ma_id>", methods=["PUT"])
def update_mitarbeiter(ma_id):
    data = request.get_json()
    db = get_db()
    db.execute("""
        UPDATE mitarbeiter SET name=?, rolle=?, email=?, modell=?,
               qualifikationen=?, wochenstunden=?, max_kurse_woche=?, mehrere_studios=?
        WHERE id=?
    """, (
        data["name"], data["rolle"], data.get("email", ""),
        data["modell"], data["qualifikationen"],
        data.get("wochenstunden", 40), data.get("max_kurse_woche", 20),
        1 if len(data.get("studios", [])) > 1 else 0,
        ma_id
    ))
    db.execute("DELETE FROM mitarbeiter_studios WHERE mitarbeiter_id=?", (ma_id,))
    for studio_id in data.get("studios", []):
        db.execute(
            "INSERT INTO mitarbeiter_studios (mitarbeiter_id, studio_id) VALUES (?, ?)",
            (ma_id, studio_id)
        )
    db.commit()
    return jsonify({"id": ma_id, **data})


@app.route("/api/mitarbeiter/<int:ma_id>", methods=["DELETE"])
def delete_mitarbeiter(ma_id):
    db = get_db()
    db.execute("DELETE FROM mitarbeiter WHERE id=?", (ma_id,))
    db.execute("DELETE FROM mitarbeiter_studios WHERE mitarbeiter_id=?", (ma_id,))
    db.commit()
    return jsonify({"deleted": ma_id})


# ── Krankmeldung ──────────────────────────────────────────────────────────────

@app.route("/api/mitarbeiter/<int:ma_id>/krankmelden", methods=["POST"])
def krankmelden(ma_id):
    """
    Markiert einen Trainer als nicht verfügbar und startet die Vertretungssuche.
    Body: { "von": "2026-06-09", "bis": "2026-06-09", "grund": "Krankheit" }
    """
    data = request.get_json()
    db = get_db()

    # Trainer als nicht verfügbar markieren
    db.execute(
        "UPDATE mitarbeiter SET verfuegbar=0 WHERE id=?", (ma_id,)
    )

    # Abwesenheit speichern
    db.execute("""
        INSERT INTO abwesenheiten (mitarbeiter_id, von, bis, grund)
        VALUES (?, ?, ?, ?)
    """, (ma_id, data["von"], data["bis"], data.get("grund", "Krankheit")))

    db.commit()

    # Betroffene Kurse finden (zwischen von und bis)
    betroffene_kurse = db.execute("""
        SELECT k.*, kt.name AS kurstyp_name, s.name AS studio_name
        FROM kurse k
        JOIN kurstypen kt ON kt.id = k.kurstyp_id
        JOIN studios s ON s.id = k.studio_id
        WHERE k.trainer_id=? AND k.datum BETWEEN ? AND ? AND k.status='aktiv'
    """, (ma_id, data["von"], data["bis"])).fetchall()

    # Benachrichtigung anlegen
    trainer = db.execute("SELECT name FROM mitarbeiter WHERE id=?", (ma_id,)).fetchone()
    _create_benachrichtigung(db, None, "system",
        f"Krankmeldung: {trainer['name']} ({data.get('grund','Krankheit')}) "
        f"von {data['von']} bis {data['bis']}. "
        f"{len(betroffene_kurse)} Kurs(e) betroffen.")

    db.commit()

    return jsonify({
        "message": "Krankmeldung gespeichert",
        "betroffene_kurse": [dict(k) for k in betroffene_kurse]
    })


@app.route("/api/mitarbeiter/<int:ma_id>/reaktivieren", methods=["POST"])
def reaktivieren(ma_id):
    db = get_db()
    db.execute("UPDATE mitarbeiter SET verfuegbar=1 WHERE id=?", (ma_id,))
    db.commit()
    trainer = db.execute("SELECT name FROM mitarbeiter WHERE id=?", (ma_id,)).fetchone()
    _create_benachrichtigung(db, None, "system",
        f"{trainer['name']} ist wieder verfügbar.")
    db.commit()
    return jsonify({"message": "Trainer reaktiviert"})


# ── Einsatzplan ───────────────────────────────────────────────────────────────

@app.route("/api/mitarbeiter/<int:ma_id>/einsatzplan", methods=["GET"])
def einsatzplan(ma_id):
    db = get_db()
    kurse = db.execute("""
        SELECT k.*, kt.name AS kurstyp_name, s.name AS studio_name
        FROM kurse k
        JOIN kurstypen kt ON kt.id = k.kurstyp_id
        JOIN studios s ON s.id = k.studio_id
        WHERE k.trainer_id=? AND k.status='aktiv'
        ORDER BY k.datum, k.uhrzeit
    """, (ma_id,)).fetchall()
    return jsonify([dict(k) for k in kurse])


# ── Verfügbarkeiten ───────────────────────────────────────────────────────────

@app.route("/api/mitarbeiter/<int:ma_id>/verfuegbarkeiten", methods=["GET"])
def get_verfuegbarkeiten(ma_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM verfuegbarkeiten WHERE mitarbeiter_id=?", (ma_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/mitarbeiter/<int:ma_id>/verfuegbarkeiten", methods=["POST"])
def set_verfuegbarkeit(ma_id):
    data = request.get_json()
    db = get_db()
    # Existierende für diesen Tag löschen und neu setzen
    db.execute(
        "DELETE FROM verfuegbarkeiten WHERE mitarbeiter_id=? AND wochentag=?",
        (ma_id, data["wochentag"])
    )
    cur = db.execute(
        "INSERT INTO verfuegbarkeiten (mitarbeiter_id, wochentag, von, bis) VALUES (?,?,?,?)",
        (ma_id, data["wochentag"], data["von"], data["bis"])
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "mitarbeiter_id": ma_id, **data}), 201


# ══════════════════════════════════════════════════════════════════════════════
# KURSE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/kurse", methods=["GET"])
def get_kurse():
    db = get_db()
    # Optionale Filter
    trainer_id = request.args.get("trainer_id")
    studio_id  = request.args.get("studio_id")
    datum_von  = request.args.get("von")
    datum_bis  = request.args.get("bis")
    status     = request.args.get("status")

    query = """
        SELECT k.*, kt.name AS kurstyp_name, s.name AS studio_name,
               m.name AS trainer_name
        FROM kurse k
        JOIN kurstypen kt ON kt.id = k.kurstyp_id
        JOIN studios s ON s.id = k.studio_id
        LEFT JOIN mitarbeiter m ON m.id = k.trainer_id
        WHERE 1=1
    """
    params = []
    if trainer_id:
        query += " AND k.trainer_id=?"; params.append(trainer_id)
    if studio_id:
        query += " AND k.studio_id=?";  params.append(studio_id)
    if datum_von:
        query += " AND k.datum >= ?";   params.append(datum_von)
    if datum_bis:
        query += " AND k.datum <= ?";   params.append(datum_bis)
    if status:
        query += " AND k.status=?";     params.append(status)

    query += " ORDER BY k.datum, k.uhrzeit"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/kurse/<int:kurs_id>", methods=["GET"])
def get_kurs(kurs_id):
    db = get_db()
    row = db.execute("""
        SELECT k.*, kt.name AS kurstyp_name, s.name AS studio_name,
               m.name AS trainer_name
        FROM kurse k
        JOIN kurstypen kt ON kt.id = k.kurstyp_id
        JOIN studios s ON s.id = k.studio_id
        LEFT JOIN mitarbeiter m ON m.id = k.trainer_id
        WHERE k.id=?
    """, (kurs_id,)).fetchone()
    if not row:
        return jsonify({"error": "Nicht gefunden"}), 404
    return jsonify(dict(row))


@app.route("/api/kurse", methods=["POST"])
def create_kurs():
    data = request.get_json()
    db = get_db()

    # Konfliktprüfung falls Trainer angegeben
    if data.get("trainer_id"):
        konflikte = scheduling.pruefe_konflikte(
            db, data["trainer_id"], data["datum"],
            data["uhrzeit"], data.get("dauer", 60),
            data.get("studio_id"), kurs_id_ausschliessen=None
        )
        if konflikte:
            return jsonify({"error": "Konflikt erkannt", "konflikte": konflikte}), 409

    cur = db.execute("""
        INSERT INTO kurse (name, kurstyp_id, datum, uhrzeit, dauer,
                           studio_id, trainer_id, status, sonderveranstaltung)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'aktiv', ?)
    """, (
        data["name"], data["kurstyp_id"], data["datum"], data["uhrzeit"],
        data.get("dauer", 60), data["studio_id"],
        data.get("trainer_id"), data.get("sonderveranstaltung", 0)
    ))
    db.commit()

    if data.get("trainer_id"):
        trainer = db.execute(
            "SELECT name FROM mitarbeiter WHERE id=?", (data["trainer_id"],)
        ).fetchone()
        _create_benachrichtigung(db, data["trainer_id"], "email",
            f"Neue Kurszuweisung: {data['name']} am {data['datum']} um {data['uhrzeit']}.")
        db.commit()

    return jsonify({"id": cur.lastrowid, **data}), 201


@app.route("/api/kurse/<int:kurs_id>", methods=["PUT"])
def update_kurs(kurs_id):
    data = request.get_json()
    db = get_db()

    if data.get("trainer_id"):
        konflikte = scheduling.pruefe_konflikte(
            db, data["trainer_id"], data["datum"],
            data["uhrzeit"], data.get("dauer", 60),
            data.get("studio_id"), kurs_id_ausschliessen=kurs_id
        )
        if konflikte:
            return jsonify({"error": "Konflikt erkannt", "konflikte": konflikte}), 409

    db.execute("""
        UPDATE kurse SET name=?, kurstyp_id=?, datum=?, uhrzeit=?, dauer=?,
               studio_id=?, trainer_id=?, status=?, sonderveranstaltung=?
        WHERE id=?
    """, (
        data["name"], data["kurstyp_id"], data["datum"], data["uhrzeit"],
        data.get("dauer", 60), data["studio_id"], data.get("trainer_id"),
        data.get("status", "aktiv"), data.get("sonderveranstaltung", 0),
        kurs_id
    ))
    db.commit()
    return jsonify({"id": kurs_id, **data})


@app.route("/api/kurse/<int:kurs_id>", methods=["DELETE"])
def delete_kurs(kurs_id):
    db = get_db()
    db.execute("DELETE FROM kurse WHERE id=?", (kurs_id,))
    db.commit()
    return jsonify({"deleted": kurs_id})


@app.route("/api/kurse/<int:kurs_id>/ausgefallen", methods=["POST"])
def kurs_ausgefallen(kurs_id):
    """Markiert Kurs als ausgefallen und informiert alle gebuchten Mitglieder."""
    db = get_db()
    db.execute("UPDATE kurse SET status='ausgefallen' WHERE id=?", (kurs_id,))

    kurs = db.execute("""
        SELECT k.*, kt.name AS kurstyp_name
        FROM kurse k JOIN kurstypen kt ON kt.id=k.kurstyp_id
        WHERE k.id=?
    """, (kurs_id,)).fetchone()

    # Alle Mitglieder die diesen Kurs gebucht haben benachrichtigen
    buchungen = db.execute(
        "SELECT mitglied_id FROM buchungen WHERE kurs_id=? AND status='aktiv'",
        (kurs_id,)
    ).fetchall()

    for b in buchungen:
        _create_benachrichtigung(db, b["mitglied_id"], "email",
            f"Kurs ausgefallen: {kurs['name']} am {kurs['datum']} um {kurs['uhrzeit']}.")

    db.commit()
    return jsonify({"message": "Kurs als ausgefallen markiert", "benachrichtigt": len(buchungen)})


# ── Trainer zuweisen ──────────────────────────────────────────────────────────

@app.route("/api/kurse/<int:kurs_id>/trainer", methods=["PUT"])
def trainer_zuweisen(kurs_id):
    """
    Weist einem Kurs einen Trainer zu – mit vollständiger Konfliktprüfung.
    Body: { "trainer_id": 3 }
    """
    data = request.get_json()
    trainer_id = data["trainer_id"]
    db = get_db()

    kurs = db.execute("SELECT * FROM kurse WHERE id=?", (kurs_id,)).fetchone()
    if not kurs:
        return jsonify({"error": "Kurs nicht gefunden"}), 404

    konflikte = scheduling.pruefe_konflikte(
        db, trainer_id, kurs["datum"], kurs["uhrzeit"],
        kurs["dauer"], kurs["studio_id"], kurs_id_ausschliessen=kurs_id
    )
    if konflikte:
        return jsonify({"error": "Dieser Trainer ist zu diesem Zeitpunkt bereits eingeteilt.",
                        "konflikte": konflikte}), 409

    db.execute("UPDATE kurse SET trainer_id=?, status='aktiv' WHERE id=?",
               (trainer_id, kurs_id))

    trainer = db.execute("SELECT name FROM mitarbeiter WHERE id=?", (trainer_id,)).fetchone()
    _create_benachrichtigung(db, trainer_id, "email",
        f"Du wurdest dem Kurs am {kurs['datum']} um {kurs['uhrzeit']} zugewiesen.")

    db.commit()
    return jsonify({"message": f"Trainer {trainer['name']} zugewiesen"})


# ══════════════════════════════════════════════════════════════════════════════
# VERTRETUNGSSUCHE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/kurse/<int:kurs_id>/vertretung", methods=["GET"])
def vertretung_suchen(kurs_id):
    """
    Findet alle geeigneten Ersatztrainer für einen Kurs.
    Prüft: Verfügbarkeit, Qualifikation, Wochenkontingent, Fahrtzeit (1h Puffer).
    """
    db = get_db()
    kurs = db.execute("""
        SELECT k.*, kt.qualifikation AS benoetigte_quali, kt.name AS kurstyp_name,
               s.id AS studio_id
        FROM kurse k
        JOIN kurstypen kt ON kt.id = k.kurstyp_id
        JOIN studios s ON s.id = k.studio_id
        WHERE k.id=?
    """, (kurs_id,)).fetchone()

    if not kurs:
        return jsonify({"error": "Kurs nicht gefunden"}), 404

    kandidaten = scheduling.finde_ersatztrainer(db, dict(kurs))
    return jsonify({"kurs_id": kurs_id, "kandidaten": kandidaten})


@app.route("/api/kurse/<int:kurs_id>/vertretung", methods=["POST"])
def vertretung_bestaetigen(kurs_id):
    """
    Bestätigt einen Ersatztrainer und sendet Benachrichtigungen.
    Body: { "trainer_id": 5 }
    """
    data = request.get_json()
    trainer_id = data["trainer_id"]
    db = get_db()

    kurs = db.execute("SELECT * FROM kurse WHERE id=?", (kurs_id,)).fetchone()
    trainer = db.execute("SELECT name FROM mitarbeiter WHERE id=?", (trainer_id,)).fetchone()

    # Zuweisung
    db.execute("UPDATE kurse SET trainer_id=?, status='aktiv' WHERE id=?",
               (trainer_id, kurs_id))

    # Ersatztrainer benachrichtigen
    _create_benachrichtigung(db, trainer_id, "email",
        f"Vertretung: Du übernimmst den Kurs am {kurs['datum']} um {kurs['uhrzeit']}.")

    # Gebuchte Mitglieder informieren
    buchungen = db.execute(
        "SELECT mitglied_id FROM buchungen WHERE kurs_id=? AND status='aktiv'", (kurs_id,)
    ).fetchall()
    for b in buchungen:
        _create_benachrichtigung(db, b["mitglied_id"], "email",
            f"Kursänderung: Dein Kurs findet statt – neuer Trainer: {trainer['name']}.")

    db.commit()
    return jsonify({
        "message": f"{trainer['name']} als Ersatz zugewiesen",
        "mitglieder_benachrichtigt": len(buchungen)
    })


# ══════════════════════════════════════════════════════════════════════════════
# MITGLIEDER
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/mitglieder", methods=["GET"])
def get_mitglieder():
    db = get_db()
    rows = db.execute("SELECT * FROM mitglieder").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/mitglieder", methods=["POST"])
def create_mitglied():
    data = request.get_json()
    db = get_db()
    cur = db.execute(
        "INSERT INTO mitglieder (name, email) VALUES (?, ?)",
        (data["name"], data["email"])
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, **data}), 201


# ── Buchungen ─────────────────────────────────────────────────────────────────

@app.route("/api/buchungen", methods=["POST"])
def create_buchung():
    data = request.get_json()
    db = get_db()
    cur = db.execute(
        "INSERT INTO buchungen (mitglied_id, kurs_id, datum, status) VALUES (?,?,date('now'),'aktiv')",
        (data["mitglied_id"], data["kurs_id"])
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, **data}), 201


@app.route("/api/buchungen/<int:buchung_id>/stornieren", methods=["POST"])
def buchung_stornieren(buchung_id):
    db = get_db()
    db.execute("UPDATE buchungen SET status='storniert' WHERE id=?", (buchung_id,))
    db.commit()
    return jsonify({"message": "Buchung storniert"})


# ══════════════════════════════════════════════════════════════════════════════
# BENACHRICHTIGUNGEN
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/benachrichtigungen", methods=["GET"])
def get_benachrichtigungen():
    db = get_db()
    empfaenger_id = request.args.get("empfaenger_id")
    query = "SELECT * FROM benachrichtigungen WHERE 1=1"
    params = []
    if empfaenger_id:
        query += " AND (empfaenger_id=? OR empfaenger_id IS NULL)"
        params.append(empfaenger_id)
    query += " ORDER BY erstellt_am DESC LIMIT 50"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/benachrichtigungen/<int:notif_id>/gelesen", methods=["POST"])
def mark_gelesen(notif_id):
    db = get_db()
    db.execute("UPDATE benachrichtigungen SET gelesen=1 WHERE id=?", (notif_id,))
    db.commit()
    return jsonify({"message": "Markiert"})


@app.route("/api/benachrichtigungen/alle-gelesen", methods=["POST"])
def alle_gelesen():
    db = get_db()
    db.execute("UPDATE benachrichtigungen SET gelesen=1")
    db.commit()
    return jsonify({"message": "Alle als gelesen markiert"})


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    """Aggregierte Übersichtsdaten für das Dashboard."""
    db = get_db()
    kurse_total   = db.execute("SELECT COUNT(*) FROM kurse WHERE status='aktiv'").fetchone()[0]
    kurse_ausf    = db.execute("SELECT COUNT(*) FROM kurse WHERE status='ausgefallen'").fetchone()[0]
    trainer_total = db.execute("SELECT COUNT(*) FROM mitarbeiter").fetchone()[0]
    trainer_verf  = db.execute("SELECT COUNT(*) FROM mitarbeiter WHERE verfuegbar=1").fetchone()[0]
    trainer_krank = db.execute("SELECT COUNT(*) FROM mitarbeiter WHERE verfuegbar=0").fetchone()[0]
    studios       = db.execute("SELECT COUNT(*) FROM studios").fetchone()[0]
    ungelesen     = db.execute("SELECT COUNT(*) FROM benachrichtigungen WHERE gelesen=0").fetchone()[0]

    # Trainer-Auslastung diese Woche
    auslastung = db.execute("""
        SELECT m.id, m.name, m.max_kurse_woche,
               COUNT(k.id) AS kurse_diese_woche
        FROM mitarbeiter m
        LEFT JOIN kurse k ON k.trainer_id=m.id AND k.status='aktiv'
               AND k.datum BETWEEN date('now','weekday 0','-6 days') AND date('now','weekday 0')
        GROUP BY m.id
    """).fetchall()

    return jsonify({
        "kurse_aktiv":      kurse_total,
        "kurse_ausgefallen": kurse_ausf,
        "trainer_gesamt":   trainer_total,
        "trainer_verfuegbar": trainer_verf,
        "trainer_krank":    trainer_krank,
        "studios":          studios,
        "benachrichtigungen_ungelesen": ungelesen,
        "trainer_auslastung": [dict(r) for r in auslastung]
    })


# ══════════════════════════════════════════════════════════════════════════════
# AUTH (einfaches Session-Login)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    db = get_db()
    ma = db.execute(
        "SELECT * FROM mitarbeiter WHERE email=? AND passwort=?",
        (data["email"], data["passwort"])
    ).fetchone()
    if not ma:
        return jsonify({"error": "E-Mail oder Passwort falsch"}), 401
    return jsonify({"id": ma["id"], "name": ma["name"], "rolle": ma["rolle"]})


# ══════════════════════════════════════════════════════════════════════════════
# HILFSFUNKTION
# ══════════════════════════════════════════════════════════════════════════════

def _create_benachrichtigung(db, empfaenger_id, kanal, inhalt):
    db.execute("""
        INSERT INTO benachrichtigungen (empfaenger_id, inhalt, kanal, gelesen)
        VALUES (?, ?, ?, 0)
    """, (empfaenger_id, inhalt, kanal))


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
