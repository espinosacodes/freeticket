# ¿Cuánta gente entra realmente?

Solución al hackathon FreeTicket — Santiago Espinosa, 1 de agosto de 2026.
El enunciado original está en [`RETO.md`](RETO.md).

**Tablero en vivo → https://espinosacodes.github.io/freeticket/**

Se republica solo en cada push que toque `web/`, `out/` o `pipeline/`.

## Correr todo

```bash
npx -y github:LucasLeguizamo/hackathon-freeticket setup TU-NOMBRE
bash scripts/pull.sh          # trae los 8 recursos a raw/
python3 pipeline/run_all.py   # cruce + proyección + tablero
```

Sin dependencias: solo la librería estándar de Python 3. No hay nada que
instalar y nada que se pueda romper en otra máquina.

Para ver el tablero:

```bash
cd web && python3 -m http.server 8777    # http://localhost:8777
```

## Las entregas

| Archivo | Qué es |
|---|---|
| [`out/matches.csv`](out/matches.csv) | `sale_id, boom_user_id, confidence` |
| [`out/forecast.csv`](out/forecast.csv) | `event_id, expected_attendance, p10, p90` — solo agosto |
| [`NOTAS.md`](NOTAS.md) | qué asumí, qué señal pesó más, qué haría con 4 horas más |
| [`DEMO.md`](DEMO.md) | el guion de la demo y las respuestas a las preguntas difíciles |
| `out/matches_auditoria.csv` | lo mismo que `matches.csv` **más la evidencia** de cada match |
| `out/arrival_curve.csv` | la curva de llegada, medida sobre 4.969 check-ins de julio |

## Resultados

**Parte A — el cruce.** 3.995 de 6.383 ventas cruzadas (62,6%). 3.812 con
confianza ≥ 0,90. **56 se descartaron por ambiguas** aunque pasaban el
umbral: precisión sobre cobertura, tal como pide el enunciado.

**Parte B — la proyección.** 3.519 personas esperadas sobre las 5.209
entradas ya adquiridas para agosto (68%). Backtest sobre 7 eventos de julio
que el modelo no vio: **error medio 4,7 personas**, con el 71% dentro del
rango p10–p90 (el objetivo es 80%; con 7 eventos eso es 5 de 7 y no se
distingue del objetivo).

## Los dos extras

Ambos están construidos, no descritos.

**El link efímero para la puerta** — `web/puerta.html#<token>`. Se manda por
WhatsApp, se abre en el teléfono sin cuenta ni app, muestra aforo esperado,
rango, pico de llegada y personal sugerido, y **caduca solo** 3 horas después
del show. El token va firmado con HMAC, sin base de datos que limpiar.

**La curva de llegada** — a qué hora entra la gente, no solo cuánta. El pico
está 10 minutos **antes** de la hora de inicio. Alimenta el personal
sugerido del link de puerta.

## Desplegado y funcionando

| | |
|---|---|
| Tablero, puerta y escáner | https://espinosacodes.github.io/freeticket/ |
| Ingest de escaneos | `https://1q5q7pqmx9.execute-api.us-east-1.amazonaws.com` |

El ingest es **real**: Lambda + API Gateway + DynamoDB, probado de punta a
punta. Se puede comprobar sin credenciales:

```bash
curl https://1q5q7pqmx9.execute-api.us-east-1.amazonaws.com/salud
curl 'https://1q5q7pqmx9.execute-api.us-east-1.amazonaws.com/aforo?event_id=ft_evt_0040'
```

Dos guardarraíles de la organización de AWS nos obligaron a desviarnos —
las Lambda Function URL públicas y `sts:AssumeRoleWithWebIdentity` están
bloqueados en esta cuenta. Cómo se diagnosticó y qué se hizo en cambio está
en [`docs/05-despliegue.md`](docs/05-despliegue.md).

## El escáner de puerta

[`web/escaner.html`](web/escaner.html) — **funciona**, no es una maqueta.
Lee el QR con la cámara (`BarcodeDetector`), valida contra el ingest, y
mueve el contador de aforo contra la proyección de ese show.

```bash
QR_SECRET=demo python3 scripts/mock_ingest.py 8788   # la Lambda, en memoria
QR_SECRET=demo python3 scripts/qr_demo.py --n 5 --png   # entradas firmadas de prueba
cd web && python3 -m http.server 8777
# abrir http://localhost:8777/escaner.html?api=http://localhost:8788
```

Probado de punta a punta contra el ingest: entrada válida → `ok`, la misma
otra vez → `duplicado`, firma alterada → `firma_invalida`, y **al cortar la
red el escaneo queda en cola y se sube solo cuando vuelve** — el aforo pasó
de 3 a 4 sin que la puerta se detuviera.

Safari no trae `BarcodeDetector`; ahí el campo «a mano» hace el mismo
recorrido. En Chrome (escritorio y Android) la cámara funciona.

## Lo que va más allá del reto

El reto pide proyectar mejor. Debajo hay un problema más grande:

> `checked_in` es un campo que alguien llena, no un hecho que el sistema observa.

Si se marca en lote al final de la noche, `checked_in_at` miente sobre la
hora. Si no se marca a los que entraron tarde, la tasa queda baja para
siempre y el modelo aprende ese ruido.

`docs/` especifica cómo cerrar ese hueco con la entrada en la wallet del
teléfono, de forma que **el mismo escaneo que deja entrar a la persona sea
el dato**:

| | |
|---|---|
| [`docs/00-vision.md`](docs/00-vision.md) | la solución completa en una página |
| [`docs/01-scan-telemetry.md`](docs/01-scan-telemetry.md) | el QR firmado, el log de escaneos, y cómo funciona **sin señal en la puerta** |
| [`docs/02-wallet-passes.md`](docs/02-wallet-passes.md) | Google Wallet (funcionando) y Apple (bloqueado, y por qué) |
| [`docs/03-puerta.md`](docs/03-puerta.md) | la spec del link efímero |
| [`docs/04-metricas.md`](docs/04-metricas.md) | las 6 métricas de operación que hoy no existen |
| [`docs/05-despliegue.md`](docs/05-despliegue.md) | qué está corriendo, y los dos bloqueos de AWS que sorteamos |

`wallet_pass.py` genera pases de Google Wallet reales: la clase se crea una
vez por show y cada entrada se firma como JWT, así que emitir 500 pases
cuesta 500 firmas locales y **cero** llamadas al API de Google.

## Despliegue

| Qué | Dónde | Cuándo |
|---|---|---|
| Tablero | GitHub Pages | push que toque `web/`, `out/` o `pipeline/` |
| Ingest de escaneos | AWS Lambda + DynamoDB | push que toque `lambda/**` |

El despliegue a AWS se autentica por **OIDC**: no hay `AWS_ACCESS_KEY_ID`
guardado en el repo ni en los secrets, así que no hay llave que se pueda
filtrar. El rol solo lo puede asumir este repositorio, desde `main`, y solo
alcanza a este stack.

Preparación, una sola vez:

```bash
bash scripts/aws-bootstrap.sh      # crea el proveedor OIDC y el rol
gh secret set AWS_DEPLOY_ROLE_ARN --body 'arn:aws:iam::<cuenta>:role/freeticket-github-deploy'
gh secret set QR_SECRET --body "$(openssl rand -hex 32)"
gh variable set AWS_REGION --body 'us-east-1'
```

La tabla de escaneos es **append-only por permisos**, no por convención: el
rol de la Lambda no tiene `DeleteItem` ni `UpdateItem`, así que no puede
reescribir la historia ni con un bug de por medio.

## Estructura

```
pipeline/    match.py · forecast.py · normalize.py · build_web.py · run_all.py
web/         tablero + link de puerta (estático, sin build)
docs/        las specs de la solución completa
out/         las entregas
raw/         la data descargada (no va al repo)
wallet_pass.py   pases de Google Wallet
```
