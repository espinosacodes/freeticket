# Spec — telemetría de escaneo en la puerta

El objetivo no es "tener un escáner". Es que **el acto de dejar entrar a
alguien produzca el dato**, sin un paso manual que se pueda omitir.

## El QR

El valor del QR es el `ticket_id` que ya existe (`ft_tkt_0000001`), firmado:

```
FT1.<ticket_id>.<event_id>.<exp>.<hmac10>
```

- `hmac10` — primeros 10 caracteres de `HMAC-SHA256(secreto_del_evento, ticket_id|event_id|exp)`
- `exp` — epoch de `starts_at + 4h`

**Por qué firmado y no el `ticket_id` pelado:** el escáner tiene que poder
validar **sin red**. Con la firma, un teléfono en un sótano sin señal
distingue un pase legítimo de uno inventado, con solo el secreto del evento
cargado antes de abrir puertas. Un `ticket_id` pelado obligaría a consultar
el servidor en cada persona — que es exactamente el momento en que no hay
señal.

El secreto es **por evento**, no global: el teléfono del portero de un show
se lleva únicamente lo que necesita esa noche. Si se pierde, se pierde una
noche, no la tiquetera.

## El evento de escaneo

Una fila por escaneo, nunca se actualiza ni se borra. La verdad es el log,
no un estado.

```json
{
  "scan_id":    "scn_01J8...",          // ULID generado en el dispositivo
  "ticket_id":  "ft_tkt_0000001",
  "event_id":   "ft_evt_0031",
  "scanned_at": "2026-08-12T20:07:31-05:00",  // reloj del dispositivo
  "received_at":"2026-08-12T20:07:33-05:00",  // reloj del servidor
  "device_id":  "puerta-1",
  "gate":       "principal",
  "result":     "ok",
  "offline":    false
}
```

`result` ∈ `ok | duplicado | evento_equivocado | firma_invalida | expirado`

**Los rechazos se guardan igual que los aceptados.** Un duplicado no es un
error del sistema: es la información de que dos personas llegaron con el
mismo pase. Botarlo es botar la única evidencia de que el pase se compartió.

## Idempotencia

`scan_id` es la llave primaria y lo genera el dispositivo. Reenviar la misma
fila cien veces produce una fila. Esto es lo que hace seguro el reintento
cuando la red va y viene.

El **primer** escaneo `ok` de un `ticket_id` es el que cuenta como asistencia.
Los siguientes se guardan como `duplicado` y no mueven la asistencia.

## Sin señal en la puerta

El caso real: un bar en el centro de Bogotá, 200 personas en 20 minutos,
LTE saturado. Si el escáner necesita red por persona, la fila se detiene y
el portero vuelve a la lista de papel — y perdimos el dato.

```
abrir puertas
  └─ descarga: secreto del evento + lista de ticket_id válidos  (una vez, ~40KB)

por cada persona
  └─ valida firma en local        (sin red)
  └─ marca visto en IndexedDB     (sin red)
  └─ luz verde / roja             (< 100 ms)
  └─ encola el evento

cuando haya red
  └─ sube la cola por lotes, idempotente por scan_id
```

El portero nunca espera a la red. La consecuencia aceptada: dos puertas
offline en simultáneo pueden dejar pasar el mismo pase dos veces. Se detecta
al sincronizar y queda como `duplicado`. Es el intercambio correcto —
**es peor detener la fila que dejar entrar a un colado y saberlo después.**

## Reloj

`scanned_at` viene del dispositivo y los teléfonos mienten. Al sincronizar
se guarda también `received_at` y el desfase estimado. Para la curva de
llegada se usa `scanned_at` corregido por el desfase; si el desfase supera
5 minutos, ese lote se marca `reloj_dudoso` y no entra a la curva.

Sale de la curva. **No** sale de la asistencia: que el reloj esté mal no
significa que la persona no entró.

## Lo que esto le devuelve al modelo

`pipeline/forecast.py` hoy aprende de `checked_in` y `checked_in_at` de julio.
Con escaneos reales, esos dos campos dejan de ser digitados y pasan a ser
observados. Sin cambiar una línea del modelo, mejora:

- la **tasa por tipo de entrada** deja de arrastrar el sesgo de quien marca
- la **curva de llegada** pasa de aproximada a real por venue y día
- aparece una señal nueva: **pase instalado y nunca escaneado** — intención
  sin asistencia, que hoy es indistinguible de "no compró"

## Qué falta para producción

- Rotación del secreto por evento y su distribución al dispositivo
- Un `gate` por puerta física para medir cada una por separado
- Retención: el log crudo pesa ~200 bytes por escaneo; 60k escaneos al año
  es despreciable, se guarda entero
- Pantalla de reconciliación: escaneos offline que llegaron tarde vs. la
  lista manual de esa noche
