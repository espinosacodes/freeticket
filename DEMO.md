# La demo

**Objetivo: 60 segundos.** Techo duro: 2 minutos.

La regla que manda todo lo que sigue:

> Al que ve el video no le importa en qué está hecho. Le importa que le
> resuelve el viernes en la noche.

Nada de Python, Lambda, HMAC, backtest, DynamoDB, modelo, pipeline. Ni una
sola vez. Si una frase no cambia lo que el usuario **hace mañana**, se corta.

---

## El corte de 60 segundos

### 0:00 – 0:08 · El dolor, en su idioma

Pantalla: el tablero, arriba.

> «Vendiste 500 entradas. ¿Cuántas personas entran? Hoy nadie lo sabe, y la
> puerta se arma a ojo.»

Sin presentarte. Sin decir «les voy a mostrar». Arrancá en el problema.

### 0:08 – 0:22 · La respuesta

Señalá la cifra grande, después una fila.

> «Esto te dice, show por show, cuánta gente va a entrar de verdad. Este
> vendió 623 y entran 242 — porque la mitad son cortesías, y la cortesía no
> llega. Con el mismo número de vendidas, dos shows llenan distinto.»

Ese ejemplo es todo el producto en una frase: **vendido ≠ entrado**, y el
sistema sabe la diferencia.

### 0:22 – 0:38 · La puerta

Abrí el link de puerta, en el teléfono.

> «Y esto le llega por WhatsApp al que está en la puerta. Cuánta gente
> esperar, a qué hora llega el pico, cuánta gente poner. Se abre y ya —
> nadie va a abrir un computador un viernes a las ocho.»

Pausá medio segundo en «3 personas en puerta». Ese es el producto haciendo
el trabajo que hoy hace la intuición de alguien.

### 0:38 – 0:55 · El momento

Teléfono, cámara, QR.

**Escaneo 1** → verde.

> «La entrada vive en la wallet del celular. Escaneás y entra.»

El contador sube en cámara. **Escaneo 2, el mismo código** → amarillo,
«Ya entró».

> «Y si el mismo código llega dos veces, te avisa. Hoy eso pasa y nadie se
> entera.»

**Este es el clip que se recuerda.** Si algo hay que sacrificar por tiempo,
se saca de los tramos anteriores, nunca de este.

### 0:55 – 1:00 · El cierre

> «Y cada persona que entra le enseña al sistema a acertar más la próxima.»

Cortá ahí. No agregues «gracias», no expliques nada más.

---

## Si necesitás los 2 minutos

Insertá **solo estas dos**, en este orden de prioridad, y nada más:

**A. El sin señal** (+12s, después del escaneo). Poné el teléfono en modo
avión y escaneá.

> «Y si en el bar no hay señal, la fila no se detiene. Se guarda y se sube
> solo cuando vuelve.»

Vale mucho porque cualquiera que haya trabajado una puerta sabe que ahí es
donde todo se cae.

**B. A quién darle la cortesía** (+15s, después de la mezcla).

> «Y como sabemos quién es cada comprador, se puede saber a quién sí le
> sirve una cortesía. Hoy se regalan a ciegas y entra menos de la mitad.»

Es el único momento donde el cruce con Boom aparece — **como beneficio, no
como técnica.**

---

## Traducción: de cómo está hecho → qué le das al usuario

Si se te escapa una de la izquierda, corregí en el momento con la derecha.

| No digas | Decí |
|---|---|
| «error medio de 4,7 personas» | «te falla por unas cinco personas» |
| «rango p10–p90» | «entre 151 y 205 — el peor y el mejor caso» |
| «cruzamos 3.995 ventas con Boom» | «sabemos quién es el que compró» |
| «token HMAC que expira» | «el link se vence solo, no queda dando vueltas» |
| «cola offline en localStorage» | «sin señal la fila no se detiene» |
| «la curva de llegada de julio» | «la gente llega 10 minutos antes de empezar» |
| «idempotente por scan_id» | «no cuenta a nadie dos veces» |
| «Lambda, DynamoDB, API Gateway» | *(nada — no lo menciones)* |

---

## Antes de grabar

```bash
cd ~/Documents/freeticket
python3 -m http.server 8777 --directory web
```

| Dónde | Qué |
|---|---|
| Pestaña 1 | https://espinosacodes.github.io/freeticket/ |
| Pestaña 2 | un link de puerta ya abierto (clic en «abrir →») |
| Pestaña 3 | `out/qr/ft_tkt_0000003.png` en grande |
| Teléfono | https://espinosacodes.github.io/freeticket/escaner.html |

El evento `ft_evt_0040` está en cero y los seis QR de `out/qr/` son válidos
contra el sistema real. Si ensayás y quedan marcados, avisá y se resetea.

**Grabá el escaneo sí o sí.** Si el celular no entra en cuadro, grabá la
pantalla del celular aparte y pegá los dos clips. Es el único momento que
nadie más va a tener.

---

## Para las preguntas, no para el video

Esto **no** va grabado. Es para la ronda de preguntas.

**«¿Qué tan confiable es el número?»**
> Se probó contra shows que el sistema nunca vio: falla por unas cinco
> personas. Y el rango no está inflado para no equivocarse — está calibrado
> para que 8 de cada 10 shows caigan adentro.

**«¿Cruzaron todos los compradores?»**
> El 63%. Y a propósito dejamos 56 sin cruzar: cuando había dos personas
> igual de probables, preferimos no adivinar. Inventar un match ensucia la
> proyección más de lo que la mejora.

**«¿El escáner funciona de verdad o es una maqueta?»**
> Funciona contra el sistema desplegado. Lo pueden probar ustedes desde el
> celular ahora mismo, con los códigos del repo.

**«¿Apple no avisa cuando la persona llega al lugar?»**
> No. Apple muestra la entrada en la pantalla de bloqueo cuando estás cerca,
> pero eso pasa solo en el teléfono — al que emite la entrada nunca le
> llega nada. La ubicación es comodidad para el usuario; el dato de
> asistencia es el escaneo.

*(Casi todo el mundo cree que ese aviso existe. Corregirlo vos mismo te
pone del lado del que sabe.)*

**«¿Cuánto falta para usarlo?»**
> El tablero, el link de puerta y el escáner están corriendo hoy. Para
> emitir entradas a nombre de FreeTicket falta un trámite con Google y otro
> con Apple. Ninguna decisión técnica pendiente.

---

## Lo que no hay que decir, nunca

- ❌ «Predecimos si **una persona** va a entrar» → se proyecta el show
  completo, no el individuo. No lo vamos a defender.
- ❌ «Apple nos avisa cuando llegan» → falso.
- ❌ «Detectamos fraude» → medimos códigos repetidos. Puede ser fraude o
  puede ser un error de la puerta. El dato es real; la interpretación no la
  afirmamos.
- ❌ «Sube la asistencia un 20%» → no hay con qué sostenerlo.
- ❌ Cualquier palabra de infraestructura.

---

## El formulario

| | |
|---|---|
| Repo | https://github.com/espinosacodes/freeticket |
| En vivo | https://espinosacodes.github.io/freeticket/ |
| Video | 60s (máx. 2 min) |
| Notas | [`NOTAS.md`](NOTAS.md) |
| Entregas | [`out/matches.csv`](out/matches.csv) · [`out/forecast.csv`](out/forecast.csv) |
