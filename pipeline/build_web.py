"""Empaqueta las salidas del pipeline en web/data.json.

El dashboard es estático a propósito: no hay servidor que se caiga en la
demo, y el link de puerta se abre en cualquier teléfono. El token que
firma cada link se genera aquí.
"""

import base64
import csv
import hashlib
import hmac
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

# Secreto de demo. En producción sale de una variable de entorno y rota por
# evento — ver docs/03-puerta.md.
SECRET = os.environ.get("PUERTA_SECRET", "demo-freeticket-2026").encode()

TYPE_ORDER = ["General", "Preferencial", "VIP", "Cortesía"]


def load(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def token(event_id, starts_at):
    exp = int((datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
               + timedelta(hours=3)).timestamp())
    payload = f"{event_id}|{exp}"
    sig = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode().rstrip("=")


def run(raw="raw", out="out", web="web"):
    fc = load(f"{out}/forecast_detalle.csv")
    curve = load(f"{out}/arrival_curve.csv")
    matches = load(f"{out}/matches_auditoria.csv")
    tickets = load(f"{raw}/freeticket_tickets.csv")

    mix = defaultdict(lambda: defaultdict(int))
    for t in tickets:
        mix[t["event_id"]][t["ticket_type"]] += 1

    # Pico de llegada: el decil con más entradas.
    peak = max(curve, key=lambda r: int(r["entradas"])) if curve else None
    peak_pct = float(peak["pct"]) if peak else 0.25
    peak_min = int(peak["minutos_vs_inicio"]) if peak else 0

    events = []
    for r in fc:
        exp = int(r["expected_attendance"])
        arrivals = exp * peak_pct
        staff = max(2, -(-int(arrivals) // 40))
        events.append({
            "event_id": r["event_id"],
            "title": r["title"],
            "venue": r["venue"],
            "city": r["city"],
            "starts_at": r["starts_at"],
            "is_residency": r["is_residency"] == "true",
            "sold": int(r["tickets_sold"]),
            "capacity": int(r["capacity"]),
            "expected": exp,
            "p10": int(r["p10"]),
            "p90": int(r["p90"]),
            "rate": float(r["expected_rate"]),
            "mix": {k: mix[r["event_id"]].get(k, 0) for k in TYPE_ORDER},
            "staff": staff,
            "peak_min": peak_min,
            "token": token(r["event_id"], r["starts_at"]),
        })

    ev_by_conf = defaultdict(int)
    for m in matches:
        c = float(m["confidence"])
        ev_by_conf["alta (≥0.90)" if c >= 0.90 else
                    "media (0.80–0.90)" if c >= 0.80 else
                    "baja (0.72–0.80)"] += 1

    reasons = defaultdict(int)
    for m in matches:
        for part in m["evidencia"].split("+"):
            reasons[part] += 1

    data = {
        "generado": None,
        "events": events,
        "curve": [{"m": int(c["minutos_vs_inicio"]),
                   "n": int(c["entradas"]),
                   "pct": float(c["pct"]),
                   "cum": float(c["pct_acumulado"])} for c in curve],
        "match": {
            "total_ventas": 6383,
            "cruzadas": len(matches),
            "por_confianza": dict(ev_by_conf),
            "evidencia": dict(sorted(reasons.items(), key=lambda x: -x[1])),
        },
        "totales": {
            "eventos": len(events),
            "entradas": sum(e["sold"] for e in events),
            "esperados": sum(e["expected"] for e in events),
            "p10": sum(e["p10"] for e in events),
            "p90": sum(e["p90"] for e in events),
        },
        "types": TYPE_ORDER,
    }

    os.makedirs(web, exist_ok=True)
    with open(f"{web}/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  web/data.json        {len(events)} eventos, {len(curve)} puntos de curva")


if __name__ == "__main__":
    run()
