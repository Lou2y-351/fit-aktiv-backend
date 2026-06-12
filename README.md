# Fit & Aktiv – Backend

Flask REST API + SQLite für das Kursplanungs- und Mitarbeiterverwaltungssystem.

---

## Schnellstart (lokal)

### 1. Python-Umgebung einrichten

```bash
# Ins Backend-Verzeichnis wechseln
cd fit-aktiv-backend

# Virtuelle Umgebung erstellen
python -m venv venv

# Aktivieren
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 2. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 3. Server starten

```bash
python app.py
```

Der Server läuft jetzt auf **http://localhost:5000**  
Die Datenbank `fitaktiv.db` wird automatisch mit Beispieldaten angelegt.

---

## API-Endpunkte – Übersicht

| Methode | URL | Beschreibung |
|---------|-----|--------------|
| GET | `/api/dashboard` | Übersichtsdaten für Dashboard |
| GET | `/api/studios` | Alle Studios |
| POST | `/api/studios` | Studio anlegen |
| GET | `/api/mitarbeiter` | Alle Mitarbeiter |
| POST | `/api/mitarbeiter` | Mitarbeiter anlegen |
| PUT | `/api/mitarbeiter/:id` | Mitarbeiter bearbeiten |
| DELETE | `/api/mitarbeiter/:id` | Mitarbeiter löschen |
| POST | `/api/mitarbeiter/:id/krankmelden` | Krankmeldung einreichen |
| POST | `/api/mitarbeiter/:id/reaktivieren` | Trainer reaktivieren |
| GET | `/api/mitarbeiter/:id/einsatzplan` | Persönlicher Einsatzplan |
| GET | `/api/kurse` | Alle Kurse (mit Filtern: `?von=&bis=&trainer_id=&status=`) |
| POST | `/api/kurse` | Kurs anlegen |
| PUT | `/api/kurse/:id` | Kurs bearbeiten |
| DELETE | `/api/kurse/:id` | Kurs löschen |
| POST | `/api/kurse/:id/ausgefallen` | Kurs als ausgefallen markieren |
| PUT | `/api/kurse/:id/trainer` | Trainer einem Kurs zuweisen |
| GET | `/api/kurse/:id/vertretung` | Ersatztrainer suchen |
| POST | `/api/kurse/:id/vertretung` | Ersatztrainer bestätigen |
| GET | `/api/kurstypen` | Alle Kurstypen |
| GET | `/api/benachrichtigungen` | Benachrichtigungen |
| POST | `/api/benachrichtigungen/:id/gelesen` | Als gelesen markieren |
| POST | `/api/benachrichtigungen/alle-gelesen` | Alle gelesen |
| POST | `/api/login` | Login |

---

## Deployment auf Render.com (kostenlos)

1. Konto auf [render.com](https://render.com) erstellen
2. „New Web Service" → GitHub-Repo verbinden
3. Einstellungen:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. `gunicorn` zu `requirements.txt` hinzufügen:
   ```
   gunicorn==22.0.0
   ```
5. Deploy klicken → deine App läuft auf `https://fit-aktiv.onrender.com`

---

## Frontend verbinden (React)

In deiner React-App alle API-Aufrufe auf die Backend-URL zeigen:

```js
// src/api.js
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5000/api";

export const api = {
  dashboard:      ()        => fetch(`${BASE_URL}/dashboard`).then(r => r.json()),
  mitarbeiter:    ()        => fetch(`${BASE_URL}/mitarbeiter`).then(r => r.json()),
  kurse:          (params)  => fetch(`${BASE_URL}/kurse?${new URLSearchParams(params)}`).then(r => r.json()),
  krankmelden:    (id, data)=> fetch(`${BASE_URL}/mitarbeiter/${id}/krankmelden`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r => r.json()),
  vertretung:     (kursId)  => fetch(`${BASE_URL}/kurse/${kursId}/vertretung`).then(r => r.json()),
};
```

Für Produktion `.env`-Datei anlegen:
```
VITE_API_URL=https://fit-aktiv.onrender.com/api
```

---

## Projektstruktur

```
fit-aktiv-backend/
├── app.py           ← Flask App, alle API-Endpunkte
├── database.py      ← SQLite Setup, Schema, Seed-Daten
├── scheduling.py    ← Konfliktprüfung, Vertretungssuche
├── requirements.txt
├── fitaktiv.db      ← Wird automatisch erstellt
└── README.md
```
