# La demo — qué grabar y por qué gana

Dos minutos. Sin slides, sin presentación personal, sin «hola, mi nombre es».
Se abre la pantalla y funciona.

---

## La tesis, en 15 segundos

> El reto pide proyectar cuánta gente entra. Lo hicimos: error medio de 4,7
> personas. Pero abajo hay un problema más grande — **`checked_in` es un
> campo que alguien llena, no un hecho que el sistema observa.** Proyectar
> mejor sobre un dato malo tiene techo. Así que además cerramos el círculo:
> el mismo escaneo que deja entrar a la persona genera el dato.

Si solo se puede decir una frase, es esa. Todo lo demás la sostiene.

---

## Antes de grabar — checklist

```bash
cd ~/Documents/freeticket
QR_SECRET=demo python3 scripts/mock_ingest.py 8788 &        # o el endpoint real
QR_SECRET=demo python3 scripts/qr_demo.py --n 5 --png       # QR en out/qr/
```

Ten abierto y listo:

| Pestaña | Qué |
|---|---|
| 1 | https://espinosacodes.github.io/freeticket/ |
| 2 | un link de puerta ya abierto (clic en «abrir →» de cualquier show) |
| 3 | `out/qr/ft_tkt_0000001.png` en grande, para apuntarle la cámara |
| Teléfono | https://espinosacodes.github.io/freeticket/escaner.html?api=… |

**Grabá la pantalla del computador y filmá el teléfono aparte, o compartí la
pantalla del teléfono.** Lo que no puede pasar es que el escaneo quede fuera
de cuadro: es el momento que nadie más va a tener.

---

## El guion, minuto a minuto

### 0:00 – 0:20 · El número

Pestaña 1. No expliques la interfaz, leé el resultado.

> «3.519 personas esperadas sobre las 5.209 entradas ya vendidas para
> agosto. Backtest sobre 7 shows de julio que el modelo nunca vio: **error
> medio de 4,7 personas.**»

Señalá una fila. La barra muestra el rango p10–p90 y la marca del esperado.

> «Y esto no es un promedio por evento. Se predice entrada por entrada.»

### 0:20 – 0:45 · Por qué la mezcla manda

Bajá a «Mezcla de entradas». Buscá una fila con cortesía alta.

> «Este show vendió 623 entradas y proyecta 242. No es que la gente no
> quiera venir: **la mitad son cortesías.** En julio la entrada pagada entró
> al 94% y la cortesía al 42%. La mezcla explica la mayor parte de la
> diferencia entre dos shows que vendieron lo mismo.»

Esto es lo que separa un modelo que entendió el negocio de uno que ajustó
una curva.

### 0:45 – 1:05 · El cruce, y lo que decidimos NO hacer

Bajá a «Calidad del cruce».

> «3.995 de 6.383 ventas cruzadas con Boom. Pero lo importante es al revés:
> **56 ventas tenían dos candidatos casi empatados y las dejamos sin
> match.** El enunciado dice que inventarle un match a un comprador nuevo es
> peor que dejarlo sin match, así que el umbral está puesto para dejar gente
> afuera.»

Mencioná una sola sutileza, la que demuestra criterio:

> «Y cuando el email coincide exacto pero el nombre no comparte ni un token,
> es la firma de que compró con el correo de la pareja. Ese match baja de
> confianza en vez de subir.»

### 1:05 – 1:25 · La puerta

Pestaña 2, el link efímero. Idealmente en la vista móvil.

> «Esto se manda por WhatsApp a quien está en la puerta. Sin cuenta, sin
> app. Cuánta gente se espera, el rango, el pico de llegada — que está 10
> minutos **antes** de la hora de inicio — y cuánta gente poner. **Y caduca
> solo tres horas después del show**, porque un link vivo con un número
> viejo es peor que ningún link.»

### 1:25 – 1:55 · El escaneo — el momento que gana

Teléfono. Apuntá al QR de la pantalla.

> «Y esto es lo que hoy no existe.»

**Escaneo 1** → verde, «Adelante», el contador sube.

> «El pase vive en la wallet del teléfono. El mismo escaneo que la deja
> entrar **es** el dato: hora real, no hora de digitación.»

**Escaneo 2, el mismo QR** → ámbar, «Ya entró».

> «Y esto es un pase compartido. Hoy eso es invisible: el portero decide y
> no queda registro. Acá queda medido.»

Si te queda aire, poné el teléfono en modo avión y escaneá otro:

> «Sin señal la puerta no se detiene. Queda en cola y sube sola cuando
> vuelve la red.»

### 1:55 – 2:00 · El cierre

> «Julio se etiquetó a mano. Con esto, cada noche produce 300 etiquetas
> limpias y el modelo se reentrena solo. **El activo no es el modelo, es el
> dato que hoy nadie está capturando.**»

---

## Cómo se conecta cada beat con lo que califican

Los criterios de las slides, y qué momento de la demo los ataca:

| Criterio | El beat | Por qué pega |
|---|---|---|
| **Credibilidad del cruce, precisión sobre cobertura** | 0:45 — las 56 descartadas | Casi todos van a presumir cobertura. Presumir lo que descartaste demuestra que leíste el enunciado. |
| **Proyección con rangos honestos** | 0:00 — MAE 4,7 y el backtest | El backtest es sobre eventos **no vistos**, y el rango está calibrado contra el 80% objetivo, no inflado para no fallar. |
| **Usabilidad real para la puerta** | 1:05 — el link efímero | No es un dashboard que alguien tendría que abrir. Es un WhatsApp que caduca. |
| **Insights inesperados sobre patrones de acceso** | 1:25 — duplicados y curva de llegada | Nadie más va a mostrar una métrica de fuga por pases compartidos, porque nadie más va a estar capturando el escaneo. |
| **Uso de IA** | implícito en todo | Está documentado en `NOTAS.md`. No hace falta gastar segundos de video. |

**Dónde está la ventaja.** Los criterios 1 y 2 los va a atacar todo el
mundo, y ahí se compite por décimas. Los criterios 3 y 4 son donde casi
nadie va a llegar, porque exigen haber construido algo que se toca. Ahí es
donde el escáner vale más que cualquier mejora marginal del modelo.

---

## Las preguntas difíciles, y la respuesta honesta

Prepará estas cinco. La honestidad acá suma más que una respuesta pulida.

**«¿La cobertura del cruce no es baja? 62%.»**
> Es la cobertura correcta para este dataset. El enunciado dice
> explícitamente que una parte grande de los compradores no está en Boom.
> Bajar el umbral subiría el número y ensuciaría la proyección, porque un
> match falso le mete un perfil de asistencia ajeno a una entrada real.

**«¿Cómo sé que el rango p10–p90 es honesto?»**
> Porque no sale de la binomial. Medimos la dispersión real evento a evento
> en julio y calibramos el ancho contra el objetivo del 80%. En el backtest
> dio 71% sobre 7 eventos — que es 5 de 7 y no se distingue del 80% con esa
> muestra. Lo reportamos así en vez de redondear hacia arriba.

**«El escáner: ¿esto sirve con datos sintéticos?»**
> El escáner no depende del dataset. Valida una firma HMAC y registra el
> escaneo. Lo que es sintético es la data histórica, no el mecanismo. Está
> corriendo, y las reglas de idempotencia están probadas.

**«¿Apple Wallet no detecta cuando la persona llega al venue?»**
> No. Apple muestra el pase en la pantalla de bloqueo cerca del venue, pero
> **eso es local al dispositivo, el emisor nunca se entera.** No hay ping de
> llegada. La geolocalización es UX; la señal de asistencia es el escaneo, y
> solo el escaneo. Está escrito así en `docs/02-wallet-passes.md`.

*(Esta es la que puede ganar la ronda de preguntas: la mayoría de la gente
cree que sí existe ese ping. Corregirlo vos mismo, sin que te lo pregunten,
te pone del lado del que sabe.)*

**«¿Qué falta para producción?»**
> El ingest está desplegable — CloudFormation, Lambda y DynamoDB están en
> `lambda/`, con CI por OIDC y sin llaves guardadas. Falta el Issuer ID de
> Google Wallet, y Apple nativo necesita el programa de desarrollador.
> Ninguna de las dos es una decisión técnica pendiente; son trámites.

---

## Lo que NO hay que decir

Cuidado con estas, porque son las que se caen con una repregunta:

- ❌ «Predecimos si **una persona** va a entrar.» → Se proyecta un evento
  sumando probabilidades por entrada. La probabilidad individual no está
  calibrada y no la vamos a defender.
- ❌ «Apple nos avisa cuando llegan.» → Falso. Ver arriba.
- ❌ «Detectamos fraude.» → Medimos duplicados. Que un pase se escanee dos
  veces puede ser fraude o puede ser un error de la puerta. La métrica es
  real; la interpretación no la afirmamos.
- ❌ «El modelo aprende solo.» → Todavía no. Está **escrito para** consumir
  esos campos, y esa es la diferencia entre una spec seria y una promesa.
- ❌ Prometer números de negocio («subimos la asistencia 20%»). No hay con
  qué sostenerlo y el jurado lo va a notar.

---

## Qué entregar en el formulario

| | |
|---|---|
| Repo | https://github.com/espinosacodes/freeticket |
| Demo en vivo | https://espinosacodes.github.io/freeticket/ |
| Video | 2 minutos, según el guion de arriba |
| Notas | [`NOTAS.md`](NOTAS.md) |
| Entregas | [`out/matches.csv`](out/matches.csv) · [`out/forecast.csv`](out/forecast.csv) |
