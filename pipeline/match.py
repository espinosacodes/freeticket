"""Parte A — cruce comprador de la tiquetera ↔ usuario de Boom.

No hay ID compartido. Se bloquea por llave normalizada para no comparar
6.000 × 6.383, se puntúa cada candidato con evidencia explícita, y se exige
margen sobre el segundo mejor.

La consigna es precisión sobre cobertura: **inventarle un match a un
comprador nuevo es peor que dejarlo sin match**. Por eso todo umbral aquí
está puesto para dejar gente afuera, no para alcanzar cobertura.
"""

import csv
from collections import defaultdict

from normalize import (
    deletions,
    email_parts,
    initial_key,
    name_key,
    name_tokens,
    norm_email,
    norm_phone,
    phone_transpositions,
)

# Umbral de aceptación y margen mínimo sobre el segundo candidato.
THRESHOLD = 0.72
MARGIN = 0.08

# Pesos. Cada uno es "qué tan improbable es que esto coincida por azar".
W_EMAIL_EXACT = 0.90       # misma dirección canónica
W_EMAIL_DEL1 = 0.74        # falta/sobra una letra, mismo dominio
W_EMAIL_LOCAL = 0.58       # mismo local, otro dominio
W_PHONE_EXACT = 0.80       # 10 dígitos idénticos
W_PHONE_SWAP = 0.60        # dos dígitos adyacentes cambiados
B_NAME_EXACT = 0.14        # bonos, no bases: un nombre solo nunca alcanza
B_NAME_OVERLAP = 0.08
B_NAME_INITIAL = 0.05
B_CITY = 0.03
B_SECOND_KEY = 0.06        # email y teléfono apuntan al mismo usuario

# Un nombre por sí solo no identifica a nadie: "Juan Pérez" hay muchos.
# Solo se usa como base cuando la ciudad también coincide, y aun así queda
# por debajo del umbral salvo que algo más lo acompañe.
W_NAME_ONLY = 0.38


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Index:
    """Índices invertidos sobre Boom, para generar candidatos baratos."""

    def __init__(self, users):
        self.users = {u["boom_user_id"]: u for u in users}
        self.by_email = defaultdict(set)
        self.by_local = defaultdict(set)
        self.by_del1 = defaultdict(set)
        self.by_phone = defaultdict(set)
        self.by_name = defaultdict(set)
        self.by_initial = defaultdict(set)
        self.norm = {}

        for u in users:
            uid = u["boom_user_id"]
            full = f"{u['first_name']} {u['last_name']}"
            e = norm_email(u["email"])
            local, domain = email_parts(u["email"])
            p = norm_phone(u["phone"])
            nk = name_key(full)
            self.norm[uid] = {
                "email": e,
                "local": local,
                "domain": domain,
                "phone": p,
                "tokens": name_tokens(full),
                "name_key": nk,
                "city": (u["city"] or "").strip().lower(),
            }
            if e:
                self.by_email[e].add(uid)
                self.by_local[local].add(uid)
                for d in deletions(local):
                    self.by_del1[(d, domain)].add(uid)
            if p:
                self.by_phone[p].add(uid)
            if nk:
                self.by_name[nk].add(uid)
                self.by_initial[initial_key(full)].add(uid)

    def candidates(self, email, local, domain, phone, nk, ik):
        c = set()
        if email:
            c |= self.by_email.get(email, set())
            c |= self.by_local.get(local, set())
            c |= self.by_del1.get((local, domain), set())
            for d in deletions(local):
                c |= self.by_del1.get((d, domain), set())
        if phone:
            c |= self.by_phone.get(phone, set())
            for v in phone_transpositions(phone):
                c |= self.by_phone.get(v, set())
        if nk:
            c |= self.by_name.get(nk, set())
            if ik:
                c |= self.by_initial.get(ik, set())
        return c


def score(sale_keys, u, why):
    """Puntúa un candidato. `why` recoge la evidencia para poder auditarla."""
    email, local, domain, phone, tokens, nk, ik, city = sale_keys
    base, ev = 0.0, []

    # --- base: la llave fuerte ---
    if email and u["email"] and email == u["email"]:
        base, ev = W_EMAIL_EXACT, ["email_exact"]
    elif local and domain and u["local"] and domain == u["domain"] and (
        local in deletions(u["local"]) or u["local"] in deletions(local)
    ):
        base, ev = W_EMAIL_DEL1, ["email_1letra"]
    elif local and u["local"] and local == u["local"]:
        base, ev = W_EMAIL_LOCAL, ["email_local_otro_dominio"]

    if phone and u["phone"]:
        if phone == u["phone"]:
            if base:
                base += B_SECOND_KEY
                ev.append("telefono_exacto")
            else:
                base, ev = W_PHONE_EXACT, ["telefono_exacto"]
        elif phone in phone_transpositions(u["phone"]):
            if not base:
                base, ev = W_PHONE_SWAP, ["telefono_digitos_cambiados"]

    if not base and nk and nk == u["name_key"] and city and city == u["city"]:
        base, ev = W_NAME_ONLY, ["nombre_y_ciudad"]

    if not base:
        return 0.0, []

    # --- bonos de corroboración ---
    inter = tokens & u["tokens"]
    if nk and nk == u["name_key"]:
        base += B_NAME_EXACT
        ev.append("nombre_exacto")
    elif len(inter) >= 2:
        base += B_NAME_OVERLAP
        ev.append("nombre_2_tokens")
    elif ik and ik == initial_key(" ".join(sorted(u["tokens"]))):
        base += B_NAME_INITIAL
        ev.append("nombre_inicial")

    if city and city == u["city"]:
        base += B_CITY
        ev.append("ciudad")

    # --- castigo: el correo de la pareja ---
    # Email idéntico pero sin UN solo token de nombre en común es la firma de
    # "compró con el correo de su pareja". El match al titular del correo es
    # probablemente la persona equivocada: se reporta, pero no con confianza
    # alta. Bajarlo aquí es lo que evita ensuciar la proyección después.
    if "email_exact" in ev and tokens and u["tokens"] and not inter:
        base -= 0.22
        ev.append("nombre_no_coincide(pareja?)")

    why.extend(ev)
    return min(base, 0.99), ev


def run(raw="raw", out="out"):
    users = load(f"{raw}/boom_users.csv")
    sales = load(f"{raw}/freeticket_sales.csv")
    events = {e["event_id"]: e for e in load(f"{raw}/freeticket_events.csv")}

    idx = Index(users)
    rows, stats = [], defaultdict(int)

    for s in sales:
        ev_city = (events.get(s["event_id"], {}).get("city") or "").strip().lower()
        email = norm_email(s["buyer_email"])
        local, domain = email_parts(s["buyer_email"])
        phone = norm_phone(s["buyer_phone"])
        tokens = name_tokens(s["buyer_name"])
        nk = name_key(s["buyer_name"])
        ik = initial_key(s["buyer_name"])
        keys = (email, local, domain, phone, tokens, nk, ik, ev_city)

        scored = []
        for uid in idx.candidates(email, local, domain, phone, nk, ik):
            why = []
            sc, ev = score(keys, idx.norm[uid], why)
            if sc > 0:
                scored.append((sc, uid, ev))

        if not scored:
            stats["sin_candidato"] += 1
            continue

        scored.sort(key=lambda x: (-x[0], x[1]))
        top = scored[0]
        runner = scored[1][0] if len(scored) > 1 else 0.0

        if top[0] < THRESHOLD:
            stats["bajo_umbral"] += 1
            continue
        # Ambigüedad: dos candidatos casi igual de buenos. Sin desempate no se
        # elige uno a la suerte — se deja sin match.
        if top[0] - runner < MARGIN and "email_exact" not in top[2]:
            stats["ambiguo"] += 1
            continue

        stats["match"] += 1
        rows.append({
            "sale_id": s["sale_id"],
            "boom_user_id": top[1],
            "confidence": round(top[0], 3),
            "evidencia": "+".join(top[2]),
        })

    with open(f"{out}/matches.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["sale_id", "boom_user_id", "confidence"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in ("sale_id", "boom_user_id", "confidence")})

    # Versión auditable: misma decisión, con el porqué al lado.
    with open(f"{out}/matches_auditoria.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["sale_id", "boom_user_id", "confidence", "evidencia"])
        w.writeheader()
        w.writerows(rows)

    total = len(sales)
    print(f"  ventas               {total}")
    print(f"  match                {stats['match']} ({stats['match']/total:.1%})")
    print(f"  sin candidato        {stats['sin_candidato']}")
    print(f"  bajo umbral          {stats['bajo_umbral']}")
    print(f"  ambiguo (descartado) {stats['ambiguo']}")
    return {r["sale_id"]: (r["boom_user_id"], r["confidence"]) for r in rows}


if __name__ == "__main__":
    run()
