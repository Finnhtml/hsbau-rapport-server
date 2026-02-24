# HSBAU Rapport-Nummer Server
# Kostenlos hosten auf: https://render.com

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
    return {"current": 0, "history": []}

def save_counter(data):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/next-number", methods=["GET"])
def next_number():
    with lock:
        data = load_counter()
        data["current"] += 1
        nummer = data["current"]
        data["history"].append({
            "nummer": nummer,
            "zeitpunkt": datetime.now().isoformat(),
            "gerät": request.args.get("geraet", "Unbekannt")
        })
        if len(data["history"]) > 500:
            data["history"] = data["history"][-500:]
        save_counter(data)
    return jsonify({"success": True, "nummer": nummer, "formatiert": str(nummer).zfill(4)})

@app.route("/current-number", methods=["GET"])
def current_number():
    data = load_counter()
    return jsonify({"current": data["current"], "formatiert": str(data["current"]).zfill(4)})

@app.route("/history", methods=["GET"])
def history():
    data = load_counter()
    return jsonify(data["history"][-50:])

@app.route("/reset", methods=["POST"])
def reset():
    admin_key = os.environ.get("ADMIN_KEY", "hsbau-admin-2024")
    if request.json.get("key") != admin_key:
        return jsonify({"error": "Nicht autorisiert"}), 403
    with lock:
        data = load_counter()
        data["history"].append({"nummer": "RESET", "zeitpunkt": datetime.now().isoformat(), "vorher": data["current"]})
        start = request.json.get("start_bei", 0)
        data["current"] = start
        save_counter(data)
    return jsonify({"success": True, "neuer_stand": start})

@app.route("/", methods=["GET"])
def status():
    data = load_counter()
    return f"""
    <html><body style="font-family:sans-serif;padding:40px;background:#f5f5f5">
    <h1 style="color:#E30613">HSBAU Rapport-Nummer Server</h1>
    <p>✅ Server läuft</p>
    <p><b>Aktuelle Nummer:</b> {data['current']}</p>
    <p><b>Letzte Vergabe:</b> {data['history'][-1]['zeitpunkt'] if data['history'] else 'Noch keine'}</p>
    </body></html>
    """

# ── Keep-Alive: pingt sich selbst alle 10 Minuten an ──
def _keep_alive():
    import time
    server_url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
    while True:
        time.sleep(600)  # 10 Minuten
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
