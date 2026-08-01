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


def _load_source(source):
    """Fetch the brand image from a URL or local path. Returns bytes, or None."""
    source = source or os.environ.get("LOGO_URI")
    if not source:
        return None
    if source.startswith(("http://", "https://")):
        import requests
        r = requests.get(source, timeout=20)
        r.raise_for_status()
        return r.content
    path = Path(source)
    return path.read_bytes() if path.exists() else None


def make_assets(source=None):
    """Cut the Apple-required image sizes from the brand logo.

    Defaults to LOGO_URI — the same image the Google pass uses — so both wallets
    render the same mark. Falls back to solid placeholders if it can't be loaded.
    """
    ASSETS.mkdir(parents=True, exist_ok=True)
    raw = _load_source(source)

    if raw is None:
        for name, (w, h) in IMAGE_SPECS.items():
            colour = (255, 214, 10) if name.startswith("icon") else (18, 18, 18)
            (ASSETS / name).write_bytes(_solid_png(w, h, colour))
        print(f"no source image — wrote {len(IMAGE_SPECS)} placeholders to {ASSETS}")
        return

    import io

    from PIL import Image

    src = Image.open(io.BytesIO(raw)).convert("RGBA")
    written = []
    for name, (w, h) in IMAGE_SPECS.items():
        if name.startswith("strip"):
            continue  # strip is banner art, not the logo — handled below
        if name.startswith("icon"):
            # Icons must fill the square — Wallet masks them to a rounded rect.
            img = src.resize((w, h), Image.LANCZOS)
        else:
            # logo is a bounding box: fit inside, never stretch.
            img = src.copy()
            img.thumbnail((w, h), Image.LANCZOS)
        img.save(ASSETS / name, "PNG")
        written.append(name)

    # A square logo squeezed into the 375x98 strip box just yields a 98x98 square,
    # so only build a strip when there is real banner art to build it from.
    hero = _load_source(os.environ.get("HERO_URI")) if os.environ.get("HERO_URI") else None
    for name in ("strip.png", "strip@2x.png"):
        target = ASSETS / name
        if hero:
            w, h = IMAGE_SPECS[name]
            img = Image.open(io.BytesIO(hero)).convert("RGBA")
            img = img.resize((w, h), Image.LANCZOS)
            img.save(target, "PNG")
            written.append(name)
        elif target.exists():
            target.unlink()  # drop stale placeholders

    print(f"wrote {len(written)} images to {ASSETS}: {', '.join(written)}")
    if not hero:
        print("no HERO_URI — pass will render without a strip image")


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


# ── preview ──────────────────────────────────────────────────────────────────

def write_preview(pass_json, out_path):
    """Render pass.json as HTML approximating the Wallet eventTicket layout.

    An unsigned .pkpass cannot be opened by iOS or macOS, so this is the only way
    to actually look at a pass before the signing certificate exists. It renders
    from the real pass.json, so what you see is what the fields contain.
    """
    import base64
    import io

    import segno

    t = pass_json["eventTicket"]

    def data_uri(name):
        p = ASSETS / name
        return ("data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
                if p.exists() else None)

    logo_uri, strip_uri = data_uri("logo@2x.png"), data_uri("strip@2x.png")
    brand = (f'<img class="logo" src="{logo_uri}" alt="">' if logo_uri
             else f'<div class="dot"></div>')
    strip = (f'<div class="strip" style="background-image:url({strip_uri})"></div>'
             if strip_uri else "")
    one = lambda group: t[group][0] if t[group] else {"label": "", "value": ""}

    buf = io.BytesIO()  # segno's writers emit bytes, not str
    segno.make(pass_json["barcodes"][0]["message"], error="q").save(
        buf, kind="svg", scale=4, dark="#000", light="#fff", border=2, xmldecl=False, svgns=True
    )
    qr_svg = buf.getvalue().decode()

    row = lambda f: (f'<div class="f"><span class="l">{f.get("label","")}</span>'
                     f'<span class="v">{f["value"]}</span></div>')
    back = "".join(
        f'<div class="b"><span class="l">{f.get("label","")}</span>'
        f'<span class="bv">{f["value"]}</span></div>'
        for f in t["backFields"]
    )

    html = f"""<!doctype html><meta charset="utf-8">
<title>{pass_json["description"]}</title>
<style>
  body {{ background:#0b0b0c; color:#fff; font:15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         display:flex; flex-wrap:wrap; gap:28px; justify-content:center; align-items:flex-start;
         padding:44px 20px; margin:0; }}
  .pass {{ width:330px; background:{pass_json["backgroundColor"].replace("rgb","rgba").replace(")",",1)")};
           border-radius:14px; overflow:hidden; box-shadow:0 12px 40px rgba(0,0,0,.6); }}
  .top {{ display:flex; justify-content:space-between; align-items:center; padding:14px 16px 10px; }}
  .brand {{ display:flex; align-items:center; gap:8px; font-weight:600; font-size:15px; }}
  .dot {{ width:22px; height:22px; border-radius:5px; background:{pass_json["labelColor"]}; }}
  .logo {{ height:24px; width:auto; display:block; }}
  .strip {{ height:92px; background-size:cover; background-position:center; }}
  .body {{ padding:14px 16px 18px; }}
  .l {{ display:block; color:{pass_json["labelColor"]}; font-size:9.5px; font-weight:600;
        letter-spacing:.09em; margin-bottom:3px; }}
  .v {{ font-size:15px; }}
  .primary .v {{ font-size:23px; font-weight:600; }}
  .grid {{ display:flex; gap:22px; margin-top:14px; flex-wrap:wrap; }}
  .grid .f {{ flex:1; min-width:88px; }}
  .qr {{ background:#fff; border-radius:9px; padding:9px; width:max-content;
         margin:20px auto 6px; }}
  .qr svg {{ display:block; }}
  .alt {{ text-align:center; font-size:11px; color:#8a8a90; letter-spacing:.06em; }}
  .card {{ width:330px; background:#151517; border-radius:14px; padding:6px 16px 14px; }}
  .card h3 {{ font-size:11px; letter-spacing:.1em; color:#8a8a90; font-weight:600; margin:14px 0 4px; }}
  .b {{ padding:11px 0; border-bottom:1px solid #232326; }}
  .b:last-child {{ border-bottom:0; }}
  .bv {{ font-size:14px; color:#d8d8dc; }}
  .note {{ width:100%; text-align:center; color:#6a6a72; font-size:12px; }}
</style>
<div class="pass">
  <div class="top">
    <div class="brand">{brand}{pass_json["logoText"]}</div>
    <div style="text-align:right">{row(one("headerFields"))}</div>
  </div>
  {strip}
  <div class="body">
    <div class="primary">{row(one("primaryFields"))}</div>
    <div class="grid">{"".join(row(f) for f in t["secondaryFields"])}</div>
    <div class="grid">{"".join(row(f) for f in t["auxiliaryFields"])}</div>
    <div class="qr">{qr_svg}</div>
    <div class="alt">{pass_json["barcodes"][0]["altText"]}</div>
  </div>
</div>
<div class="card"><h3>REVERSO</h3>{back}</div>
<p class="note">Vista previa desde pass.json — no es el render de iOS.</p>
"""
    out_path.write_text(html, encoding="utf-8")
    return out_path


# ── pass2u ───────────────────────────────────────────────────────────────────

P2U_IMAGE_CACHE = ROOT / ".pass2u-images.json"

# Pass2U's recommended @2x dimensions per image type.
P2U_IMAGE_SIZES = {"icon": (58, 58), "logo": (100, 100),
                   "thumbnail": (180, 180), "background": (360, 440)}


def pass2u_images(refresh=False):
    """Upload brand images to Pass2U and return {type: hex}.

    Hexes are stable, so they're cached — re-uploading on every pass would be
    pure waste. The Event Ticket Layout 1 model always renders a background and
    thumbnail; there is no way to switch them off. So both are rendered as solid
    backgroundColor (with the logo inset on the thumbnail), which makes them
    disappear into the card the way the flat Google Wallet ticket looks.
    """
    if P2U_IMAGE_CACHE.exists() and not refresh:
        return json.loads(P2U_IMAGE_CACHE.read_text())

    import io

    import requests
    from PIL import Image

    src = Image.open(io.BytesIO(_load_source(None))).convert("RGBA")
    dark = tuple(int(n) for n in
                 os.environ.get("PASS_BG_RGB", "26,26,26").split(",")) + (255,)

    def flat(w, h, logo_px=None):
        im = Image.new("RGBA", (w, h), dark)
        if logo_px:
            lg = src.resize((logo_px, logo_px), Image.LANCZOS)
            im.paste(lg, ((w - logo_px) // 2, (h - logo_px) // 2), lg)
        return im

    built = {
        "icon": src.resize(P2U_IMAGE_SIZES["icon"], Image.LANCZOS),
        "logo": src.resize(P2U_IMAGE_SIZES["logo"], Image.LANCZOS),
        "thumbnail": flat(*P2U_IMAGE_SIZES["thumbnail"], logo_px=120),
        "background": flat(*P2U_IMAGE_SIZES["background"]),
    }

    headers = {"x-api-key": os.environ["PASS2U_API_KEY"],
               "Accept": "application/json", "Content-Type": "image/png"}
    hexes = {}
    for name, im in built.items():
        buf = io.BytesIO()
        im.save(buf, "PNG")
        r = requests.post("https://api.pass2u.net/v2/images",
                          headers=headers, data=buf.getvalue(), timeout=30)
        if not r.ok:
            raise SystemExit(f"pass2u image {name}: {r.status_code} {r.text[:200]}")
        hexes[name] = r.json()["hex"]

    P2U_IMAGE_CACHE.write_text(json.dumps(hexes, indent=2))
    return hexes


def pass2u_body(pass_json, ticket_number, images=None):
    """The exact JSON payload POSTed to Pass2U. Split out so it can be dry-run:
    credits are finite and non-replicable barcodes burn the ticket code on use."""
    ticket = pass_json["eventTicket"]

    # Only Dynamic model fields are settable; keys must match the Model Designer.
    fields = [
        {"key": f["key"], "label": f.get("label", ""), "value": f["value"]}
        for group in ("headerFields", "primaryFields", "secondaryFields",
                      "auxiliaryFields", "backFields")
        for f in ticket[group]
    ]

    # Mirror the locally-built pass so both providers render the same ticket.
    body = {
        "description": pass_json["description"],
        "organizationName": pass_json["organizationName"],
        "logoText": pass_json["logoText"],
        "foregroundColor": pass_json["foregroundColor"],
        "backgroundColor": pass_json["backgroundColor"],
        "labelColor": pass_json["labelColor"],
        "relevantDate": pass_json["relevantDate"],
        "expirationDate": pass_json["expirationDate"],
        "fields": fields,
        "barcode": {"message": ticket_number, "altText": ticket_number},
    }
    if "locations" in pass_json:
        body["locations"] = pass_json["locations"]
        body["maxDistance"] = pass_json["maxDistance"]
    if images:
        body["images"] = [{"type": t, "hex": h} for t, h in images.items()]
    return body


def pass2u_link(pass_json, ticket_number, send_fields=True):
    """Hand the pass to Pass2U, which signs it with their Pass Type ID certificate.

    This is the only route to a pass that installs in native Apple Wallet without
    the $99 Apple Developer Program. Returns the public download URL — open it on
    the iPhone and Wallet offers "Add".

    Prerequisites in the Pass2U dashboard (manual, ~10 min):
      1. Create an Event Ticket model; note its Model ID.
      2. Every field you want to set here must be typed **Dynamic** in the Model
         Designer, with a Key matching the keys below. Fixed/Points/Credits fields
         are ignored by the API.
      3. Set Barcode Type to "Dynamic - assigned by CSV file or API".

    Request shape verified against Pass2U Pass API User Guide v2.2.3 (2023-03-01).
    """
    import requests

    api_key = os.environ.get("PASS2U_API_KEY")
    model_id = os.environ.get("PASS2U_MODEL_ID")
    if not (api_key and model_id):
        raise SystemExit(
            "PASS2U_API_KEY and PASS2U_MODEL_ID are not set — see .env.example.\n"
            "Both come from the Pass2U dashboard; the trial API key is free for 30 days."
        )
    body = pass2u_body(pass_json, ticket_number, images=pass2u_images())
    if send_fields is False:
        body.pop("fields", None)

    r = requests.post(
        f"https://api.pass2u.net/v2/models/{model_id}/passes",
        headers={"x-api-key": api_key,
                 "Accept": "application/json",
                 "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if not r.ok:
        if "not defined as 'Dynamic'" in r.text:
            raise SystemExit(
                f"pass2u rejected a field: {r.text[:200]}\n\n"
                "Pass2U hard-rejects field keys that aren't typed Dynamic in the\n"
                "Model Designer — it does NOT fall back to model defaults.\n"
                "Either type those keys as Dynamic in the model, or re-run with\n"
                "--no-fields to issue a pass carrying only images/colors/barcode."
            )
        raise SystemExit(f"pass2u {r.status_code}: {r.text[:400]}")
    return f"https://www.pass2u.net/d/{r.json()['passId']}"


# ── cli ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--make-assets", action="store_true",
                   help="cut Apple image sizes from LOGO_URI (or --source) and exit")
    p.add_argument("--source", help="brand image URL or path; defaults to LOGO_URI")
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
    p.add_argument("--preview", action="store_true",
                   help="also write an HTML rendering next to the .pkpass")
    p.add_argument("--no-fields", action="store_true",
                   help="pass2u: skip field overrides (use until model fields are Dynamic)")
    p.add_argument("--out")
    a = p.parse_args()

    if a.make_assets:
        make_assets(a.source)
        raise SystemExit(0)

    if not (a.holder and a.ticket):
        p.error("--holder and --ticket are required")

    pass_json = build_pass_json(a.holder, a.ticket, a.points, a.seat,
                                allow_geocode=not a.no_geocode)

    if a.provider == "pass2u":
        print(pass2u_link(pass_json, a.ticket, send_fields=not a.no_fields))
    else:
        out = Path(a.out) if a.out else OUT / f"{a.ticket}.pkpass"
        build_pkpass(pass_json, out, sign=not a.unsigned)
        print(out)
        if a.preview:
            print(write_preview(pass_json, out.with_suffix(".html")))
        if a.unsigned:
            print("UNSIGNED — inspection only, iOS will reject this file.")
