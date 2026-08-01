# NOTAS

## Qué asumí

**El cruce es un problema de precisión, no de cobertura.** El enunciado dice
que una parte grande de los compradores simplemente no está en Boom, y que
inventarles un match es peor que dejarlos sin match. Todo el diseño sale de
ahí: umbral en 0.72, margen mínimo de 0.08 sobre el segundo candidato, y
**56 ventas descartadas por ambiguas** aunque su mejor candidato pasaba el
umbral. Cruzamos 3.995 de 6.383 ventas (62,6%). Podría subir esa cifra
bajando el umbral; sería peor solución.

**Un nombre no identifica a nadie.** "Juan Pérez" hay muchos. El nombre solo
funciona como bono de corroboración sobre un email o un teléfono; como base
única exige además que la ciudad coincida, y aun así queda por debajo del
umbral salvo que otra señal lo acompañe.

**La asistencia se predice por entrada, no por evento.** Julio está
etiquetado ticket a ticket y ahí está la señal: el tipo de entrada es el
factor que más manda (pagada ~94%, cortesía ~42%). Un promedio por evento
borraría exactamente eso.

**`checked_in` es un dato digitado, no observado.** Es la asunción que más
me marcó y la que motivó todo `docs/`: se puede proyectar mejor sobre un
dato malo, pero tiene techo. Ver más abajo.

## Qué señal pesó más

En orden, medido sobre julio:

1. **El tipo de entrada.** Domina todo lo demás. La base por tipo explica la
   mayor parte de la varianza entre shows: dos eventos con el mismo
   `tickets_sold` y distinta mezcla proyectan muy distinto.
2. **El acto / la residencia.** Un show de residencia tiene cuatro hermanos
   en julio con el mismo público. El factor por artista, encogido por
   volumen (`n/(n+200)`), captura eso sin dejar que un acto con 30 entradas
   mande sobre la base.
3. **El perfil de Boom del comprador.** Aquí es donde el cruce de la Parte A
   paga. El `use_rate` **no** se usa como probabilidad — mezcla entradas de
   membresía (tope ~60%) con las de consumo mínimo (~75%) y se queda corto,
   que es la trampa que advierte el enunciado. Se usa como **bucket
   ordinal**, y "sin match en Boom" es su propia categoría: no estar en Boom
   es información, no un dato faltante.
4. Canal y anticipación de compra: aportan poco, pero aportan.

Los factores se estiman **en cascada**, cada uno sobre el residuo del
anterior, para no contar dos veces la misma señal.

## El rango p10–p90

No sale de la binomial. Una Poisson-binomial pura da un intervalo demasiado
angosto porque asume que cada persona decide por separado, y no es así:
llueve, el acto se vuelve famoso, el grupo entero no aparece.

Se mide la dispersión real evento a evento en julio y se calibra el ancho
contra el objetivo: **el ancho que en julio habría dejado adentro al 80% de
los eventos** (φ ≈ 1,25× la binomial). Calibrar contra el objetivo y no
contra la desviación estándar es deliberado — un intervalo más ancho es
cómodo para no equivocarse e inútil para dimensionar una puerta.

**Backtest honesto**, entrenando sin un quinto de los eventos de julio y
midiendo contra ellos:

| | |
|---|---|
| Eventos no vistos | 7 |
| Error medio | **4,7 personas** |
| Cobertura p10–p90 | **71%** (objetivo 80%) |

71% sobre 7 eventos es 5 de 7. Con esa muestra no se distingue de 80%, y lo
digo así en vez de redondear hacia arriba.

## Qué haría con cuatro horas más

**Primero, lo que ya está especificado y no alcancé a desplegar:** el
ingest de escaneos de `docs/01-scan-telemetry.md`. Es lo que convierte
`checked_in` de campo digitado en hecho observado, y con eso la curva de
llegada deja de ser aproximada y aparece una señal que hoy no existe —
*pase instalado y nunca escaneado*, o sea intención sin asistencia.

Después, por orden de retorno:

1. **Cruzar a nivel persona, no de venta.** Una venta con `qty=3` son tres
   entradas y hoy heredan todas el perfil del comprador. El acompañante de
   un fiel de Boom no es un fiel de Boom.
2. **Transitividad en el cruce.** Si la venta A y la venta B comparten
   teléfono y A tiene email limpio, B hereda evidencia. Hoy cada venta se
   resuelve sola.
3. **Los amigos de Boom (`social`).** No los usé. Quien va acompañado
   probablemente entra más que quien va solo, y `friends_count` está ahí.
4. **Calibrar el personal sugerido** contra el tiempo real de escaneo. Hoy
   las 40 personas/hora por portero son una estimación defendible pero no
   medida — y con la telemetría de escaneo se vuelve un número real.

## Uso de IA

Todo el desarrollo se hizo con Claude Code como par: exploración de los
datos, diseño del esquema de bloqueo y puntaje, el modelo en cascada, la
calibración del intervalo, el tablero y las specs de `docs/`. El criterio
sobre qué señal usar, qué umbral poner y qué **no** afirmar (ver la
corrección sobre la geolocalización de Apple en
`docs/02-wallet-passes.md`) se discutió explícitamente en vez de aceptarse
por defecto.
