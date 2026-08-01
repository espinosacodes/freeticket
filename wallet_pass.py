"""Generate Google Wallet event tickets for FreeTicket shows.

Usage:
    python wallet_pass.py --holder "Santiago Espinosa" --ticket FT-000123

Prints an "Add to Google Wallet" link. The event class is created once (idempotent);
each ticket is signed into a JWT save-link, so no per-ticket API write is needed.
"""

import argparse
import json
import os

import jwt
import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2 import service_account

load_dotenv()

SCOPE = "https://www.googleapis.com/auth/wallet_object.issuer"
API = "https://walletobjects.googleapis.com/walletobjects/v1"
SAVE_URL = "https://pay.google.com/gp/v/save/"

ISSUER_ID = os.environ["GOOGLE_WALLET_ISSUER_ID"]
KEY_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "secrets/wallet-sa.json")
CLASS_ID = f"{ISSUER_ID}.{os.environ.get('WALLET_CLASS_SUFFIX', 'freeticket_show')}"
ORIGINS = [o.strip() for o in os.environ.get("WALLET_ORIGINS", "").split(",") if o.strip()]

credentials = service_account.Credentials.from_service_account_file(KEY_FILE, scopes=[SCOPE])
key = json.load(open(KEY_FILE))


def session():
    credentials.refresh(Request())
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {credentials.token}"
    return s


def event_class():
    """The show itself — shared by every ticket to it."""
    cls = {
        "id": CLASS_ID,
        "issuerName": os.environ.get("WALLET_ISSUER_NAME", "FreeTicket"),
        "reviewStatus": "UNDER_REVIEW",
        "eventName": {
            "defaultValue": {"language": "es-CO", "value": os.environ["EVENT_NAME"]}
        },
        "venue": {
            "name": {"defaultValue": {"language": "es-CO", "value": os.environ["VENUE_NAME"]}},
            "address": {
                "defaultValue": {"language": "es-CO", "value": os.environ["VENUE_ADDRESS"]}
            },
        },
        "dateTime": {
            "start": os.environ["EVENT_START"],
            "end": os.environ["EVENT_END"],
        },
        "homepageUri": {
            "uri": os.environ.get("EVENT_HOMEPAGE", "https://appfreeticket.com"),
            "description": "FreeTicket",
        },
        "hexBackgroundColor": os.environ.get("HEX_BACKGROUND_COLOR", "#1a1a1a"),
    }
    if os.environ.get("LOGO_URI"):
        cls["logo"] = {"sourceUri": {"uri": os.environ["LOGO_URI"]}}
    if os.environ.get("HERO_URI"):
        cls["heroImage"] = {"sourceUri": {"uri": os.environ["HERO_URI"]}}
    return cls


def ensure_class():
    s = session()
    r = s.get(f"{API}/eventTicketClass/{CLASS_ID}")
    if r.status_code == 404:
        r = s.post(f"{API}/eventTicketClass", json=event_class())
    else:
        r = s.put(f"{API}/eventTicketClass/{CLASS_ID}", json=event_class())
    r.raise_for_status()
    return r.json()


def event_object(holder, ticket_number, points=0, seat=None):
    obj = {
        "id": f"{ISSUER_ID}.{ticket_number}",
        "classId": CLASS_ID,
        "state": "ACTIVE",
        "ticketHolderName": holder,
        "ticketNumber": ticket_number,
        "barcode": {
            "type": "QR_CODE",
            "value": ticket_number,
            "alternateText": ticket_number,
        },
        "textModulesData": [
            {"header": "Puntos", "body": str(points), "id": "points"},
            {"header": "Entrada", "body": "Gratis con membresía", "id": "tier"},
        ],
        "linksModuleData": {
            "uris": [{"uri": "https://appfreeticket.com", "description": "Ver mis shows"}]
        },
    }
    if seat:
        obj["seatInfo"] = {"seat": {"defaultValue": {"language": "es-CO", "value": seat}}}
    return obj


def save_link(obj):
    claims = {
        "iss": key["client_email"],
        "aud": "google",
        "typ": "savetowallet",
        "origins": ORIGINS,
        "payload": {"eventTicketObjects": [obj]},
    }
    token = jwt.encode(claims, key["private_key"], algorithm="RS256")
    return SAVE_URL + token


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--holder", required=True)
    p.add_argument("--ticket", required=True, help="ticket number / QR value, e.g. FT-000123")
    p.add_argument("--points", type=int, default=0)
    p.add_argument("--seat")
    a = p.parse_args()

    ensure_class()
    print(save_link(event_object(a.holder, a.ticket, a.points, a.seat)))
