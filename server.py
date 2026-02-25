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
    # New format: counters per person + history
    return {"counters": {}, "history": []}

def save_counter(data):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/next-number", methods=["GET"])
def next_number():
    person = request.args.get("person") or request.args.get("personalnummer") or "global"
    with lock:
        data = load_counter()
        counters = data.setdefault("counters", {})
        counters.setdefault(person, 0)
        counters[person] += 1
        nummer = counters[person]
        data.setdefault("history", []).append({
            "nummer": nummer,
            "person": person,
            "zeitpunkt": datetime.now().isoformat(),
            "gerät": request.args.get("geraet", "Unbekannt")
        })
        if len(data.get("history", [])) > 500:
            data["history"] = data["history"][-500:]
        save_counter(data)
    return jsonify({"success": True, "nummer": nummer, "formatiert": str(nummer).zfill(4), "person": person})

@app.route("/current-number", methods=["GET"])
def current_number():
    person = request.args.get("person") or request.args.get("personalnummer") or "global"
    data = load_counter()
    counters = data.get("counters", {})
    current = counters.get(person, 0)
    return jsonify({"current": current, "formatiert": str(current).zfill(4), "person": person})

@app.route("/history", methods=["GET"])
def history():
    data = load_counter()
    return jsonify(data["history"][-50:])

@app.route("/reset", methods=["POST"])
def reset():
    admin_key = os.environ.get("ADMIN_KEY", "hsbau-admin-2024")
    if request.json.get("key") != admin_key:
        return jsonify({"error": "Nicht autorisiert"}), 403
    person = request.json.get("person") or request.json.get("personalnummer") or "global"
    with lock:
        data = load_counter()
        data.setdefault("history", []).append({"nummer": "RESET", "zeitpunkt": datetime.now().isoformat(), "person": person, "vorher": data.get("counters", {}).get(person, 0)})
        start = int(request.json.get("start_bei", 0))
        counters = data.setdefault("counters", {})
        counters[person] = start
        save_counter(data)
    return jsonify({"success": True, "neuer_stand": start, "person": person})

@app.route("/", methods=["GET"])
def status():
    data = load_counter()
    counters = data.get("counters", {})
    last = (data.get("history") or [])[-1] if data.get("history") else None
    counters_html = "".join([f"<li>{p}: {n}</li>" for p, n in counters.items()]) or "<li>keine</li>"
    return f"""
    <html><body style="font-family:sans-serif;padding:40px;background:#f5f5f5">
    <h1 style="color:#E30613">HSBAU Rapport-Nummer Server</h1>
    <p>✅ Server läuft</p>
    <p><b>Aktuelle Nummern (pro Personal):</b></p>
    <ul>
    {counters_html}
    </ul>
    <p><b>Letzte Vergabe:</b> {last['zeitpunkt'] if last else 'Noch keine'}</p>
    </body></html>
    """


@app.route("/set-number", methods=["POST"])
def set_number():
    # Allows admin to manually set a person's counter via form or JSON on the website.
    admin_key = os.environ.get("ADMIN_KEY", "hsbau-admin-2024")
    # Accept either JSON or form data
    data_in = request.json if request.is_json else request.form
    if not data_in:
        return jsonify({"error": "Keine Daten erhalten"}), 400
    key = data_in.get("key")
    if key != admin_key:
        return jsonify({"error": "Nicht autorisiert"}), 403
    person = data_in.get("person") or data_in.get("personalnummer") or "global"
    try:
        value = int(data_in.get("value", 0))
    except Exception:
        return jsonify({"error": "Ungültiger Wert"}), 400

    with lock:
        d = load_counter()
        counters = d.setdefault("counters", {})
        before = counters.get(person, 0)
        counters[person] = value
        d.setdefault("history", []).append({"nummer": "MANUAL_SET", "person": person, "von": before, "auf": value, "zeitpunkt": datetime.now().isoformat(), "gerät": request.remote_addr})
        save_counter(d)

    return jsonify({"success": True, "person": person, "neuer_wert": value, "vorher": before})

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
