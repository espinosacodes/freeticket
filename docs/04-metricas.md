# Las métricas que hoy no existen

Todo lo de aquí sale del log de escaneos de
[`01-scan-telemetry.md`](01-scan-telemetry.md). Ninguna necesita que
FreeTicket cambie su sistema de venta: salen del escaneo en la puerta.

## 1. Hora real de entrada

**Hoy:** `checked_in_at` es la hora en que alguien digitó, no la hora en que
la persona entró. Cuando se marca en lote, decenas de entradas comparten
minuto.

**Con escaneo:** la hora es la del escaneo. La curva de llegada deja de ser
una aproximación y pasa a ser por venue, por día de la semana y por acto.

**Para qué:** dimensionar la puerta y decidir a qué hora abrir. Un show de
residencia que siempre llena a las 20:10 no necesita el mismo personal que
una fecha suelta que llega goteando.

## 2. Tasa de duplicados

**Hoy:** invisible. Si dos personas llegan con la misma captura de pantalla,
la segunda entra o no según el criterio del portero, y no queda registro.

**Con escaneo:** cada `result: duplicado` es un intento medido. Por evento,
por tipo de entrada y por canal de venta.

**Para qué:** un canal con duplicados muy por encima del resto tiene una
fuga. Hoy esa fuga se paga en aforo y nadie la ve. Es dinero, no curiosidad.

## 3. Largo de la fila, en vivo

**Hoy:** no existe.

**Con escaneo:** el tiempo entre escaneos consecutivos en la misma puerta.
Si baja de 4 segundos sostenidos, hay fila.

**Para qué:** una alerta a las 20:15 que dice "puerta principal saturada"
llega a tiempo para abrir la segunda. Un reporte al otro día no.

## 4. No-show por segmento

**Hoy:** se sabe la tasa agregada por tipo de entrada — pagada ~94%,
cortesía ~42%.

**Con escaneo + el cruce de la Parte A:** la tasa por **persona**, cruzada
con su perfil de Boom.

**Para qué:** esta es la que cambia plata. Una cortesía que no se usa es un
asiento perdido dos veces — no entró nadie y no se pudo vender. Saber a
**quién** darle la cortesía, en vez de cuántas dar, es la diferencia entre
un 42% y algo mucho mejor. El cruce con Boom que hicimos en la Parte A es
justo lo que dice a quién.

## 5. Pase instalado y nunca escaneado

**Hoy:** indistinguible de "no compró".

**Con wallet:** el pase instalado es intención declarada. Si se instaló y no
se escaneó, esa persona pensaba ir y no fue.

**Para qué:** es la señal más cara de conseguir en cualquier negocio de
eventos, y aquí sale gratis del mismo flujo. Alimenta directamente la
proyección: hoy el modelo trata igual a quien compró y olvidó, y a quien
compró y planeó ir.

> Ojo: en Apple esto **solo** existe con el camino de certificado propio
> ($99/año) y el web service en pie. Ver
> [`02-wallet-passes.md`](02-wallet-passes.md#apple-el-muro).

## 6. El círculo cerrado

Las cinco anteriores son reportes. Esta es la que cambia el producto.

```
escaneo real -> checked_in observado -> reentreno -> proyección
     ^                                                    |
     └──────────── se compara contra ─────────────────────┘
```

Cada noche produce 200–500 etiquetas nuevas y limpias. `pipeline/forecast.py`
ya está escrito para consumir exactamente esos campos, así que el
reentrenamiento no pide código nuevo: pide que el dato entre.

Hoy el modelo se entrena una vez sobre un julio digitado a mano. En tres
meses de escaneo tendría ~90 shows etiquetados a nivel entrada, con hora
real. **Ese es el activo**, no el modelo.
