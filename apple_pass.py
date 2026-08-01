"""Generate Apple Wallet event tickets (.pkpass) for FreeTicket shows.

Companion to wallet_pass.py (Google Wallet). Both read the same show config from
.env, so EVENT_NAME / VENUE_NAME / EVENT_START describe one show in both wallets.

Usage:
    python apple_pass.py --make-assets                          # placeholder art, once
    python apple_pass.py --holder "Santiago Espinosa" --ticket FT-000123
    python apple_pass.py --holder "..." --ticket FT-000123 --provider pass2u

Providers:
    local   sign with your own Pass Type ID cert (.p12). Requires the paid Apple
            Developer Program — a free personal team cannot create one.
    pass2u  Pass2U signs with their certificate. Free tier, no Apple account.
            See the note on PASS2U_API in the pass2u_link() docstring.
"""

import argparse
import hashlib
import json
import os
import struct
import uuid
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets" / "apple"
OUT = ROOT / "out"

MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
         "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

# Apple rejects a pass missing any icon size. logo/strip are optional but the
# pass looks unfinished without them.
REQUIRED_IMAGES = ["icon.png", "icon@2x.png", "icon@3x.png"]
OPTIONAL_IMAGES = ["logo.png", "logo@2x.png", "strip.png", "strip@2x.png"]

IMAGE_SPECS = {
    "icon.png": (29, 29),
    "icon@2x.png": (58, 58),
    "icon@3x.png": (87, 87),
    "logo.png": (160, 50),
    "logo@2x.png": (320, 100),
    "strip.png": (375, 98),
    "strip@2x.png": (750, 196),
}


# ── placeholder art ──────────────────────────────────────────────────────────

def _solid_png(width, height, rgb):
    """Minimal solid-colour PNG. Avoids a Pillow dependency for placeholders."""
    row = bytes(rgb) * width
    raw = b"".join(b"\x00" + row for _ in range(height))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_assets():
    """Write placeholder icons/logo/strip so the pipeline runs before real art exists."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, (w, h) in IMAGE_SPECS.items():
        colour = (255, 214, 10) if name.startswith("icon") else (18, 18, 18)
        (ASSETS / name).write_bytes(_solid_png(w, h, colour))
    print(f"wrote {len(IMAGE_SPECS)} placeholder images to {ASSETS}")


# ── geocoding ────────────────────────────────────────────────────────────────

GEOCODE_CACHE = ROOT / ".geocode-cache.json"


def geocode(address):
    """Resolve an address to (lat, lon) via Nominatim. Returns None if not found.

    Results are cached to .geocode-cache.json, which is committed on purpose: the
    demo then builds passes with no network call and no rate limit to trip over.
    Nominatim asks for <= 1 req/s and a User-Agent that identifies the caller.
    """
    cache = json.loads(GEOCODE_CACHE.read_text()) if GEOCODE_CACHE.exists() else {}
    if address in cache:
        return tuple(cache[address]) if cache[address] else None

    import requests

    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json", "limit": 1},
        headers={"User-Agent": "FreeTicket-Wallet/1.0 (mail@plada.ai)"},
        timeout=15,
    )
    r.raise_for_status()
    hits = r.json()
    coords = (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None

    cache[address] = list(coords) if coords else None
    GEOCODE_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return coords


def venue_coords(allow_geocode=True):
    """VENUE_LAT/VENUE_LON win if set; otherwise derive them from VENUE_ADDRESS."""
    lat, lon = os.environ.get("VENUE_LAT"), os.environ.get("VENUE_LON")
    if lat and lon:
        return float(lat), float(lon)
    address = os.environ.get("VENUE_ADDRESS")
    if not (address and allow_geocode):
        return None
    return geocode(address)


# ── pass.json ────────────────────────────────────────────────────────────────

def build_pass_json(holder, ticket_number, points=0, seat=None, serial=None,
                    allow_geocode=True):
    start = datetime.fromisoformat(os.environ["EVENT_START"])
    serial = serial or str(uuid.uuid4())

    aux = [
        {"key": "holder", "label": "ASISTENTE", "value": holder},
        {"key": "tier", "label": "ENTRADA", "value": "Gratis con membresía"},
    ]
    if seat:
        aux.append({"key": "seat", "label": "PUESTO", "value": seat})

    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": os.environ.get("PASS_TYPE_IDENTIFIER", ""),
        "teamIdentifier": os.environ.get("TEAM_IDENTIFIER", ""),
        "organizationName": os.environ.get("WALLET_ISSUER_NAME", "FreeTicket"),
        "serialNumber": serial,
        "description": f"Entrada FreeTicket — {os.environ['EVENT_NAME']}",

        "logoText": os.environ.get("WALLET_ISSUER_NAME", "FreeTicket"),
        "foregroundColor": "rgb(255,255,255)",
        "backgroundColor": "rgb(26,26,26)",
        "labelColor": "rgb(255,214,10)",

        "relevantDate": os.environ["EVENT_START"],
        "expirationDate": os.environ["EVENT_END"],
        # A comedy ticket is per-person: keep it off AirDrop.
        "sharingProhibited": True,

        "barcodes": [{
            "format": "PKBarcodeFormatQR",
            "message": ticket_number,
            "messageEncoding": "iso-8859-1",
            "altText": ticket_number,
        }],

        "eventTicket": {
            "headerFields": [
                {"key": "date", "label": "FECHA",
                 "value": f"{start.day} {MESES[start.month - 1]}"},
            ],
            "primaryFields": [
                {"key": "event", "label": "SHOW", "value": os.environ["EVENT_NAME"]},
            ],
            "secondaryFields": [
                {"key": "venue", "label": "VENUE", "value": os.environ["VENUE_NAME"]},
                {"key": "time", "label": "HORA",
                 "value": start.strftime("%I:%M %p").lstrip("0")},
            ],
            "auxiliaryFields": aux,
            "backFields": [
                {"key": "points", "label": "Puntos", "value": f"+{points} al asistir"},
                {"key": "address", "label": "Dirección",
                 "value": os.environ.get("VENUE_ADDRESS", "")},
                {"key": "terms", "label": "Términos",
                 "value": "Llegar 15 minutos antes. Entrada sujeta a aforo."},
            ],
        },

        "userInfo": {"ticketNumber": ticket_number, "serial": serial},
    }

    # Lock-screen surfacing when the attendee reaches the venue. This is the
    # signal that turns a pass into attendance data. Baked in at build time —
    # a signed pass cannot look this up later.
    coords = venue_coords(allow_geocode)
    if coords:
        pass_json["locations"] = [{
            "latitude": coords[0],
            "longitude": coords[1],
            "relevantText": f"Tu show en {os.environ['VENUE_NAME']} empieza pronto",
        }]
        pass_json["maxDistance"] = 500

    if os.environ.get("APPLE_STORE_ID"):
        pass_json["associatedStoreIdentifiers"] = [int(os.environ["APPLE_STORE_ID"])]

    # Only meaningful once a backend implements the Wallet web service endpoints.
    if os.environ.get("PASS_WEB_SERVICE_URL") and os.environ.get("PASS_AUTH_TOKEN"):
        pass_json["webServiceURL"] = os.environ["PASS_WEB_SERVICE_URL"]
        pass_json["authenticationToken"] = os.environ["PASS_AUTH_TOKEN"]

    return pass_json


# ── bundle + signature ───────────────────────────────────────────────────────

def collect_images():
    if not ASSETS.exists():
        raise SystemExit(f"no assets at {ASSETS} — run: python apple_pass.py --make-assets")
    missing = [n for n in REQUIRED_IMAGES if not (ASSETS / n).exists()]
    if missing:
        raise SystemExit(f"missing required images: {', '.join(missing)}")
    names = REQUIRED_IMAGES + [n for n in OPTIONAL_IMAGES if (ASSETS / n).exists()]
    return {n: (ASSETS / n).read_bytes() for n in names}


def sign_manifest(manifest_bytes):
    """Detached PKCS#7 over manifest.json, per the Wallet spec.

    The signing certificate must be an Apple-issued Pass Type ID certificate whose
    UID equals passTypeIdentifier and whose OU equals teamIdentifier. iOS verifies
    both, so a self-signed or Apple Development certificate will not install.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding, pkcs7, pkcs12
    from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate

    p12_path = Path(os.environ["APPLE_PASS_P12"])
    wwdr_path = Path(os.environ["APPLE_WWDR_CERT"])
    passphrase = os.environ.get("APPLE_PASS_P12_PASSWORD") or None

    key, cert, _ = pkcs12.load_key_and_certificates(
        p12_path.read_bytes(),
        passphrase.encode() if passphrase else None,
    )
    if key is None or cert is None:
        raise SystemExit(f"could not load key/cert from {p12_path}")

    raw = wwdr_path.read_bytes()
    wwdr = (load_pem_x509_certificate(raw) if raw.lstrip().startswith(b"-----")
            else load_der_x509_certificate(raw))

    return (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .add_certificate(wwdr)
        # Binary is required: without it the builder canonicalises LF to CRLF and
        # signs bytes that differ from the manifest.json actually in the bundle.
        .sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature,
                             pkcs7.PKCS7Options.Binary])
    )


def build_pkpass(pass_json, out_path, sign=True):
    files = {"pass.json": json.dumps(pass_json, ensure_ascii=False, indent=2).encode()}
    files.update(collect_images())

    # manifest.json maps every bundled file to its SHA-1. Apple still specifies SHA-1 here.
    manifest = {name: hashlib.sha1(data).hexdigest() for name, data in files.items()}
    manifest_bytes = json.dumps(manifest, indent=2).encode()
    files["manifest.json"] = manifest_bytes

    if sign:
        files["signature"] = sign_manifest(manifest_bytes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out_path


# ── pass2u ───────────────────────────────────────────────────────────────────

def pass2u_link(pass_json, ticket_number):
    """Hand the pass to Pass2U, which signs it with their Pass Type ID certificate.

    NOTE: verify this request shape against https://www.pass2u.net/api/ before the
    demo. Pass2U's v2 API is versioned and the field names below reflect the model
    -based flow (you create a pass "model" in their dashboard, then POST per-pass
    overrides). The rest of this file does not depend on it.
    """
    import requests

    api_key = os.environ["PASS2U_API_KEY"]
    model_id = os.environ["PASS2U_MODEL_ID"]
    ticket = pass_json["eventTicket"]

    fields = [
        {"key": f["key"], "label": f.get("label", ""), "value": f["value"]}
        for group in ("headerFields", "primaryFields", "secondaryFields",
                      "auxiliaryFields", "backFields")
        for f in ticket[group]
    ]

    body = {
        "barcode": {"message": ticket_number, "altText": ticket_number},
        "fields": fields,
        "expirationDate": pass_json["expirationDate"],
    }

    r = requests.post(
        f"https://api.pass2u.net/v2/models/{model_id}/passes",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return f"https://www.pass2u.net/d/{r.json()['passId']}"


# ── cli ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--make-assets", action="store_true",
                   help="write placeholder images and exit")
    p.add_argument("--holder")
    p.add_argument("--ticket", help="ticket number / QR value, e.g. FT-000123")
    p.add_argument("--points", type=int, default=0)
    p.add_argument("--seat")
    p.add_argument("--provider", choices=["local", "pass2u"],
                   default=os.environ.get("APPLE_PASS_PROVIDER", "local"))
    p.add_argument("--unsigned", action="store_true",
                   help="build the bundle without signing (inspection only — will not install)")
    p.add_argument("--no-geocode", action="store_true",
                   help="skip the address lookup; omit locations unless VENUE_LAT/LON are set")
    p.add_argument("--out")
    a = p.parse_args()

    if a.make_assets:
        make_assets()
        raise SystemExit(0)

    if not (a.holder and a.ticket):
        p.error("--holder and --ticket are required")

    pass_json = build_pass_json(a.holder, a.ticket, a.points, a.seat,
                                allow_geocode=not a.no_geocode)

    if a.provider == "pass2u":
        print(pass2u_link(pass_json, a.ticket))
    else:
        out = Path(a.out) if a.out else OUT / f"{a.ticket}.pkpass"
        build_pkpass(pass_json, out, sign=not a.unsigned)
        print(out)
        if a.unsigned:
            print("UNSIGNED — inspection only, iOS will reject this file.")
