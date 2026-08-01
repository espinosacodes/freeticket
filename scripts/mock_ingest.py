"""El mismo contrato que la Lambda, en memoria, para probar sin AWS.

    QR_SECRET=demo python3 scripts/mock_ingest.py 8788

Implementa las mismas dos rutas de lambda/handler.py con las mismas reglas:
idempotencia por scan_id, primer escaneo gana, duplicados guardados.
Sirve para probar web/escaner.html antes de que el stack esté desplegado.
"""

import hashlib
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

SECRET = os.environ.get("QR_SECRET", "demo").encode()

SCANS = {}          # scan_id -> fila
CLAIMED = {}        # (event_id, ticket_id) -> epoch


def verify(qr):
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


def handle_batch(scans):
    out = []
    for s in scans:
        sid = s.get("scan_id")
        if not sid:
            out.append({"scan_id": None, "result": "sin_scan_id"})
            continue
        if sid in SCANS:
            out.append({"scan_id": sid, "result": "ya_recibido"})
            continue

        ticket_id, event_id, bad = verify(s.get("qr"))
        if bad == "firma_invalida":
            result, event_id = "firma_invalida", s.get("event_id", "desconocido")
        elif s.get("event_id") and s["event_id"] != event_id:
            result = "evento_equivocado"
        elif bad == "expirado":
            result = "expirado"
        else:
            key = (event_id, ticket_id)
            if key in CLAIMED:
                result = "duplicado"
            else:
                CLAIMED[key] = int(time.time())
                result = "ok"

        SCANS[sid] = {**s, "result": result, "received_at": int(time.time())}
        out.append({"scan_id": sid, "result": result, "ticket_id": ticket_id})
    return {"recibidos": len(out), "resultados": out}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "content-type")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.rstrip("/").endswith("/aforo"):
            eid = (parse_qs(u.query).get("event_id") or [""])[0]
            if not eid:
                return self._send(400, {"error": "falta event_id"})
            n = sum(1 for (e, _t) in CLAIMED if e == eid)
            return self._send(200, {"event_id": eid, "adentro": n})
        if u.path.rstrip("/") in ("", "/salud"):
            return self._send(200, {"ok": True, "mock": True,
                                    "rutas": ["POST /scan", "GET /aforo?event_id="]})
        self._send(404, {"error": "ruta desconocida"})

    def do_POST(self):
        if not urlparse(self.path).path.rstrip("/").endswith("/scan"):
            return self._send(404, {"error": "ruta desconocida"})
        n = int(self.headers.get("content-length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "body no es JSON"})
        scans = body.get("scans")
        if not isinstance(scans, list) or not scans:
            return self._send(400, {"error": 'se espera {"scans": [...]}'})
        self._send(200, handle_batch(scans))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
    print(f"mock ingest en http://localhost:{port}  (QR_SECRET={SECRET.decode()})")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
