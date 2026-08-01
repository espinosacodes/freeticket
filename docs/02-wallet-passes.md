# Spec — el pase en la wallet

El pase es el vehículo del QR de [`01-scan-telemetry.md`](01-scan-telemetry.md).
Sin él, el QR vive en un correo que nadie encuentra a las 8pm en la fila.

## Por qué wallet y no un PDF

| | PDF por correo | Pase en wallet |
|---|---|---|
| Encontrarlo en la fila | buscar el correo | está en la wallet |
| Sin señal en el venue | hay que tenerlo bajado | siempre offline |
| Cambió la hora del show | correo nuevo que nadie abre | el pase se actualiza solo |
| Puntos de Boom | no se ven | en el pase |
| El negocio se entera de algo | no | instalación, actualización, escaneo |

La última fila es la que importa para este reto.

## Google — funcionando

`wallet_pass.py`, ya en el repo.

El diseño correcto y no obvio: **la clase se crea una vez por show, y cada
entrada se firma como JWT de `save-link`**. No hay una escritura al API de
Google por entrada. Emitir 500 pases para un show cuesta 500 firmas locales
y **cero** llamadas de red — no hay límite de tasa que pueda tumbar una
salida a la venta.

```bash
python3 wallet_pass.py --holder "Ana Ruiz" --ticket FT-000123 --points 40
# -> https://pay.google.com/gp/v/save/eyJhbGciOi...
```

Ese link se manda por WhatsApp. La persona lo toca y el pase queda en su
teléfono.

**Bloqueado por:** `GOOGLE_WALLET_ISSUER_ID` vacío. Se saca en
pay.google.com/business/console → Google Wallet API. Es un número de ~19
dígitos que empieza en `33880000...`. **No** es el merchant ID de Google Pay
(`BCR2DN...`) — el API lo rechaza con `Invalid value at 'issuer_id'
(TYPE_INT64)`. Después hay que invitar a la service account como *Developer*.

Con `reviewStatus: UNDER_REVIEW` los pases funcionan para las cuentas de
prueba del emisor sin esperar aprobación de Google. Sirve para demo; para
producción hay que pasar a `APPROVED`.

## Apple — el muro

Apple no deja firmar un pase sin un certificado Pass Type ID, y ese
certificado exige el Apple Developer Program a $99/año. Un Apple ID
personal (el team `F3V9Y6Y96W`) **no** puede crearlo, y un certificado
"Apple Development" no sirve de sustituto: iOS verifica que el UID del
certificado sea igual a `PASS_TYPE_IDENTIFIER` y que el OU sea igual a
`TEAM_IDENTIFIER`.

Dos caminos, ninguno gratis-y-rápido a la vez:

1. **`provider=local`** — pagar los $99, firmar nosotros. Control total,
   incluye el web service para empujar actualizaciones al pase.
2. **`provider=pass2u`** — Pass2U firma con su certificado. Sin cuenta
   Apple, llave de prueba a 30 días. Cuesta: los pases dicen Pass2U, y en
   el Model Designer **hay que tipar cada campo como `Dynamic`** con su Key,
   y el código de barras como `Dynamic - assigned by CSV file or API`. Los
   campos `Fixed`, `Points` y `Credits` no se pueden setear por API.

`apple_pass.py` **todavía no existe**. `.env.example` y `requirements.txt`
(la dependencia `segno`) ya lo anticipan, pero el archivo no está escrito.

### Corrección importante sobre la geolocalización

`.env.example` dice hoy que `VENUE_LAT/LON` hace que Apple mande un "ping de
llegada" y que ese ping es la señal de asistencia. **Eso no es así.**

Apple usa `locations` para mostrar el pase en la pantalla de bloqueo cuando
el teléfono está cerca del venue. Ese comportamiento es **local al
dispositivo**: el emisor nunca se entera. No hay webhook, no hay ping, no
hay dato que llegue al servidor.

Lo que Apple **sí** reporta al emisor, y solo con `provider=local` más un
`PASS_WEB_SERVICE_URL` en pie, es el **registro del pase**: qué dispositivo
lo instaló y cuándo, y cuándo lo eliminó.

Entonces:

- Geolocalización = **UX**. El pase aparece solo cuando la persona llega a la
  puerta y no tiene que buscarlo. Vale mucho, y es honesto venderlo así.
- Instalación / eliminación del pase = **telemetría**. Es real, pero es otra
  cosa, y necesita el camino de los $99.
- Asistencia = **el escaneo**, y solo el escaneo.

No mezclar las tres es la diferencia entre una demo que aguanta preguntas y
una que no.

## Actualizar un pase en vivo

Con el web service en pie (Apple) o `walletobjects.patch` (Google), el pase
puede cambiar después de emitido:

- pasar a `state: USED` al escanearse — se ve gris en la wallet, mata el
  reuso por captura de pantalla
- cambiar la hora si el show se mueve
- subir los puntos de Boom después del show

Para el hackathon solo aplica lo de Google, que ya está resuelto en el
código.
