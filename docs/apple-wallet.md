# Apple Wallet — FreeTicket

Genera entradas `.pkpass` para shows de stand-up. Es el hermano de
`wallet_pass.py` (Google Wallet); ambos leen la misma configuración de show
desde `.env` (`EVENT_NAME`, `VENUE_NAME`, `EVENT_START`, `VENUE_ADDRESS`), así
que un solo `.env` describe el evento en las dos billeteras.

## El problema central: la firma

Un `.pkpass` debe ir firmado con un **Pass Type ID certificate** emitido por
Apple. iOS verifica que el `UID` del certificado sea igual al
`passTypeIdentifier` y que su `OU` sea igual al `teamIdentifier`. No hay forma
de evadirlo: un certificado self-signed o un "Apple Development" se rechazan sin
error útil, y el Simulador valida igual que un dispositivo real.

La cuenta gratuita de Apple (personal team `F3V9Y6Y96W`) **no puede** crear un
Pass Type ID. Eso requiere el Apple Developer Program (USD 99/año).

Por eso hay dos proveedores:

| Proveedor | Estado | Nota |
|---|---|---|
| `local` | ⛔ bloqueado | Listo en código; falta el certificado de Apple |
| `pass2u` | ✅ funcionando | Pass2U firma con **su** certificado |

Pass2U firma con `pass.tw.com.freedi.eventticket` / `OU=27J49PDZTS`
(MicroMacro Mobile Inc.), emitido por Apple WWDR CA G4. Por eso instala.

## Uso

```bash
python apple_pass.py --make-assets                 # recorta imágenes desde LOGO_URI
python apple_pass.py --provider pass2u \
    --holder "Santiago Espinosa" --ticket FT-000125 --points 40
```

Imprime una URL `pass2u.net/d/{passId}`: se abre en el iPhone y Wallet ofrece
**Add**.

Flags útiles:

| Flag | Para qué |
|---|---|
| `--preview` | Escribe un HTML que renderiza el pase (única forma de verlo sin firma) |
| `--unsigned` | Arma el bundle sin firmar — solo inspección, iOS lo rechaza |
| `--no-fields` | pass2u: omite los campos de texto (ver TODO) |
| `--no-geocode` | No consulta Nominatim; usa `VENUE_LAT`/`VENUE_LON` si existen |
| `--source` | Imagen de marca alterna (por defecto `LOGO_URI`) |

## Qué está hecho

- **Construcción del bundle**: `pass.json`, imágenes, `manifest.json` (SHA-1 por
  archivo) y `signature` (PKCS#7 detached) empaquetados en zip.
- **Firma local** con `cryptography`, verificada extremo a extremo contra un
  certificado de prueba (`openssl smime -verify` → OK, hashes del manifest OK,
  WWDR presente en la cadena).
- **Geocoding**: deriva `locations` desde `VENUE_ADDRESS` vía Nominatim, con
  caché en `.geocode-cache.json`. Sin llaves ni facturación.
- **Assets**: recorta `icon` (29/58/87) y `logo` desde `LOGO_URI` — la misma
  imagen que usa el pase de Google.
- **Preview HTML** con QR real (segno), embebido en base64.
- **Integración Pass2U**: crear pase, subir imágenes (`POST /v2/images`),
  descargar el `.pkpass` firmado.
- **Imágenes en Pass2U** cacheadas en `.pass2u-images.json`.

## TODO

- [ ] **Campos de texto en el Model Designer.** Bloqueante para que el pase se
      parezca al de Google. En la pestaña *Design* del modelo `392142`, poner
      cada campo en tipo **Dynamic** con estas Keys:

      | Área | Key | Label |
      |---|---|---|
      | Header | `date` | FECHA |
      | Primary | `event` | SHOW |
      | Secondary 1 | `venue` | VENUE |
      | Secondary 2 | `time` | HORA |
      | Auxiliary 1 | `holder` | ASISTENTE |
      | Auxiliary 2 | `tier` | ENTRADA |
      | Back 1 | `points` | Puntos |
      | Back 2 | `address` | Dirección |
      | Back 3 | `terms` | Términos |

      Las nueve deben ser Dynamic: una sola que no lo sea hace fallar todo el
      request. Mientras tanto, `--no-fields` emite un pase válido pero con el
      texto de la plantilla (jazz).

- [ ] **Resolver `VENUE_NAME` vs `VENUE_ADDRESS`.** Hoy el pase dice
      "BOOM Stand-Up Bar" pero el geofence cae en Teatro México (Cl 22 #5-85).
      Son dos venues distintos. Definir cuál es el show del 12 de agosto.

- [ ] **`HERO_URI`** vacío ⇒ el pase se arma sin `strip.png`. Poner una imagen
      apaisada (750×288) si se quiere banner.

- [ ] **Webhook de instalación.** Pass2U expone *Pass Installed*
      (`{passId, modelId, installedAt}`) y `GET /passes/{passId}/status` con
      `devices[]` (marca, modelo, `installedTime`) y `redemptions[]`.
      Conectarlo a una edge function de InsForge para medir el embudo:
      **reservado → agregado a wallet → escaneado en puerta**.

- [ ] **Endpoint de redención.** El QR lleva el número de tiquete; falta la
      tabla `redemptions` y la función que valide el serial, rechace doble
      escaneo y estampe la hora de llegada. Es el dato real de asistencia.

- [ ] **Decidir certificado propio.** La llave de prueba de Pass2U vence
      **2026-08-31**; renovar cuesta USD 100/año, casi lo mismo que Apple
      (USD 99). Con cuenta propia de Apple se desbloquea `webServiceURL` y
      `--provider local`, y se deja de depender de un tercero.

## Trampas encontradas (no repetir)

- **`PKCS7Options.Binary` es obligatorio.** Sin él, `cryptography` canonicaliza
  LF→CRLF y firma bytes distintos a los del `manifest.json` empaquetado. El pase
  se rechaza sin error legible. Equivale al `-binary` de
  `openssl smime -binary -sign` de la receta de Apple.

- **`#` sin comillas en `.env` corta el valor.** `VENUE_ADDRESS=Cl 22 #5-85`
  se leía como `"Cl 22"`. Afecta también a `wallet_pass.py`. Va entre comillas.

- **Pass2U rechaza keys que no sean Dynamic**, no cae a los defaults del modelo:
  `Field key 'date' is not defined as 'Dynamic' in the model`.

- **El tipo de barcode es irreversible** una vez emitido el modelo. Está en
  *Dynamic – assigned by CSV file or API (non-replicable)*, que es lo correcto:
  el código `FT-…` llega al QR y no se puede emitir dos veces.

- **Non-replicable quema el número.** Cada creación exitosa consume el código;
  para reintentar hay que incrementar el ticket. `FT-000123` y `FT-000124` ya
  están consumidos.

- **Event Ticket Layout 1 siempre renderiza background y thumbnail.** No se
  pueden apagar. Se suben en `rgb(26,26,26)` sólido (con el logo incrustado en
  el thumbnail) para que desaparezcan contra el fondo, como la tarjeta plana de
  Google.

- **Los requests fallidos no consumen créditos** — un 400 no crea pase.

- **`messageEncoding`**: Pass2U lo reescribe a `UTF-8` (local usa
  `iso-8859-1`). Irrelevante para códigos ASCII.

## Secretos

`.env` y `secrets/` están en `.gitignore`. La API key de Pass2U vive solo en
`.env`. Nunca en `.env.example` ni en un commit.
