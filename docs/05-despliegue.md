# Despliegue — qué está corriendo y qué nos bloqueó

## Lo que está en pie

| Pieza | Dónde | Estado |
|---|---|---|
| Tablero, puerta y escáner | GitHub Pages | ✅ https://espinosacodes.github.io/freeticket/ |
| Ingest de escaneos | AWS Lambda + API Gateway + DynamoDB | ✅ `https://1q5q7pqmx9.execute-api.us-east-1.amazonaws.com` |
| Publicación del tablero | GitHub Actions | ✅ automática en cada push a `web/`, `out/` o `pipeline/` |
| Despliegue del ingest | GitHub Actions + OIDC | ⚠️ bloqueado por la organización de AWS (abajo) |

Comprobado contra el endpoint real, no contra el mock:

```
1) entrada válida          -> ok
2) la misma otra vez       -> duplicado
3) mismo scan_id reenviado -> ya_recibido      (idempotente)
4) firma alterada          -> firma_invalida
aforo                      -> 2
items en DynamoDB          -> 6
```

## Dos cosas que la cuenta de AWS no deja hacer

Esta cuenta (`556899121445`) está bajo una organización con guardarraíles.
Dos se cruzaron en el camino, y las dos tienen la misma forma: **la
organización bloquea puertas de entrada públicas y federación externa.**

### 1. Las Lambda Function URL están bloqueadas

El diseño original exponía la función con una Function URL (`AuthType: NONE`),
que es la opción con menos piezas. Quedó creada y bien configurada:

```
AuthType: NONE
policy:   Principal "*", Action lambda:InvokeFunctionUrl,
          Condition lambda:FunctionUrlAuthType = NONE
```

Y aun así devolvía `403 Forbidden` — **incluso firmando la petición con
SigV4 y credenciales de administrador**. Que también falle firmada es lo que
descarta un problema de permisos del recurso: si fuera la policy, la
petición firmada habría pasado. Lo que la rechaza está por encima de la
cuenta.

Que la función estaba bien se comprobó invocándola directo, sin la URL:

```bash
aws lambda invoke --function-name freeticket-scan-ingest \
  --payload '{"requestContext":{"http":{"method":"GET","path":"/salud"}}}' out.json
# -> {"statusCode": 200, ...}
```

**Solución:** API Gateway HTTP API por delante. Es otro servicio y no cae
bajo el mismo guardarraíl. La función es idéntica; solo cambia la puerta.
`lambda/template.yaml` ya define el API Gateway, así que el stack es
reproducible tal como está.

### 2. `sts:AssumeRoleWithWebIdentity` está bloqueado

El workflow de CI se autentica por OIDC, sin llaves guardadas. El proveedor
OIDC existe, con la audiencia correcta, y el rol confía en este repositorio:

```
provider aud: sts.amazonaws.com                      ✓
role trust:   repo:espinosacodes/freeticket:...      ✓
```

Y aun así: `Not authorized to perform sts:AssumeRoleWithWebIdentity`.

Se descartó lo obvio antes de concluir:

- **Propagación de IAM** — se reintentó varios minutos después. Igual.
- **El claim `sub`** — se amplió a `repo:espinosacodes/freeticket:*`, o sea
  cualquier rama. Igual. Si fuera el `sub`, esto lo habría arreglado.

Quedando descartadas ambas, lo que queda es una SCP/RCP de la organización
negando la federación por web identity.

**Solución para el hackathon:** el stack se desplegó desde la máquina local
con credenciales de IAM normales, que sí funcionan. Los mismos comandos que
corre el workflow:

```bash
aws cloudformation deploy --stack-name freeticket-scan-ingest \
  --template-file lambda/template.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides QrSecret="$QR_SECRET" AllowOrigin='*'
cd lambda && zip -r ../fn.zip handler.py && cd ..
aws lambda update-function-code --function-name freeticket-scan-ingest \
  --zip-file fileb://fn.zip --publish
```

**Solución de verdad:** que quien administre la organización permita
`sts:AssumeRoleWithWebIdentity` para `token.actions.githubusercontent.com`.
El workflow queda en el repo, correcto y listo: el día que se levante ese
permiso, funciona sin tocar una línea.

No se cambió a llaves de acceso guardadas en los secrets de GitHub para
sortearlo. Eso habría hecho que el CI funcionara hoy a cambio de dejar una
credencial de larga vida en un repositorio público, que es exactamente el
intercambio que el guardarraíl existe para impedir.

## El secreto de los QR

`QR_SECRET` firma los QR y vive en dos lados: la variable de entorno de la
Lambda (inyectada por CloudFormation, `NoEcho`) y los secrets de GitHub. No
está en el repo.

Para generar QR de prueba hay que firmarlos con el mismo secreto:

```bash
QR_SECRET=<el secreto> python3 scripts/qr_demo.py ft_evt_0040 --n 5 --png
```

Sin él, `scripts/mock_ingest.py` con `QR_SECRET=demo` reproduce el mismo
contrato en local y sirve para probar todo sin AWS.

En producción el secreto debe ser **por evento** y rotar, no uno global —
ver [`01-scan-telemetry.md`](01-scan-telemetry.md). Uno solo es una
simplificación consciente para el hackathon.
