# Guion de narración — 1:18

Orden de lo que se ve, con el texto exacto para la voz.

| # | Tiempo | En pantalla | Narración |
|---|---|---|---|
| 1 | 0:00–0:11 | `1-tablero.mp4` | Vendiste quinientas entradas. ¿Cuántas personas entran? Hoy nadie lo sabe, y la puerta se arma a ojo. |
| 2 | 0:11–0:28 | `1-tablero.mp4` (scroll) | Esto te dice, show por show, cuánta gente va a entrar de verdad. Mirá este: vendió doscientas ochenta y seis entradas. Entran ciento tres. Cien por ciento cortesías, y la cortesía no llega. |
| 3 | 0:28–0:42 | `2-puerta.mp4` | Y esto le llega por WhatsApp al que está en la puerta. Cuánta gente esperar, a qué hora llega el pico, cuánta gente poner. Nadie va a abrir un computador un viernes a las ocho. |
| 4 | 0:42–0:55 | **cámara: Android** | La entrada vive en la wallet del celular. Esto es un Android. |
| 5 | 0:55–1:06 | **cámara: iPhone** | Y esto es un iPhone. La misma entrada, en las dos. |
| 6 | 1:06–1:14 | **cámara: repetir Android** | Y si el mismo código llega dos veces, te avisa. Hoy eso pasa, y nadie se entera. |
| 7 | 1:14–1:18 | contador en pantalla | Cada persona que entra le enseña al sistema a acertar más la próxima. |

## Cómo filmar los tramos 4 a 6

Un solo plano fijo, celular en la mano, escáner abierto en el otro:

1. **Android** — abrí el pase de Google Wallet, apuntá el escáner. Verde, el
   contador pasa a **1**. Dejá que se vea el pase entero antes de escanear:
   ese es el plano que prueba que se generó bien.
2. **iPhone** — abrí el pase de Apple Wallet, apuntá. Verde, contador **2**.
3. **Android otra vez**, el mismo pase de antes → amarillo, «Ya entró».

Los tres escaneos van contra el sistema real. No hay nada simulado.

> El pase de Google trae la maqueta completa (nombre, puntos, tipo de
> entrada). El de Apple sale por Pass2U y hoy muestra marca y código, sin
> los campos de texto. Por eso **primero Android**: el plano bonito primero,
> y el iPhone entra a probar que funciona en las dos.

## Generar la voz

```bash
export OPENAI_API_KEY=sk-...            # tu llave, en tu terminal
python3 scripts/voz.py video/guion.md --out video/voz.mp3
```

Sale un `.mp3` por tramo y uno pegado. Si un tramo quedó largo o corto, se
edita el texto de la tabla y se vuelve a correr solo ese.

## Armar el video

```bash
# 1. poné tus clips de cámara en video/ como 4-android.mp4, 5-apple.mp4, 6-dup.mp4
# 2. pegá todo en orden
cd video && ffmpeg -y -f concat -safe 0 -i orden.txt -c copy mudo.mp4
# 3. montá la voz encima
ffmpeg -y -i mudo.mp4 -i voz.mp3 -c:v copy -c:a aac -shortest freeticket-final.mp4
```

Si el video queda más corto que la voz, alargá el clip del tablero; si queda
más largo, cortá del tablero. **Nunca del escaneo.**
