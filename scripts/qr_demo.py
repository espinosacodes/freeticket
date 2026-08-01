"""Genera payloads de QR firmados, para probar el escáner.

    QR_SECRET=demo python3 scripts/qr_demo.py ft_evt_0031 --n 3

Imprime el payload que va dentro del QR y, si `segno` está instalado,
escribe también el PNG para apuntarle la cámara.
"""

import argparse
import hashlib
import hmac
import json
import os
import time

SECRET = os.environ.get("QR_SECRET", "demo").encode()


def firmar(ticket_id, event_id, exp):
    sig = hmac.new(SECRET, f"{ticket_id}|{event_id}|{exp}".encode(),
                   hashlib.sha256).hexdigest()[:10]
    return f"FT1.{ticket_id}.{event_id}.{exp}.{sig}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("event_id", nargs="?", help="por defecto, el primer evento de web/data.json")
    p.add_argument("--n", type=int, default=3, help="cuántas entradas generar")
    p.add_argument("--horas", type=float, default=6, help="vigencia del QR")
    p.add_argument("--png", action="store_true", help="escribir también los PNG")
    p.add_argument("--vencido", action="store_true", help="generar uno ya expirado, para probar el rechazo")
    a = p.parse_args()

    event_id = a.event_id
    if not event_id:
        with open("web/data.json", encoding="utf-8") as f:
            event_id = json.load(f)["events"][0]["event_id"]

    exp = int(time.time() + (-3600 if a.vencido else a.horas * 3600))

    payloads = []
    for i in range(1, a.n + 1):
        tid = f"ft_tkt_{i:07d}"
        payloads.append(firmar(tid, event_id, exp))

    for q in payloads:
        print(q)

    if a.png:
        try:
            import segno
        except ImportError:
            print("\n(segno no está instalado: pip install segno)")
            return
        os.makedirs("out/qr", exist_ok=True)
        for q in payloads:
            tid = q.split(".")[1]
            segno.make(q).save(f"out/qr/{tid}.png", scale=8, border=2)
        print(f"\n{len(payloads)} PNG en out/qr/")


if __name__ == "__main__":
    main()
