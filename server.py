# HSBAU Rapport-Nummer Server
# Pro Personalnummer eigene fortlaufende Nummer + Admin-Panel

from flask import Flask, jsonify, request, render_template_string, redirect, session
from flask_cors import CORS
from datetime import datetime
import json, os

app = Flask(__name__)
CORS(app, resources={r"/next-number": {"origins": "*"},
                     r"/current-numbers": {"origins": "*"},
                     r"/history": {"origins": "*"}})
app.secret_key = os.environ.get("SECRET_KEY", "hsbau-secret-2024")

COUNTER_FILE = "rapport_counter.json"
ADMIN_KEY    = os.environ.get("ADMIN_KEY", "hsbauadmin2026")

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

# ── API Endpunkte ──

@app.route("/next-number", methods=["GET"])
def next_number():
    person = request.args.get("person", "").strip().zfill(2)
    import threading
    lock = threading.Lock()
    with lock:
        data = load_counter()
        if "personen" not in data: data["personen"] = {}
        if "history"  not in data: data["history"]  = []
        if person not in data["personen"]: data["personen"][person] = 0
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
    return jsonify({
        p: {"aktuell": n, "naechste": f"{p}-{str(n+1).zfill(4)}"}
        for p, n in sorted(personen.items())
    })

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
    if request.json.get("key") != ADMIN_KEY:
        return jsonify({"error": "Nicht autorisiert"}), 403
    import threading
    lock = threading.Lock()
    with lock:
        data = load_counter()
        person = request.json.get("person", "").strip()
        start  = int(request.json.get("start_bei", 0))
        if person:
            data["personen"][person.zfill(2)] = start
            msg = f"Person {person} auf {start} gesetzt"
        else:
            data["personen"] = {}
            msg = "Alle Zähler zurückgesetzt"
        data["history"].append({"person": person or "ALLE", "nummer": f"RESET→{start}", "zeitpunkt": datetime.now().isoformat()})
        save_counter(data)
    return jsonify({"success": True, "message": msg})

# ── Admin Panel ──

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HSBAU Admin</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #E9ECEF; min-height: 100vh; }
  .header { background: #E30613; color: white; padding: 20px 40px; display: flex; align-items: center; gap: 16px; }
  .header h1 { font-size: 22px; font-weight: 700; }
  .header span { font-size: 13px; opacity: 0.8; }
  .container { max-width: 800px; margin: 30px auto; padding: 0 20px; }
  .card { background: white; border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .card h2 { font-size: 16px; font-weight: 700; color: #E30613; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #E9ECEF; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #343A40; color: white; padding: 10px 14px; text-align: left; font-size: 13px; }
  td { padding: 10px 14px; border-bottom: 1px solid #E9ECEF; font-size: 14px; }
  tr:hover td { background: #f8f9fa; }
  .badge { background: #E30613; color: white; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; }
  .form-row { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; margin-top: 16px; }
  .form-group { display: flex; flex-direction: column; gap: 4px; }
  label { font-size: 12px; font-weight: 600; color: #6C757D; text-transform: uppercase; }
  input, select { padding: 9px 12px; border: 1.5px solid #CED4DA; border-radius: 6px; font-size: 14px; font-family: inherit; outline: none; }
  input:focus, select:focus { border-color: #E30613; }
  .btn { padding: 9px 20px; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: inherit; }
  .btn-red   { background: #E30613; color: white; }
  .btn-dark  { background: #343A40; color: white; }
  .btn-gray  { background: #6C757D; color: white; }
  .btn:hover { opacity: 0.88; }
  .msg { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; font-weight: 600; }
  .msg-ok  { background: #d4edda; color: #155724; }
  .msg-err { background: #f8d7da; color: #721c24; }
  .login-wrap { max-width: 360px; margin: 80px auto; }
  .login-wrap .card { padding: 32px; }
  .login-wrap h2 { text-align: center; }
  .login-wrap input { width: 100%; margin-top: 16px; }
  .login-wrap .btn { width: 100%; margin-top: 12px; padding: 12px; font-size: 15px; }
  .history-list { max-height: 300px; overflow-y: auto; }
  .history-item { display: flex; gap: 12px; padding: 8px 0; border-bottom: 1px solid #E9ECEF; font-size: 13px; }
  .history-item .nr { font-weight: 700; color: #E30613; min-width: 90px; }
  .history-item .time { color: #6C757D; }
  .logout { float: right; background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 14px; border-radius: 5px; cursor: pointer; font-size: 13px; }
</style>
</head>
<body>

{% if not logged_in %}
<div class="login-wrap">
  <div class="card">
    <h2 style="color:#E30613">🔐 HSBAU Admin</h2>
    {% if error %}<div class="msg msg-err">{{ error }}</div>{% endif %}
    <form method="POST" action="/admin">
      <label>Admin-Passwort</label>
      <input type="password" name="password" placeholder="Passwort eingeben" autofocus>
      <button class="btn btn-red" type="submit">Anmelden</button>
    </form>
  </div>
</div>

{% else %}
<div class="header">
  <div>
    <h1>🏗️ HSBAU Rapport Admin</h1>
    <span>Rapport-Nummern Verwaltung</span>
  </div>
  <form method="POST" action="/admin/logout" style="margin-left:auto">
    <button class="logout" type="submit">Abmelden</button>
  </form>
</div>

<div class="container">

  {% if msg %}<div class="msg msg-ok">✅ {{ msg }}</div>{% endif %}
  {% if err %}<div class="msg msg-err">❌ {{ err }}</div>{% endif %}

  <!-- Aktueller Stand -->
  <div class="card">
    <h2>📊 Aktueller Stand pro Arbeiter</h2>
    <table>
      <tr>
        <th>Person Nr.</th>
        <th>Gespeicherte Rapporte</th>
        <th>Letzte Nummer</th>
        <th>Nächste Nummer</th>
      </tr>
      {% for p, n in personen.items() %}
      <tr>
        <td><b>{{ p }}</b></td>
        <td>{{ n }}</td>
        <td><span class="badge">{{ p }}-{{ '%04d'|format(n) }}</span></td>
        <td>{{ p }}-{{ '%04d'|format(n+1) }}</td>
      </tr>
      {% else %}
      <tr><td colspan="4" style="color:#6C757D">Noch keine Rapporte gespeichert.</td></tr>
      {% endfor %}
    </table>
  </div>

  <!-- Zähler anpassen -->
  <div class="card">
    <h2>✏️ Nächste Nummer manuell setzen</h2>
    <p style="color:#6C757D;font-size:13px;margin-bottom:4px">
      Hier kannst du festlegen, bei welcher Nummer der Zähler einer Person weiterzählen soll.<br>
      <b>Beispiel:</b> Person 01, Nächste Nummer = 10 → nächster Rapport wird <b>01-0010</b>
    </p>
    <form method="POST" action="/admin/set">
      <div class="form-row">
        <div class="form-group">
          <label>Person Nr.</label>
          <select name="person">
            <option value="01">01</option>
            <option value="02">02</option>
            <option value="03">03</option>
            <option value="04">04</option>
          </select>
        </div>
        <div class="form-group">
          <label>Nächste Nummer soll sein</label>
          <input type="number" name="naechste" min="1" placeholder="z.B. 10" style="width:140px">
        </div>
        <button class="btn btn-dark" type="submit">Setzen</button>
      </div>
    </form>
  </div>

  <!-- Alle zurücksetzen -->
  <div class="card">
    <h2>⚠️ Alle Zähler zurücksetzen</h2>
    <p style="color:#6C757D;font-size:13px;margin-bottom:12px">Setzt alle Zähler auf 0 zurück. Alle Nummern starten neu bei 0001.</p>
    <form method="POST" action="/admin/reset-all" onsubmit="return confirm('Wirklich ALLE Zähler zurücksetzen?')">
      <button class="btn btn-red" type="submit">🗑️ Alle zurücksetzen</button>
    </form>
  </div>

  <!-- Verlauf -->
  <div class="card">
    <h2>📋 Letzter Verlauf</h2>
    <div class="history-list">
      {% for e in history|reverse %}
      <div class="history-item">
        <span class="nr">{{ e.nummer }}</span>
        <span class="time">{{ e.zeitpunkt[:16].replace('T', ' ') }}</span>
        <span>{{ e.geraet if e.geraet else '' }}</span>
      </div>
      {% else %}
      <p style="color:#6C757D;font-size:13px">Noch keine Einträge.</p>
      {% endfor %}
    </div>
  </div>

</div>
{% endif %}
</body>
</html>
"""

@app.route("/admin", methods=["GET", "POST"])
def admin():
    logged_in = session.get("admin_logged_in", False)
    msg = request.args.get("msg", "")
    err = request.args.get("err", "")

    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == ADMIN_KEY:
            session["admin_logged_in"] = True
            return redirect("/admin")
        else:
            return render_template_string(ADMIN_HTML, logged_in=False, error="Falsches Passwort!")

    if not logged_in:
        return render_template_string(ADMIN_HTML, logged_in=False, error=None)

    data = load_counter()
    return render_template_string(ADMIN_HTML,
        logged_in=True,
        personen=data.get("personen", {}),
        history=data.get("history", [])[-100:],
        msg=msg, err=err
    )

@app.route("/admin/set", methods=["POST"])
def admin_set():
    if not session.get("admin_logged_in"):
        return redirect("/admin")
    person   = request.form.get("person", "01").zfill(2)
    naechste = request.form.get("naechste", "")
    try:
        naechste_int = int(naechste)
        if naechste_int < 1:
            raise ValueError
        import threading
        lock = threading.Lock()
        with lock:
            data = load_counter()
            if "personen" not in data: data["personen"] = {}
            data["personen"][person] = naechste_int - 1
            data["history"].append({
                "person":    person,
                "nummer":    f"ADMIN-SET→{person}-{str(naechste_int).zfill(4)}",
                "zeitpunkt": datetime.now().isoformat(),
                "geraet":    "Admin-Panel"
            })
            save_counter(data)
        return redirect(f"/admin?msg=Person {person}: Nächste Nummer ist jetzt {person}-{str(naechste_int).zfill(4)}")
    except:
        return redirect("/admin?err=Ungültige Eingabe. Bitte eine Zahl größer 0 eingeben.")

@app.route("/admin/reset-all", methods=["POST"])
def admin_reset_all():
    if not session.get("admin_logged_in"):
        return redirect("/admin")
    import threading
    lock = threading.Lock()
    with lock:
        data = load_counter()
        data["personen"] = {}
        data["history"].append({"person": "ALLE", "nummer": "RESET→0", "zeitpunkt": datetime.now().isoformat(), "geraet": "Admin-Panel"})
        save_counter(data)
    return redirect("/admin?msg=Alle Zähler wurden zurückgesetzt.")

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect("/admin")

@app.route("/", methods=["GET"])
def status():
    data = load_counter()
    personen = data.get("personen", {})
    history  = data.get("history", [])
    letzte   = history[-1] if history else {}
    rows = "".join(
        f"<tr><td style='padding:6px 16px'><b>{p}</b></td>"
        f"<td style='padding:6px 16px'>{n}</td>"
        f"<td style='padding:6px 16px'>{p}-{str(n).zfill(4)}</td></tr>"
        for p, n in sorted(personen.items())
    )
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
    <br><a href="/admin" style="color:#E30613;font-weight:bold">→ Admin-Panel öffnen</a>
    </body></html>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"HSBAU Server startet auf Port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
