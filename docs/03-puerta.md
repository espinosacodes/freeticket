# Spec — el link efímero de la puerta

Uno de los dos extras que el reto pide explícitamente.

> «Quien está en la puerta el viernes no va a abrir un notebook.»

## Qué es

Un link que se manda por WhatsApp al que va a estar en la puerta, unas horas
antes del show. Se abre en el teléfono, sin cuenta, sin app, sin login.
Muestra cuatro cosas y nada más:

```
┌─────────────────────────────────┐
│  Ace of Clubs · mié 20:30       │
│                                 │
│      178  personas              │
│      entre 151 y 205            │
│                                 │
│  de 241 entradas vendidas       │
│                                 │
│  Pico 20:10–20:30 · 96 personas │
│  Sugerido: 3 en puerta          │
│                                 │
│  Este link caduca a las 23:30   │
└─────────────────────────────────┘
```

## Por qué caduca

No es teatro de seguridad. El link lleva la proyección de un show concreto,
se reenvía en grupos de WhatsApp y nadie lo borra. A las tres horas el show
ya pasó y el número dejó de ser cierto: un link vivo con un número viejo es
peor que ningún link.

```
/puerta/<token>

token = base64url(event_id | exp | hmac)
exp   = starts_at + 3h
```

Sin base de datos de tokens: se valida la firma y se compara `exp` con el
reloj. Se pueden emitir mil y no hay nada que limpiar después.

## De dónde sale cada número

| En pantalla | De dónde |
|---|---|
| `178 personas` | `expected_attendance` de `out/forecast.csv` |
| `entre 151 y 205` | `p10` – `p90` |
| `241 entradas` | `tickets_sold` |
| `Pico 20:10–20:30` | `out/arrival_curve.csv`, medida sobre 4.969 check-ins de julio |
| `3 en puerta` | ver abajo |

## El personal sugerido

La regla, deliberadamente simple para poder defenderla:

```
llegadas_en_el_pico = esperados × pct_del_decil_pico
personal            = ceil(llegadas_en_el_pico / 40)     # 40 personas/hora por portero
mínimo 2 (uno escanea, uno resuelve problemas)
```

40 por hora sale de la curva de julio y de un escaneo que toma ~8 segundos
con margen. **No** está calibrado contra el tiempo real de escaneo, porque
ese dato no existe todavía — existirá cuando corra
[la telemetría de escaneo](01-scan-telemetry.md). Es la primera cosa que se
recalibra con datos reales.

Se muestra el pico, no el total, porque la puerta se dimensiona por el peor
momento, no por la noche entera.

## Cuando haya escaneo en vivo

El mismo link, con los escaneos entrando, deja de ser una proyección y pasa
a ser un tablero:

```
      112 / 178 esperados
      ████████████░░░░░░░
      63% · faltan 66 · van 12 min de show
```

Es el mismo endpoint y el mismo token. Lo único que cambia es que hay un
contador real contra el cual comparar la proyección — y esa comparación,
noche tras noche, es el set de entrenamiento que hoy no existe.
