"""Ingest de escaneos de puerta — implementa docs/01-scan-telemetry.md.

Dos rutas, sobre una Lambda Function URL:

    POST /scan     un lote de escaneos, idempotente por scan_id
    GET  /aforo    cuánta gente lleva adentro un evento

Sin dependencias fuera del runtime de Lambda (boto3 viene incluido).

La verdad es el log: un escaneo nunca se actualiza ni se borra. Un
duplicado se guarda como duplicado — es la evidencia de que el pase se
compartió, y botarla es botar la única señal de fuga que existe.
"""

import hashlib
import hmac
import json
import os
import time

import boto3
from botocore.exceptions import ClientError

TABLE = os.environ["SCANS_TABLE"]
SECRET = os.environ.get("QR_SECRET", "").encode()

ddb = boto3.client("dynamodb")

CORS = {
    "Access-Control-Allow-Origin": os.environ.get("ALLOW_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def reply(code, body):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json", **CORS},
        "body": json.dumps(body, ensure_ascii=False),
    }


def verify(qr):
    """FT1.<ticket_id>.<event_id>.<exp>.<hmac10> -> (ticket_id, event_id, motivo).

    Se valida con `compare_digest`, no con `==`: la comparación normal corta
    en el primer byte distinto y filtra el secreto por tiempo de respuesta.
    """
    parts = (qr or "").split(".")
    if len(parts) != 5 or parts[0] != "FT1":
        return None, None, "firma_invalida"
    _, ticket_id, event_id, exp, sig = parts

    expected = hmac.new(
        SECRET, f"{ticket_id}|{event_id}|{exp}".encode(), hashlib.sha256
    ).hexdigest()[:10]
    if not hmac.compare_digest(sig, expected):
        return None, None, "firma_invalida"
    if exp.isdigit() and int(exp) < int(time.time()):
        return ticket_id, event_id, "expirado"
    return ticket_id, event_id, None


def record(scan, event_id, ticket_id, result):
    """Guarda el escaneo. `scan_id` lo genera el dispositivo, así que
    reenviar el mismo lote cien veces produce una fila: eso es lo que hace
    seguro el reintento cuando la red va y viene."""
    now = int(time.time())
    try:
        ddb.put_item(
            TableName=TABLE,
            Item={
                "pk": {"S": f"EVT#{event_id}"},
                "sk": {"S": f"SCAN#{scan['scan_id']}"},
                "ticket_id": {"S": ticket_id or ""},
                "scanned_at": {"S": str(scan.get("scanned_at", ""))},
                "received_at": {"N": str(now)},
                "device_id": {"S": str(scan.get("device_id", ""))},
                "gate": {"S": str(scan.get("gate", ""))},
                "result": {"S": result},
                "offline": {"BOOL": bool(scan.get("offline", False))},
            },
            ConditionExpression="attribute_not_exists(sk)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return "ya_recibido"
    return result


def claim(event_id, ticket_id):
    """El primer escaneo válido de una entrada es el que cuenta como
    asistencia. Los siguientes son duplicados y no mueven el aforo."""
    try:
        ddb.put_item(
            TableName=TABLE,
            Item={
                "pk": {"S": f"EVT#{event_id}"},
                "sk": {"S": f"TKT#{ticket_id}"},
                "at": {"N": str(int(time.time()))},
            },
            ConditionExpression="attribute_not_exists(sk)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def post_scan(body):
    scans = body.get("scans") or []
    if not isinstance(scans, list) or not scans:
        return reply(400, {"error": "se espera {\"scans\": [...]}"})
    if len(scans) > 500:
        return reply(413, {"error": "máximo 500 escaneos por lote"})

    out = []
    for s in scans:
        if not s.get("scan_id"):
            out.append({"scan_id": None, "result": "sin_scan_id"})
            continue

        ticket_id, event_id, bad = verify(s.get("qr"))
        if bad == "firma_invalida":
            # No se conoce el evento: se guarda bajo el que declaró el
            # dispositivo, para no perder el intento.
            r = record(s, s.get("event_id", "desconocido"), "", "firma_invalida")
            out.append({"scan_id": s["scan_id"], "result": r})
            continue

        declared = s.get("event_id")
        if declared and declared != event_id:
            r = record(s, event_id, ticket_id, "evento_equivocado")
            out.append({"scan_id": s["scan_id"], "result": r})
            continue

        if bad == "expirado":
            r = record(s, event_id, ticket_id, "expirado")
            out.append({"scan_id": s["scan_id"], "result": r})
            continue

        result = "ok" if claim(event_id, ticket_id) else "duplicado"
        r = record(s, event_id, ticket_id, result)
        out.append({"scan_id": s["scan_id"], "result": r, "ticket_id": ticket_id})

    return reply(200, {"recibidos": len(out), "resultados": out})


def get_aforo(qs):
    event_id = (qs or {}).get("event_id")
    if not event_id:
        return reply(400, {"error": "falta event_id"})

    total, key = 0, None
    while True:
        kw = {
            "TableName": TABLE,
            "KeyConditionExpression": "pk = :p AND begins_with(sk, :s)",
            "ExpressionAttributeValues": {
                ":p": {"S": f"EVT#{event_id}"},
                ":s": {"S": "TKT#"},
            },
            "Select": "COUNT",
        }
        if key:
            kw["ExclusiveStartKey"] = key
        r = ddb.query(**kw)
        total += r["Count"]
        key = r.get("LastEvaluatedKey")
        if not key:
            break

    return reply(200, {"event_id": event_id, "adentro": total})


def lambda_handler(event, context):
    ctx = event.get("requestContext", {}).get("http", {})
    method, path = ctx.get("method", "GET"), ctx.get("path", "/")

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    try:
        if method == "POST" and path.rstrip("/").endswith("/scan"):
            return post_scan(json.loads(event.get("body") or "{}"))
        if method == "GET" and path.rstrip("/").endswith("/aforo"):
            return get_aforo(event.get("queryStringParameters"))
        if path.rstrip("/") in ("", "/salud"):
            return reply(200, {"ok": True, "rutas": ["POST /scan", "GET /aforo?event_id="]})
    except json.JSONDecodeError:
        return reply(400, {"error": "body no es JSON"})

    return reply(404, {"error": "ruta desconocida"})
