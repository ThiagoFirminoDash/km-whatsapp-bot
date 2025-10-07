#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WhatsApp KM Bot (Flask + SQLite + Twilio)
- Registra: KM início/fim, corridas (R$), abastecimentos (tipo, valor, litros)
- Comandos no WhatsApp: 
  km inicio 32000
  km final 32210
  corrida 25        | corrida 12, 18, 34
  abasteci etanol 120 28   (tipo valor litros)
  abasteci gasolina 200 33.5
  resumo            (de hoje, TZ America/Sao_Paulo)
  resumo AAAA-MM-DD
- Endpoints extras:
  /cron/daily        -> retorna texto do resumo (para logs ou teste)
  /cron/send_daily   -> envia o resumo por WhatsApp (Twilio) para ?user=whatsapp:+55SEUNUM
"""

import os, re, sqlite3
from datetime import datetime, date
from zoneinfo import ZoneInfo

from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient

# ===== Configurações =====
TZ = ZoneInfo("America/Sao_Paulo")
DB_PATH = os.getenv("DB_PATH", "km_driver.db")

# Twilio (para enviar resumo diário)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM        = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

twilio_ok = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM)
twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if twilio_ok else None

app = Flask(__name__)

# ===== DB =====
def db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db(); cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS day_km (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_phone TEXT NOT NULL,
        d DATE NOT NULL,
        km_start REAL,
        km_end REAL,
        UNIQUE(user_phone, d)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_phone TEXT NOT NULL,
        d DATE NOT NULL,
        ts TIMESTAMP NOT NULL,
        amount REAL NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fuels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_phone TEXT NOT NULL,
        d DATE NOT NULL,
        ts TIMESTAMP NOT NULL,
        fuel_type TEXT NOT NULL,
        liters REAL NOT NULL,
        amount REAL NOT NULL
    )""")
    conn.commit(); conn.close()

init_db()

# ===== Helpers =====
def today_sp():
    return datetime.now(TZ).date()

def parse_nums(txt: str):
    # captura 12, 12.5, 12,50
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", txt)]

def upsert_day(user, d, km_start=None, km_end=None):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT km_start, km_end FROM day_km WHERE user_phone=? AND d=?", (user, d))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO day_km (user_phone, d, km_start, km_end) VALUES (?,?,?,?)",
                    (user, d, km_start, km_end))
    else:
        new_start = km_start if km_start is not None else row["km_start"]
        new_end   = km_end   if km_end   is not None else row["km_end"]
        cur.execute("UPDATE day_km SET km_start=?, km_end=? WHERE user_phone=? AND d=?",
                    (new_start, new_end, user, d))
    conn.commit(); conn.close()

def add_ride(user, d, amount):
    conn = db(); cur = conn.cursor()
    cur.execute("INSERT INTO rides (user_phone, d, ts, amount) VALUES (?,?,?,?)",
                (user, d, datetime.now(TZ), amount))
    conn.commit(); conn.close()

def add_fuel(user, d, fuel_type, amount, liters):
    conn = db(); cur = conn.cursor()
    cur.execute("INSERT INTO fuels (user_phone, d, ts, fuel_type, liters, amount) VALUES (?,?,?,?,?,?)",
                (user, d, datetime.now(TZ), fuel_type.lower(), liters, amount))
    conn.commit(); conn.close()

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def summarize_text(user, d):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT km_start, km_end FROM day_km WHERE user_phone=? AND d=?", (user, d))
    km = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(amount),0) AS total FROM rides WHERE user_phone=? AND d=?", (user, d))
    rides_total = cur.fetchone()["total"] or 0.0
    cur.execute("SELECT COALESCE(SUM(amount),0) AS gas, COALESCE(SUM(liters),0) AS liters FROM fuels WHERE user_phone=? AND d=?", (user, d))
    f = cur.fetchone()
    fuel_total = f["gas"] or 0.0
    liters_total = f["liters"] or 0.0
    conn.close()

    km_str = "—"
    km_run = None
    if km and km["km_start"] is not None and km["km_end"] is not None:
        km_run = km["km_end"] - km["km_start"]
        km_str = f"{km['km_start']:.0f} → {km['km_end']:.0f} (rodou {km_run:.1f} km)"

    lucro = rides_total - fuel_total
    custo_km = (fuel_total / km_run) if (km_run and km_run > 0) else None
    preco_medio = (fuel_total / liters_total) if liters_total > 0 else None

    lines = [f"📊 Resumo de {d}"]
    lines.append(f"• KM: {km_str}")
    lines.append(f"• Ganhos (corridas): {money(rides_total)}")
    lines.append(f"• Combustível: {money(fuel_total)}" + (f"\n  └ Preço médio/L: {money(preco_medio)}" if preco_medio else ""))
    if custo_km is not None:
        lines.append(f"• Custo por km: {money(custo_km)}")
    lines.append(f"• 💰 Lucro do dia: {money(lucro)}")
    return "\n".join(lines)

def send_whatsapp(to, body):
    if not twilio_ok:
        return False, "Twilio não configurado"
    twilio.messages.create(from_=TWILIO_FROM, to=to, body=body)
    return True, "ok"

def help_text():
    return ("🧾 *Comandos*\n"
            "• km inicio 32000\n"
            "• km final 32210\n"
            "• corrida 25  |  corrida 12, 18, 34\n"
            "• abasteci etanol 120 28   (tipo valor litros)\n"
            "• abasteci gasolina 200 33.5\n"
            "• resumo            (de hoje)\n"
            "• resumo AAAA-MM-DD\n")

# ===== Rotas =====
@app.post("/whatsapp")
def whatsapp_webhook():
    from_phone = request.form.get("From")      # 'whatsapp:+55...'
    body = (request.form.get("Body") or "").strip().lower()
    if not from_phone: abort(400)

    d = today_sp()
    resp = MessagingResponse()
    msg = resp.message

    if body.startswith("km inicio"):
        vals = parse_nums(body)
        if not vals: msg.body("Use: km inicio 32000"); return str(resp)
        upsert_day(from_phone, d, km_start=vals[0])
        msg.body(f"✅ KM inicial salvo: {vals[0]:.0f}"); return str(resp)

    if body.startswith("km final"):
        vals = parse_nums(body)
        if not vals: msg.body("Use: km final 32210"); return str(resp)
        upsert_day(from_phone, d, km_end=vals[0])
        msg.body(f"✅ KM final salvo: {vals[0]:.0f}"); return str(resp)

    if body.startswith("corrida"):
        amounts = parse_nums(body)
        if not amounts: msg.body("Use: corrida 25  |  corrida 12, 18, 34"); return str(resp)
        for a in amounts: add_ride(from_phone, d, a)
        msg.body("✅ Corrida(s) registrada(s)."); return str(resp)

    if body.startswith("abasteci"):
        parts = body.split()
        if len(parts) < 4: msg.body("Use: abasteci etanol 120 28 (tipo valor litros)"); return str(resp)
        fuel_type = parts[1]
        nums = parse_nums(" ".join(parts[2:]))
        if len(nums) < 2: msg.body("Use: abasteci <tipo> <valor> <litros>"); return str(resp)
        add_fuel(from_phone, d, fuel_type, nums[0], nums[1])
        msg.body("✅ Abastecimento salvo."); return str(resp)

    if body.startswith("resumo"):
        tokens = body.split()
        dsum = d
        if len(tokens) == 2:
            try: dsum = date.fromisoformat(tokens[1])
            except ValueError: msg.body("Data inválida. Use AAAA-MM-DD"); return str(resp)
        msg.body(summarize_text(from_phone, dsum)); return str(resp)

    if body in ("ajuda","help","?"):
        msg.body(help_text()); return str(resp)

    msg.body("Não entendi 🤔\n\n" + help_text()); return str(resp)

# Resumo em TEXTO (para logs/cron)
@app.get("/cron/daily")
def cron_daily_text():
    user = request.args.get("user")
    d_str = request.args.get("date")
    if not user: return "Passe ?user=whatsapp:+55SEU_NUM", 400
    ddate = date.fromisoformat(d_str) if d_str else today_sp()
    return summarize_text(user, ddate), 200

# Resumo e ENVIO pelo WhatsApp (usa Twilio)
@app.get("/cron/send_daily")
def cron_send_daily():
    user = request.args.get("user")
    d_str = request.args.get("date")
    if not user: return "Passe ?user=whatsapp:+55SEU_NUM", 400
    ddate = date.fromisoformat(d_str) if d_str else today_sp()
    body = summarize_text(user, ddate)
    ok, info = send_whatsapp(user, body)
    if not ok: return f"Falha envio: {info}", 500
    return "Enviado", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
