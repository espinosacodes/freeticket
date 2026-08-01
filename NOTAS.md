# NOTAS

## Qué asumí

**El cruce es un problema de precisión, no de cobertura.** El enunciado dice
que buena parte de los compradores no está en Boom y que inventarles un
match es peor que dejarlos sin match. Todo sale de ahí: umbral en 0,72,
margen mínimo sobre el segundo candidato, y **56 ventas descartadas por
ambiguas** aunque su mejor candidato pasaba el umbral. Cruzamos 3.995 de
6.383 (62,6%); bajar el umbral subiría esa cifra y empeoraría la solución.

**La asistencia se predice por entrada, no por evento.** Julio está
etiquetado ticket a ticket, y ahí está la señal. Un promedio por evento
borraría lo que más manda: la mezcla de tipos de entrada.

**`checked_in` es un dato digitado, no observado.** Alguien lo llena. Si se
marca en lote, la hora miente; si no se marca a los que entraron tarde, la
tasa queda baja para siempre. Proyectar mejor sobre eso tiene techo — por
eso además cerramos el círculo con el escaneo en la puerta.

## Qué señal pesó más

1. **El tipo de entrada.** Domina todo. Pagada ~94%, cortesía ~42%: dos
   shows con las mismas ventas y distinta mezcla proyectan muy distinto.
2. **El acto y su residencia.** Un show de residencia tiene cuatro hermanos
   en julio con el mismo público.
3. **El perfil de Boom del comprador** — aquí paga el cruce de la Parte A.
   El `use_rate` crudo **no** se usa como probabilidad: mezcla membresía
   (tope ~60%) con consumo mínimo (~75%) y se queda corto, que es la trampa
   que advierte el enunciado. Se usa como bucket ordinal, y «sin match en
   Boom» es su propia categoría — no estar en Boom es información, no un
   dato faltante.

**El rango p10–p90 no sale de la binomial**, que sería demasiado angosta
porque asume que cada persona decide por separado. Se mide la dispersión
real de julio y se calibra contra el objetivo. Backtest sobre 7 eventos no
vistos: **error medio 4,7 personas**, 71% dentro del rango (objetivo 80%;
son 5 de 7, y con esa muestra no se distingue del objetivo).

## Qué haría con cuatro horas más

1. **Cruzar a nivel persona, no de venta.** Una venta con `qty=3` son tres
   entradas que hoy heredan todas el perfil del comprador. El acompañante
   de un fiel de Boom no es un fiel de Boom.
2. **Transitividad en el cruce:** si dos ventas comparten teléfono y una
   tiene email limpio, la otra hereda evidencia.
3. **Usar `social`.** Quien va acompañado entra más que quien va solo, y
   `friends_count` está ahí sin usar.
4. **Calibrar el personal sugerido** contra el tiempo real de escaneo — que
   ya es medible, porque el ingest quedó desplegado.

## Uso de IA

Todo se hizo con Claude Code como par: exploración, esquema de bloqueo y
puntaje, el modelo en cascada, la calibración del intervalo, el tablero y
las specs. El criterio sobre qué umbral poner y qué **no** afirmar se
discutió en vez de aceptarse por defecto — por ejemplo la corrección sobre
la geolocalización de Apple en [`docs/02-wallet-passes.md`](docs/02-wallet-passes.md):
no reporta la llegada al emisor, aunque casi todo el mundo cree que sí.

---

El desarrollo completo —los factores en cascada, la calibración del
intervalo, y las decisiones de color y de orden del tablero— está en
[`docs/06-metodo.md`](docs/06-metodo.md).
