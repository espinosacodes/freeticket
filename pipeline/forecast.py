"""Parte B — proyección de asistencia para los shows de agosto.

Se predice **entrada por entrada**, no evento por evento. Julio está
etiquetado a nivel ticket, así que ese es el grano donde hay señal: la
mezcla de tipos de entrada es lo que más manda, y un promedio por evento
la borraría.

    p(entra) = tasa_del_tipo × factor_acto × factor_boom × factor_canal × factor_anticipación

Cada factor se estima sobre el residuo del anterior y se encoge hacia 1
según cuántas entradas lo respaldan (`n/(n+k)`), para que un acto con 30
entradas en julio no mande más que la base.

El rango p10–p90 no sale de la binomial: sale de la binomial **inflada**
por la dispersión que se mide en julio evento a evento. Un intervalo
puramente binomial sería demasiado angosto y quedaría bonito en el papel
y mal en la puerta.
"""

import csv
import math
from collections import defaultdict
from datetime import datetime

Z10 = 1.2815515655446004  # cuantil normal para p10 / p90

CAP_LO, CAP_HI = 0.02, 0.995
K_ARTIST, K_BOOM, K_CHANNEL, K_LEAD = 200.0, 300.0, 300.0, 300.0


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def shrunk_factor(actual, predicted, n, k):
    """Factor multiplicativo encogido hacia 1 por volumen de evidencia."""
    if predicted <= 0 or n <= 0:
        return 1.0
    raw = actual / predicted
    w = n / (n + k)
    return 1.0 + (raw - 1.0) * w


def use_rate_bucket(profile):
    """El use_rate crudo mezcla membresía y consumo mínimo; se usa como
    bucket ordinal, no como probabilidad. Sin match es su propia categoría:
    'no está en Boom' es información, no un dato faltante."""
    if profile is None:
        return "sin_boom"
    try:
        r = float(profile["use_rate"] or 0)
    except ValueError:
        return "sin_boom"
    if r >= 0.8:
        return "fiel"
    if r >= 0.55:
        return "medio"
    if r >= 0.3:
        return "tibio"
    return "frio"


def lead_bucket(purchased_at, starts_at):
    """Cuánta anticipación tuvo la compra. Comprar con tres semanas y
    comprar en la puerta no son la misma intención."""
    p, s = parse_dt(purchased_at), parse_dt(starts_at)
    if not p or not s:
        return "desconocido"
    d = (s - p).total_seconds() / 86400.0
    if d < 0.5:
        return "mismo_dia"
    if d < 3:
        return "semana"
    if d < 10:
        return "anticipado"
    return "muy_anticipado"


def build_rows(raw, matches):
    """Una fila por entrada, con todo lo que se sabe de ella."""
    events = {e["event_id"]: e for e in load(f"{raw}/freeticket_events.csv")}
    sales = {s["sale_id"]: s for s in load(f"{raw}/freeticket_sales.csv")}
    profiles = {p["boom_user_id"]: p for p in load(f"{raw}/boom_profile.csv")}
    tickets = load(f"{raw}/freeticket_tickets.csv")

    rows = []
    for t in tickets:
        ev = events.get(t["event_id"])
        sale = sales.get(t["sale_id"])
        if not ev or not sale:
            continue
        m = matches.get(t["sale_id"])
        prof = profiles.get(m[0]) if m else None
        ci = t["checked_in"].strip().lower()
        rows.append({
            "ticket_id": t["ticket_id"],
            "event_id": t["event_id"],
            "artist_id": ev["artist_id"],
            "is_residency": ev["is_residency"] == "true",
            "month": ev["month"],
            "type": t["ticket_type"],
            "channel": sale["channel"],
            "boom": use_rate_bucket(prof),
            "lead": lead_bucket(sale["purchased_at"], ev["starts_at"]),
            "y": 1.0 if ci == "true" else (0.0 if ci == "false" else None),
        })
    return rows, events


def fit(train):
    """Estima base por tipo y los cuatro factores, en cascada."""
    model = {}

    agg = defaultdict(lambda: [0.0, 0])
    for r in train:
        a = agg[r["type"]]
        a[0] += r["y"]
        a[1] += 1
    overall = sum(r["y"] for r in train) / max(len(train), 1)
    model["base"] = {k: (v[0] + 5 * overall) / (v[1] + 5) for k, v in agg.items()}
    model["overall"] = overall

    def cascade(key, k, so_far):
        agg = defaultdict(lambda: [0.0, 0.0, 0])
        for r in train:
            p = so_far(r)
            a = agg[r[key]]
            a[0] += r["y"]
            a[1] += p
            a[2] += 1
        return {kk: shrunk_factor(v[0], v[1], v[2], k) for kk, v in agg.items()}

    p0 = lambda r: model["base"].get(r["type"], overall)
    model["artist"] = cascade("artist_id", K_ARTIST, p0)

    p1 = lambda r: p0(r) * model["artist"].get(r["artist_id"], 1.0)
    model["boom"] = cascade("boom", K_BOOM, p1)

    p2 = lambda r: p1(r) * model["boom"].get(r["boom"], 1.0)
    model["channel"] = cascade("channel", K_CHANNEL, p2)

    p3 = lambda r: p2(r) * model["channel"].get(r["channel"], 1.0)
    model["lead"] = cascade("lead", K_LEAD, p3)

    return model


def predict(model, r):
    p = model["base"].get(r["type"], model["overall"])
    p *= model["artist"].get(r["artist_id"], 1.0)
    p *= model["boom"].get(r["boom"], 1.0)
    p *= model["channel"].get(r["channel"], 1.0)
    p *= model["lead"].get(r["lead"], 1.0)
    return min(max(p, CAP_LO), CAP_HI)


def dispersion(model, rows_by_event):
    """Cuánto más ancha es la realidad que la binomial.

    Para cada evento de julio se compara el error real contra la desviación
    que predice la Poisson-binomial. Si el modelo fuera perfecto y las
    entradas independientes, la desviación de esos z sería 1. Es mayor:
    la gente no decide por separado — llueve, el acto se vuelve famoso, el
    grupo entero no aparece. Ese factor es el que ensancha p10–p90.
    """
    zs = []
    for _, rs in rows_by_event.items():
        ps = [predict(model, r) for r in rs]
        exp = sum(ps)
        var = sum(p * (1 - p) for p in ps)
        act = sum(r["y"] for r in rs)
        if var > 1:
            zs.append((act - exp) / math.sqrt(var))
    if len(zs) < 5:
        return 1.6
    # Se calibra directo contra el objetivo: el ancho que en julio habría
    # dejado adentro al 80% de los eventos. Usar la desviación estándar
    # daría un intervalo más ancho de lo necesario — cómodo para no
    # equivocarse, inútil para dimensionar la puerta.
    a = sorted(abs(z) for z in zs)
    q80 = a[min(len(a) - 1, int(math.ceil(0.8 * len(a))) - 1)]
    return max(q80 / Z10, 1.0)


def evaluate(rows):
    """Backtest honesto: se entrena sin un quinto de los eventos de julio y
    se mide contra ellos. Determinista (cada 5º evento por id ordenado) para
    que el número no cambie entre corridas."""
    july = [r for r in rows if r["month"] == "julio" and r["y"] is not None]
    ids = sorted({r["event_id"] for r in july})
    holdout = set(ids[::5])
    train = [r for r in july if r["event_id"] not in holdout]
    test = [r for r in july if r["event_id"] in holdout]
    if not test:
        return None

    model = fit(train)
    by_ev = defaultdict(list)
    for r in train:
        by_ev[r["event_id"]].append(r)
    phi = dispersion(model, by_ev)

    by_test = defaultdict(list)
    for r in test:
        by_test[r["event_id"]].append(r)

    errs, within, n_ev = [], 0, 0
    for _, rs in by_test.items():
        ps = [predict(model, r) for r in rs]
        exp, var = sum(ps), sum(p * (1 - p) for p in ps)
        sd = phi * math.sqrt(max(var, 0.0))
        act = sum(r["y"] for r in rs)
        errs.append(abs(act - exp))
        if exp - Z10 * sd <= act <= exp + Z10 * sd:
            within += 1
        n_ev += 1

    return {
        "eventos": n_ev,
        "mae": sum(errs) / n_ev,
        "cobertura_p10_p90": within / n_ev,
        "phi": phi,
    }


def arrival_curve(raw, out):
    """A qué hora entra la gente — el otro extra que cuenta.

    Minutos respecto a la hora de inicio, sobre todos los check-in de julio.
    Es lo que le dice a la puerta cuándo poner el pico de personal.
    """
    events = {e["event_id"]: e for e in load(f"{raw}/freeticket_events.csv")}
    buckets = defaultdict(int)
    total = 0
    for t in load(f"{raw}/freeticket_tickets.csv"):
        if t["checked_in"].strip().lower() != "true":
            continue
        ev = events.get(t["event_id"])
        ci, st = parse_dt(t["checked_in_at"]), parse_dt(ev["starts_at"]) if ev else None
        if not ci or not st:
            continue
        m = int((ci - st).total_seconds() // 60)
        buckets[max(-120, min(90, (m // 10) * 10))] += 1
        total += 1

    cum = 0
    with open(f"{out}/arrival_curve.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["minutos_vs_inicio", "entradas", "pct", "pct_acumulado"])
        for m in sorted(buckets):
            cum += buckets[m]
            w.writerow([m, buckets[m], round(buckets[m] / total, 4), round(cum / total, 4)])
    return total


def run(matches, raw="raw", out="out"):
    rows, events = build_rows(raw, matches)

    ev = evaluate(rows)
    if ev:
        print(f"  backtest ({ev['eventos']} eventos de julio no vistos)")
        print(f"    MAE                 {ev['mae']:.1f} personas")
        print(f"    cobertura p10-p90   {ev['cobertura_p10_p90']:.0%}  (objetivo 80%)")
        print(f"    dispersión phi      {ev['phi']:.2f}× la binomial")

    july = [r for r in rows if r["month"] == "julio" and r["y"] is not None]
    model = fit(july)
    by_ev = defaultdict(list)
    for r in july:
        by_ev[r["event_id"]].append(r)
    phi = dispersion(model, by_ev)

    aug = defaultdict(list)
    for r in rows:
        if r["month"] == "agosto":
            aug[r["event_id"]].append(r)

    out_rows = []
    for eid, rs in aug.items():
        e = events[eid]
        ps = [predict(model, r) for r in rs]
        exp, var = sum(ps), sum(p * (1 - p) for p in ps)
        sd = phi * math.sqrt(max(var, 0.0))
        sold = len(rs)
        cap = int(e["capacity"] or sold)
        out_rows.append({
            "event_id": eid,
            "expected_attendance": int(round(min(exp, sold))),
            "p10": int(round(max(0.0, exp - Z10 * sd))),
            "p90": int(round(min(float(sold), exp + Z10 * sd))),
            "tickets_sold": sold,
            "capacity": cap,
            "title": e["title"],
            "venue": e["venue"],
            "city": e["city"],
            "starts_at": e["starts_at"],
            "is_residency": e["is_residency"],
            "expected_rate": round(exp / sold, 4) if sold else 0.0,
        })
    out_rows.sort(key=lambda r: r["starts_at"])

    with open(f"{out}/forecast.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["event_id", "expected_attendance", "p10", "p90"])
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r[k] for k in ("event_id", "expected_attendance", "p10", "p90")})

    # Versión ancha: la que come el dashboard y el link de puerta.
    cols = list(out_rows[0].keys()) if out_rows else []
    with open(f"{out}/forecast_detalle.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(out_rows)

    n = arrival_curve(raw, out)
    print(f"  eventos de agosto    {len(out_rows)}")
    print(f"  entradas proyectadas {sum(r['tickets_sold'] for r in out_rows)}")
    print(f"  asistencia esperada  {sum(r['expected_attendance'] for r in out_rows)}")
    print(f"  curva de llegada     {n} check-ins de julio")

    return {"model": model, "phi": phi, "eval": ev, "forecast": out_rows}


if __name__ == "__main__":
    import json
    with open("out/matches_auditoria.csv", newline="", encoding="utf-8") as f:
        m = {r["sale_id"]: (r["boom_user_id"], float(r["confidence"]))
             for r in csv.DictReader(f)}
    res = run(m)
    with open("out/modelo.json", "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in res["model"].items()}, f, ensure_ascii=False, indent=2)
