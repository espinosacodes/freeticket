"""Un comando, de punta a punta.

    python3 pipeline/run_all.py

Lee raw/*.csv, escribe out/matches.csv y out/forecast.csv (más los
artefactos anchos que consume el dashboard). Sin dependencias externas:
solo la librería estándar, para que corra en cualquier máquina sin
instalar nada.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_web as bw
import forecast as fc
import match as mt

RAW, OUT = "raw", "out"


def main():
    if not os.path.isdir(RAW) or not os.listdir(RAW):
        sys.exit(
            "Falta la data en raw/. Traela primero:\n"
            "  npx -y github:LucasLeguizamo/hackathon-freeticket setup TU-NOMBRE\n"
            "  bash scripts/pull.sh"
        )
    os.makedirs(OUT, exist_ok=True)

    print("\nParte A — cruce comprador ↔ Boom")
    matches = mt.run(RAW, OUT)

    print("\nParte B — proyección de agosto")
    fc.run(matches, RAW, OUT)

    print("\nTablero")
    bw.run(RAW, OUT, "web")

    print(f"\nListo. Salidas en {OUT}/:")
    for f in sorted(os.listdir(OUT)):
        print(f"  {f}")


if __name__ == "__main__":
    main()
