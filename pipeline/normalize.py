"""Limpieza de las tres llaves sucias: email, teléfono, nombre.

El ruido está puesto a propósito por el organizador. Cada función aquí
deshace UN tipo de ruido y deja la llave en una forma comparable.
"""

import re
import unicodedata

# Dominios mal escritos que aparecen en el dataset. La lista es corta y
# explícita a propósito: un corrector genérico inventaría matches.
DOMAIN_TYPOS = {
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gnail.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
}


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def norm_email(raw):
    """MAYÚSCULAS, alias +algo y dominio mal escrito -> forma canónica."""
    if not raw:
        return ""
    e = strip_accents(raw).strip().lower()
    if "@" not in e:
        return ""
    local, _, domain = e.rpartition("@")
    local = local.split("+", 1)[0]          # ana+shows@ -> ana@
    domain = DOMAIN_TYPOS.get(domain, domain)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")       # gmail ignora los puntos
        domain = "gmail.com"
    return f"{local}@{domain}"


def email_parts(raw):
    e = norm_email(raw)
    if not e:
        return "", ""
    local, _, domain = e.rpartition("@")
    return local, domain


def norm_phone(raw):
    """Cinco formatos distintos -> los últimos 10 dígitos.

    Colombia: móvil de 10 dígitos. Se descarta el indicativo +57 y cualquier
    separador. Menos de 10 dígitos se considera inutilizable, no se adivina.
    """
    if not raw:
        return ""
    d = re.sub(r"\D", "", raw)
    if d.startswith("57") and len(d) == 12:
        d = d[2:]
    return d[-10:] if len(d) >= 10 else ""


def phone_transpositions(p):
    """Variantes con dos dígitos adyacentes intercambiados.

    El organizador dice que a veces vienen dos dígitos cambiados de orden.
    Nueve variantes por teléfono: barato y mucho más preciso que una
    distancia de edición genérica.
    """
    if len(p) != 10:
        return set()
    out = set()
    for i in range(9):
        if p[i] != p[i + 1]:
            out.add(p[:i] + p[i + 1] + p[i] + p[i + 2:])
    return out


def deletions(s):
    """Variantes con un carácter borrado — atrapa 'le falta una letra'."""
    if len(s) < 5:                            # en locales cortos hay colisión
        return set()
    return {s[:i] + s[i + 1:] for i in range(len(s))}


PARTICLES = {"de", "del", "la", "las", "los", "san", "santa", "da", "di"}


def name_tokens(raw):
    """Sin tildes, en minúscula, sin partículas, como conjunto.

    Devolver un conjunto resuelve de una vez 'apellido primero' y el
    'segundo apellido que Boom no registró': se compara por intersección,
    no por orden ni por longitud.
    """
    if not raw:
        return frozenset()
    s = strip_accents(raw).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return frozenset(t for t in s.split() if len(t) > 1 and t not in PARTICLES)


def name_key(raw):
    """Clave canónica de bloqueo: tokens ordenados alfabéticamente."""
    return " ".join(sorted(name_tokens(raw)))


def initial_key(raw):
    """Clave laxa: primer token + inicial del resto. Para 'solo la inicial'."""
    t = sorted(name_tokens(raw))
    if not t:
        return ""
    return t[0] + "|" + "".join(x[0] for x in t[1:])
