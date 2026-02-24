# HSBAU Rapport-Nummer Server
# Kostenlos hosten auf: https://render.com oder https://railway.app
#
# Lokal testen: python server.py
# Dann im Browser: http://localhost:5000/next-number

from flask import Flask, jsonify, request
from datetime import datetime
import json, os, threading

app = Flask(__name__)
lock = threading.Lock()

# Datei wo die aktuelle Nummer gespeichert wird
COUNTER_FILE = "rapport_counter.json"

def load_counter():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"current": 0, "history": []}

def save_counter(data):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── API Endpunkte ──

@app.route("/next-number", methods=["GET"])
def next_number():
    """Gibt die nächste Rapport-Nummer zurück und zählt hoch."""
    with lock:
        data = load_counter()
        data["current"] += 1
        nummer = data["current"]

        # Verlauf speichern (wer hat wann geholt)
        data["history"].append({
            "nummer": nummer,
            "zeitpunkt": datetime.now().isoformat(),
            "gerät": request.args.get("geraet", "Unbekannt")
        })

        # Nur letzten 500 Einträge behalten
        if len(data["history"]) > 500:
            data["history"] = data["history"][-500:]

        save_counter(data)

    return jsonify({
        "success": True,
        "nummer": nummer,
        "formatiert": str(nummer).zfill(4)  # z.B. "0042"
    })

@app.route("/current-number", methods=["GET"])
def current_number():
    """Zeigt die aktuelle Nummer ohne hochzuzählen."""
    data = load_counter()
    return jsonify({
        "current": data["current"],
        "formatiert": str(data["current"]).zfill(4)
    })

@app.route("/history", methods=["GET"])
def history():
    """Zeigt die letzten vergebenen Nummern."""
    data = load_counter()
    return jsonify(data["history"][-50:])  # Letzte 50

@app.route("/reset", methods=["POST"])
def reset():
    """Setzt den Zähler zurück (nur mit Admin-Key)."""
    admin_key = os.environ.get("ADMIN_KEY", "hsbau-admin-2024")
    if request.json.get("key") != admin_key:
        return jsonify({"error": "Nicht autorisiert"}), 403
    with lock:
        data = load_counter()
        data["history"].append({
            "nummer": "RESET",
            "zeitpunkt": datetime.now().isoformat(),
            "vorher": data["current"]
        })
        start = request.json.get("start_bei", 0)
        data["current"] = start
        save_counter(data)
    return jsonify({"success": True, "neuer_stand": start})

@app.route("/", methods=["GET"])
def status():
    """Status-Seite."""
    data = load_counter()
    return f"""
    <html><body style="font-family:sans-serif;padding:40px;background:#f5f5f5">
    <h1 style="color:#E30613">HSBAU Rapport-Nummer Server</h1>
    <p>✅ Server läuft</p>
    <p><b>Aktuelle Nummer:</b> {data['current']}</p>
    <p><b>Letzte Vergabe:</b> {data['history'][-1]['zeitpunkt'] if data['history'] else 'Noch keine'}</p>
    <hr>
    <h3>API Endpunkte:</h3>
    <ul>
      <li><a href="/next-number">GET /next-number</a> — Nächste Nummer holen</li>
      <li><a href="/current-number">GET /current-number</a> — Aktuelle Nummer ansehen</li>
      <li><a href="/history">GET /history</a> — Verlauf der letzten 50</li>
    </ul>
    </body></html>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"HSBAU Server startet auf Port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
