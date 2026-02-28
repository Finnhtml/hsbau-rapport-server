# HSBAU Rapport-Nummer Server
# Pro Personalnummer eigene fortlaufende Nummer

from flask import Flask, jsonify, request
from datetime import datetime
import json, os, threading, urllib.request

app = Flask(__name__)
lock = threading.Lock()

COUNTER_FILE = "rapport_counter.json"

def load_counter():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"personen": {}, "history": []}

def save_counter(data):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/next-number", methods=["GET"])
def next_number():
    person = request.args.get("person", "").strip().zfill(2)

    with lock:
        data = load_counter()
        if "personen" not in data: data["personen"] = {}
        if "history"  not in data: data["history"]  = []

        if person not in data["personen"]:
            data["personen"][person] = 0

        data["personen"][person] += 1
        nummer = data["personen"][person]
        formatiert = f"{person}-{str(nummer).zfill(4)}"

        data["history"].append({
            "person":    person,
            "nummer":    formatiert,
            "zeitpunkt": datetime.now().isoformat(),
            "geraet":    request.args.get("geraet", "Unbekannt")
        })
        if len(data["history"]) > 1000:
            data["history"] = data["history"][-1000:]
        save_counter(data)

    return jsonify({"success": True, "person": person, "nummer": nummer, "formatiert": formatiert})

@app.route("/current-numbers", methods=["GET"])
def current_numbers():
    data = load_counter()
    personen = data.get("personen", {})
    result = {
        p: {"aktuell": n, "formatiert": f"{p}-{str(n).zfill(4)}"}
        for p, n in sorted(personen.items())
    }
    return jsonify(result)

@app.route("/history", methods=["GET"])
def history():
    data = load_counter()
    person = request.args.get("person", "").strip()
    entries = data.get("history", [])
    if person:
        entries = [e for e in entries if e.get("person") == person.zfill(2)]
    return jsonify(entries[-50:])

@app.route("/reset", methods=["POST"])
def reset():
    admin_key = os.environ.get("ADMIN_KEY", "hsbau-admin-2024")
    if request.json.get("key") != admin_key:
        return jsonify({"error": "Nicht autorisiert"}), 403
    with lock:
        data = load_counter()
        person = request.json.get("person", "").strip()
        start  = request.json.get("start_bei", 0)
        if person:
            data["personen"][person.zfill(2)] = start
            msg = f"Person {person} zurückgesetzt auf {start}"
        else:
            data["personen"] = {}
            msg = "Alle Zähler zurückgesetzt"
        data["history"].append({"person": person or "ALLE", "nummer": "RESET", "zeitpunkt": datetime.now().isoformat()})
        save_counter(data)
    return jsonify({"success": True, "message": msg})

@app.route("/", methods=["GET"])
def status():
    data = load_counter()
    personen = data.get("personen", {})
    rows = "".join(
        f"<tr><td style='padding:6px 16px'><b>{p}</b></td>"
        f"<td style='padding:6px 16px'>{n}</td>"
        f"<td style='padding:6px 16px'>{p}-{str(n).zfill(4)}</td></tr>"
        for p, n in sorted(personen.items())
    )
    letzte = data.get("history", [{}])[-1]
    return f"""
    <html><body style="font-family:sans-serif;padding:40px;background:#f5f5f5">
    <h1 style="color:#E30613">HSBAU Rapport-Nummer Server</h1>
    <p>✅ Server läuft</p>
    <p><b>Letzte Vergabe:</b> {letzte.get('nummer','—')} um {letzte.get('zeitpunkt','—')[:16].replace('T',' ')} von {letzte.get('geraet','—')}</p>
    <h3>Stand pro Person:</h3>
    <table border="1" cellspacing="0" style="border-collapse:collapse;background:white">
      <tr style="background:#E30613;color:white">
        <th style="padding:6px 16px">Person</th>
        <th style="padding:6px 16px">Rapporte</th>
        <th style="padding:6px 16px">Letzte Nummer</th>
      </tr>
      {rows if rows else "<tr><td colspan='3' style='padding:10px'>Noch keine Rapporte</td></tr>"}
    </table>
    <br>
    <h3>API:</h3>
    <ul>
      <li><a href="/next-number?person=01">GET /next-number?person=01</a></li>
      <li><a href="/current-numbers">GET /current-numbers</a></li>
      <li><a href="/history?person=01">GET /history?person=01</a></li>
    </ul>
    </body></html>
    """

def _keep_alive():
    import time
    server_url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
    while True:
        time.sleep(600)
        try:
            urllib.request.urlopen(f"{server_url}/", timeout=5)
            print("[HSBAU] Keep-alive ping ✓")
        except Exception as e:
            print(f"[HSBAU] Keep-alive fehlgeschlagen: {e}")

threading.Thread(target=_keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"HSBAU Server startet auf Port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
