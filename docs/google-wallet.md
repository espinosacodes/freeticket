# Google Wallet — FreeTicket

Passes de entrada para shows de stand-up. Cada ticket lleva un QR cuyo valor es el
`ticketNumber`: ese código es la llave que une "tiquete adquirido" con "asistió",
o sea el denominador del análisis de % de asistencia.

Script: [`wallet_pass.py`](../wallet_pass.py). Config: `.env` (ver `.env.example`).
El equivalente para iOS es [`apple_pass.py`](../apple_pass.py) y lee el mismo `.env`.

## Estado: funcionando end to end

La clase existe en los servidores de Google y el link de guardado se genera y firma.

```
GET /walletobjects/v1/eventTicketClass/3388000000023182970.freeticket_show  -> 200
  reviewStatus  approved
  eventName     Free Comedy Night
  venue         BOOM Stand-Up Bar
  dateTime      2026-08-12T20:00-05:00 -> 22:00-05:00
  logo          https://appfreeticket.com/brand/apple-icon.png
```

### Lo que ya está hecho

| Pieza | Valor / detalle |
|---|---|
| Proyecto GCP | `freeticket-wallet-08011232` (nuevo, sin billing) |
| API | `walletobjects.googleapis.com` habilitada |
| Service account | `freeticket-wallet@freeticket-wallet-08011232.iam.gserviceaccount.com` |
| Llave | `secrets/wallet-sa.json` — gitignored, nunca al repo |
| Issuer ID | `3388000000023182970` |
| Acceso | SA invitada al issuer con rol **Developer** |
| Clase | `3388000000023182970.freeticket_show`, `approved` |
| Logo | `/brand/apple-icon.png` (180×180) |

### Uso

```bash
.venv/bin/python wallet_pass.py --holder "Santiago Espinosa" --ticket FT-000123 --points 40
```

Imprime un link `https://pay.google.com/gp/v/save/<jwt>`. Se abre en Android con la
cuenta del issuer y el pase se instala. Cada corrida re-sincroniza la clase desde
`.env`, así que editar `EVENT_NAME` / fechas y volver a correr actualiza el show.

**Arquitectura:** la clase (el show) se crea vía REST una vez; cada ticket va inline
en un JWT firmado. No hay escritura por ticket — se pueden generar miles de links
sin tocar la API.

## Lo que falta

### Bloqueadores para producción

- [ ] **Salir de demo mode.** Hoy solo las cuentas listadas en el issuer pueden
      guardar el pase. Para público general: perfil de negocio aprobado +
      "Request publishing access" en la consola. Para el hackatón no hace falta.
- [ ] **Logo en mejor resolución.** `apple-icon.png` es 180×180 y Google recomienda
      660×660; se ve suave al escalar. Falta el mark original en alta.
- [ ] **`heroImage`.** `HERO_URI` está vacío — es el banner ancho del pase, el que
      más lo hace ver "de verdad" en la demo.

### Integración pendiente

- [ ] **Endpoint de escaneo en la puerta.** Recibir el `ticketNumber` del QR y
      registrar el check-in. Sin esto no hay dato de asistencia real, que es el
      punto del análisis.
- [ ] **Marcar el pase como usado.** Tras el check-in, `PATCH` del objeto a
      `state: "COMPLETED"` para que no se reutilice.
- [ ] **Un ticket por asistente.** El `ticketNumber` es el ID permanente del objeto:
      reusar `FT-000123` sobrescribe el pase anterior en vez de crear otro.
      La numeración tiene que salir del sistema de reservas, no a mano.
- [ ] **Botón Add-to-Wallet en la web.** `WALLET_ORIGINS` ya lista
      `appfreeticket.com`, `app.freeticket.us` y `localhost:3000`; falta embeber el
      botón. El link crudo funciona desde cualquier lado, el botón embebido no.
- [ ] **Una clase por show.** Hoy `WALLET_CLASS_SUFFIX` es fijo (`freeticket_show`),
      o sea un solo show a la vez. Para varios: un suffix por evento.

### Nice to have

- [ ] Puntos del programa de fidelidad en vivo (hoy `--points` es manual).
- [ ] Notificación push cuando cambia hora o venue (Wallet lo soporta vía update de
      la clase).
- [ ] Geolocalización del venue para que el pase salga en la pantalla de bloqueo al
      llegar — `VENUE_LAT` / `VENUE_LON` están vacíos.

## Notas / trampas encontradas

- El **merchant ID** de Google Pay (`BCR2DN6DTLYMBO3Y`) **no** es el issuer ID. La
  API lo rechaza con `Invalid value at 'issuer_id' (TYPE_INT64)`. El issuer ID es
  el número de ~19 dígitos bajo "Google Wallet API" en la consola.
- `GET /walletobjects/v1/issuer` devuelve `{}` aunque la SA ya tenga acceso — no
  sirve para descubrir el issuer ID, hay que leerlo de la consola.
- En `.env`, `VENUE_ADDRESS` va entre comillas: un `#` sin comillas arranca comentario
  y truncaría la dirección a `Cl 22`.
- Wallet no acepta SVG para el logo; tiene que ser PNG cuadrado.
