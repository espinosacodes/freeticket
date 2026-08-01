# La solución, en una página

## El problema que el reto no dice en voz alta

El reto pide proyectar cuánta gente entra en agosto. Se puede resolver con
un modelo sobre julio — y eso es lo que hicimos en `pipeline/`. Pero hay un
problema debajo:

> **`checked_in` es un campo que alguien llena. No un hecho que el sistema observa.**

En julio hay 4.969 check-ins registrados sobre 11.931 entradas. Ese dato es
la única verdad que tiene el negocio, y sale de una persona en la puerta con
una lista. Si esa persona marca en lote al final de la noche, `checked_in_at`
miente sobre la hora. Si no marca a los que entraron tarde, la tasa de
asistencia queda baja para siempre. El modelo aprende de ese ruido y nadie
se entera.

**Proyectar mejor sobre un dato malo tiene techo. Arreglar el dato no.**

## Las tres piezas

| | Qué hace | Estado |
|---|---|---|
| **1. La proyección** | Cruza comprador↔Boom y proyecta agosto con rango honesto | ✅ `pipeline/` |
| **2. La puerta** | Link efímero por WhatsApp: aforo, rango, personal sugerido, curva de llegada | ✅ `web/` |
| **3. El pase** | Entrada en Google/Apple Wallet, con QR que al escanearse **genera** el check-in | 📐 spec + demo |

La pieza 3 es la que cierra el círculo. Hoy el flujo es:

```
venta -> (hueco) -> alguien marca una lista -> checked_in
```

Con el pase en la wallet:

```
venta -> pase en el teléfono -> scan en la puerta -> evento firmado con hora real
                                                      |
                                                      v
                                          el modelo se reentrena solo
```

El mismo escaneo que deja entrar a la persona **es** el dato. No hay paso
manual que se pueda saltar, y la hora es la del escaneo, no la de cuando
alguien se acordó de marcar.

## Por qué esto se puede usar mañana

Nada de esto pide que FreeTicket cambie su sistema de venta.

- El pase se genera **después** de la venta, desde el `ticket_id` que ya existe
- El escáner es un navegador en un teléfono cualquiera, sin app que instalar
- Si no hay señal en el venue, la puerta sigue funcionando ([offline first](01-scan-telemetry.md#sin-señal-en-la-puerta))
- Si el pase falla, la lista de siempre sigue ahí — el pase **suma**, no reemplaza

## Lo que esto le da al negocio que hoy no tiene

Ver [`04-metricas.md`](04-metricas.md) para el detalle. En corto:

1. **Hora real de entrada**, no hora de digitación → curva de llegada por show
2. **Tasa de duplicados** → cuántos pases se comparten por captura de pantalla
3. **Tiempo entre escaneos** → largo de la fila, en vivo
4. **No-show por segmento** → qué cortesía no sirvió y a quién sí darle la próxima
5. **Pase instalado pero no escaneado** → intención sin asistencia, la señal más cara de conseguir hoy

## Honestidad sobre el alcance

Lo que está **construido y corriendo** en este repo: la proyección, el
backtest, el link de puerta, y la generación de pases de Google Wallet.

Lo que está **especificado pero no desplegado**: el ingest de escaneos y el
reentrenamiento automático. Los datos del hackathon son sintéticos, así que
un escáner en vivo no tendría contra qué validar. La spec está escrita al
nivel de detalle en que se puede implementar, no al nivel de idea bonita.

Lo que está **bloqueado por terceros**: Apple Wallet nativo necesita el
programa de desarrollador ($99/año) o un firmante externo. Ver
[`02-wallet-passes.md`](02-wallet-passes.md#apple-el-muro).
