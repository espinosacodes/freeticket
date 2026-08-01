#!/usr/bin/env bash
# Se corre UNA vez, a mano, con credenciales de AWS válidas en tu terminal.
#
# Crea el proveedor OIDC de GitHub y un rol que solo este repositorio puede
# asumir. Después de esto, GitHub Actions despliega sin ninguna llave
# guardada en ningún lado: no hay AWS_ACCESS_KEY_ID en los secrets, así que
# no hay nada que se pueda filtrar.
#
#   bash scripts/aws-bootstrap.sh
set -euo pipefail

REPO="${REPO:-espinosacodes/freeticket}"
ROLE="${ROLE:-freeticket-github-deploy}"
REGION="${AWS_REGION:-us-east-1}"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "Cuenta AWS: $ACCOUNT · repo: $REPO · región: $REGION"

# 1. Proveedor OIDC de GitHub (idempotente).
ARN_OIDC="arn:aws:iam::${ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$ARN_OIDC" >/dev/null 2>&1; then
  echo "Proveedor OIDC: ya existe"
else
  aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
  echo "Proveedor OIDC: creado"
fi

# 2. Rol que SOLO puede asumir este repo, y solo desde la rama main.
TRUST=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "${ARN_OIDC}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": { "token.actions.githubusercontent.com:sub": "repo:${REPO}:ref:refs/heads/main" }
    }
  }]
}
JSON
)

if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$ROLE" --policy-document "$TRUST"
  echo "Rol $ROLE: actualizado"
else
  aws iam create-role --role-name "$ROLE" \
    --assume-role-policy-document "$TRUST" \
    --description "Despliegue del ingest de escaneos de FreeTicket desde GitHub Actions" >/dev/null
  echo "Rol $ROLE: creado"
fi

# 3. Permisos. Acotados al stack y a la función de este proyecto.
POLICY=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": ["cloudformation:*"],
      "Resource": "arn:aws:cloudformation:${REGION}:${ACCOUNT}:stack/freeticket-scan-ingest/*" },
    { "Effect": "Allow",
      "Action": ["lambda:*"],
      "Resource": "arn:aws:lambda:${REGION}:${ACCOUNT}:function:freeticket-scan-ingest" },
    { "Effect": "Allow",
      "Action": ["dynamodb:*"],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT}:table/freeticket-scans" },
    { "Effect": "Allow",
      "Action": ["iam:CreateRole","iam:DeleteRole","iam:GetRole","iam:PassRole",
                 "iam:AttachRolePolicy","iam:DetachRolePolicy",
                 "iam:PutRolePolicy","iam:DeleteRolePolicy","iam:GetRolePolicy",
                 "iam:ListRolePolicies","iam:ListAttachedRolePolicies","iam:TagRole"],
      "Resource": "arn:aws:iam::${ACCOUNT}:role/freeticket-scan-ingest-FnRole-*" }
  ]
}
JSON
)
aws iam put-role-policy --role-name "$ROLE" \
  --policy-name freeticket-deploy --policy-document "$POLICY"
echo "Permisos: aplicados"

ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE}"
echo
echo "Listo. Ahora registrá esto en GitHub (una sola vez):"
echo
echo "  gh secret set AWS_DEPLOY_ROLE_ARN --body '${ROLE_ARN}'"
echo "  gh secret set QR_SECRET --body \"\$(openssl rand -hex 32)\""
echo "  gh variable set AWS_REGION --body '${REGION}'"
echo
echo "Y después: gh workflow run 'Desplegar el ingest de escaneos'"
