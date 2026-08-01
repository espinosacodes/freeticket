"""Narración en español con la API de OpenAI (gpt-4o-mini-tts).

    export OPENAI_API_KEY=sk-...
    python3 scripts/voz.py video/guion.md --out video/voz.mp3

Lee los textos de la tabla del guion, genera un mp3 por tramo y los pega en
uno solo. Sin dependencias: urllib de la librería estándar.

La llave sale de la variable de entorno. Nunca se escribe a disco ni se
imprime.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.openai.com/v1/audio/speech"

# gpt-4o-mini-tts acepta instrucciones de interpretación, no solo texto.
# Esto es lo que separa una voz de robot de una que convence.
INSTRUCCIONES = (
    "Hablá en español latinoamericano neutro, con acento colombiano suave. "
    "Tono de alguien que conoce el negocio y está mostrando algo que funciona: "
    "seguro, directo, sin entusiasmo de comercial ni voz de tutorial. "
    "Ritmo pausado, con una pausa breve después de cada pregunta. "
    "Bajá el tono al final de cada frase, como quien afirma, no como quien vende."
)

# alloy/echo/fable/onyx/nova/shimmer · onyx = grave y con autoridad
VOZ_POR_DEFECTO = "onyx"


def tramos_del_guion(path):
    """Saca la última columna de cada fila de la tabla del guion."""
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or "Narración" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 4:
            continue
        texto = cols[-1]
        # limpia el markdown que no se lee en voz alta
        texto = re.sub(r"[*`]", "", texto).strip()
        if texto and not texto.startswith("#"):
            out.append((cols[0], texto))
    return out


def hablar(texto, voz, modelo="gpt-4o-mini-tts"):
    body = json.dumps({
        "model": modelo,
        "voice": voz,
        "input": texto,
        "instructions": INSTRUCCIONES,
        "response_format": "mp3",
    }).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("guion", nargs="?", default="video/guion.md")
    p.add_argument("--out", default="video/voz.mp3")
    p.add_argument("--voz", default=VOZ_POR_DEFECTO)
    p.add_argument("--solo", type=int, help="regenerar un solo tramo, por número")
    a = p.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Falta OPENAI_API_KEY.\n  export OPENAI_API_KEY=sk-...")

    tramos = tramos_del_guion(a.guion)
    if not tramos:
        sys.exit(f"No encontré narración en {a.guion}")

    carpeta = os.path.dirname(a.out) or "."
    os.makedirs(carpeta, exist_ok=True)
    partes = []

    for num, texto in tramos:
        destino = os.path.join(carpeta, f"voz-{num}.mp3")
        partes.append(destino)
        if a.solo and str(a.solo) != num:
            continue
        print(f"  {num}. {texto[:64]}{'…' if len(texto) > 64 else ''}")
        try:
            audio = hablar(texto, a.voz)
        except urllib.error.HTTPError as e:
            sys.exit(f"OpenAI {e.code}: {e.read().decode()[:200]}")
        open(destino, "wb").write(audio)

    faltan = [p for p in partes if not os.path.exists(p)]
    if faltan:
        print(f"\n(faltan {len(faltan)} tramos; corré sin --solo para generarlos)")
        return

    lista = os.path.join(carpeta, "voz-lista.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for x in partes:
            f.write(f"file '{os.path.basename(x)}'\n")
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", os.path.basename(lista), "-c", "copy", os.path.basename(a.out)],
        cwd=carpeta,
    )
    if r.returncode == 0:
        print(f"\nListo: {a.out}  ({len(partes)} tramos)")
        print("Duración por tramo, para cuadrar los cortes:")
        for x in partes:
            d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", x],
                               capture_output=True, text=True).stdout.strip()
            print(f"  {os.path.basename(x):<12} {float(d):.1f}s")


if __name__ == "__main__":
    main()
