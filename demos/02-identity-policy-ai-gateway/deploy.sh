#!/usr/bin/env bash
# Deploys the course demo stack into rg-hbl-ops. Idempotent: re-run after any change.
# Needs: az CLI (logged in), Owner or Contributor + Resource Policy Contributor on the subscription
# (policy definitions are created at subscription scope), and permission to create role assignments.
set -euo pipefail
cd "$(dirname "$0")"

: "${RESOURCE_GROUP:=rg-hbl-ops}"
: "${AZURE_LOCATION:=australiaeast}"
: "${FOUNDRY_MODEL_NAME:=gpt-5-mini}"
: "${FOUNDRY_MODEL_VERSION:=2025-08-07}"
: "${FOUNDRY_EVAL_MODEL_NAME:=gpt-5}"          # the evaluation judge (module 4), its own deployment
: "${FOUNDRY_EVAL_MODEL_VERSION:=2025-08-07}"
: "${APIM_SKU:=Basicv2}"
: "${TOKENS_PER_MINUTE:=500}"
: "${PUBLISHER_NAME:=Harbourline Platform Team}"
: "${DEPLOY_POLICY:=true}"
: "${DEPLOY_MODEL_ALLOWLIST_POLICY:=true}"
: "${DEPLOY_WORKLOAD_DEMO:=true}"
: "${PUBLIC_NETWORK_EFFECT:=Audit}"
: "${DEPLOY_MCP:=true}"             # stage 2: the Site APIs as a Functions app + the APIM MCP server

# Windows: `python3` on PATH is often the Microsoft Store stub, so prefer an activated venv's `python`.
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/Scripts/python.exe" ]]; then PY="$VIRTUAL_ENV/Scripts/python.exe"
  elif [[ -x "$(dirname "$0")/../../.venv/Scripts/python.exe" ]]; then PY="$(dirname "$0")/../../.venv/Scripts/python.exe"
  elif [[ -x "$(dirname "$0")/../../.venv/bin/python" ]]; then PY="$(dirname "$0")/../../.venv/bin/python"
  else PY="$(command -v python3 || command -v python)"; fi
fi

AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
PUBLISHER_EMAIL="${PUBLISHER_EMAIL:-$(az account show --query user.name -o tsv)}"
PRESENTER_OBJECT_ID="${PRESENTER_OBJECT_ID:-$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)}"
DEPLOYMENT_NAME="hbl-ops-m2-$(date -u +%Y%m%d%H%M%S)"

echo "Subscription : $AZURE_SUBSCRIPTION_ID"
echo "Resource grp : $RESOURCE_GROUP ($AZURE_LOCATION)"
echo "Model        : $FOUNDRY_MODEL_NAME $FOUNDRY_MODEL_VERSION   APIM: $APIM_SKU   token budget: $TOKENS_PER_MINUTE TPM"
echo "Author    : ${PRESENTER_OBJECT_ID:-<not resolved - laptop needs roles granted manually>}"
echo "Search       : ${DEPLOY_SEARCH:=true} (AI Search + embedding deployment + project connections for modules 3 and 4)"
echo

for rp in Microsoft.CognitiveServices Microsoft.ApiManagement Microsoft.Search Microsoft.ContainerInstance Microsoft.OperationalInsights Microsoft.Insights; do
  if [[ "$(az provider show -n "$rp" --query registrationState -o tsv 2>/dev/null)" != "Registered" ]]; then
    echo "Registering resource provider $rp (one-off, can take a few minutes)..."
    az provider register -n "$rp" --wait --output none
  fi
done

az group create --name "$RESOURCE_GROUP" --location "$AZURE_LOCATION" \
  --tags course=ai-ready-azure module=02-trust-and-control delete-after=course-day --output none

echo "Deploying infra/main.bicep as $DEPLOYMENT_NAME (APIM v2 takes 5-10 minutes on first run)..."
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --template-file infra/main.bicep \
  --parameters \
      location="$AZURE_LOCATION" \
      publisherEmail="$PUBLISHER_EMAIL" \
      publisherName="$PUBLISHER_NAME" \
      modelDeploymentName="$FOUNDRY_MODEL_NAME" \
      modelName="$FOUNDRY_MODEL_NAME" \
      modelVersion="$FOUNDRY_MODEL_VERSION" \
      evalModelName="$FOUNDRY_EVAL_MODEL_NAME" \
      evalModelVersion="$FOUNDRY_EVAL_MODEL_VERSION" \
      apimSku="$APIM_SKU" \
      tokensPerMinute="$TOKENS_PER_MINUTE" \
      authorObjectId="$PRESENTER_OBJECT_ID" \
      deployPolicy="$DEPLOY_POLICY" \
      deployModelAllowListPolicy="$DEPLOY_MODEL_ALLOWLIST_POLICY" \
      deployWorkloadDemo="$DEPLOY_WORKLOAD_DEMO" \
      publicNetworkEffect="$PUBLIC_NETWORK_EFFECT" \
  --query "properties.outputs" --output json > .deploy-outputs.json

out() { "$PY" -c 'import json,sys; d=json.load(open(".deploy-outputs.json")); k=sys.argv[1].lower(); v=next((x.get("value","") for n,x in d.items() if n.lower()==k), ""); print(v if isinstance(v,str) else json.dumps(v))' "$1"; }  # az CLI camel-cases output names, so match case-insensitively

FOUNDRY_ACCOUNT_NAME="$(out FOUNDRY_ACCOUNT_NAME)"
FOUNDRY_PROJECT_ENDPOINT="$(out FOUNDRY_PROJECT_ENDPOINT)"
AZURE_OPENAI_ENDPOINT="$(out AZURE_OPENAI_ENDPOINT)"
APIM_NAME="$(out APIM_NAME)"
APIM_GATEWAY_URL="$(out APIM_GATEWAY_URL)"
APIM_SUBSCRIPTION_RESOURCE_ID="$(out APIM_SUBSCRIPTION_RESOURCE_ID)"
APPLICATIONINSIGHTS_CONNECTION_STRING="$(out APPLICATIONINSIGHTS_CONNECTION_STRING)"
WORKLOAD_IDENTITY_CLIENT_ID="$(out WORKLOAD_IDENTITY_CLIENT_ID)"
WORKLOAD_CONTAINER_GROUP="$(out WORKLOAD_CONTAINER_GROUP)"
FOUNDRY_PROJECT_NAME="$(out FOUNDRY_PROJECT_NAME)"
FOUNDRY_EMBEDDING_MODEL_NAME="$(out FOUNDRY_EMBEDDING_MODEL_NAME)"
FOUNDRY_EVAL_MODEL_NAME="$(out FOUNDRY_EVAL_MODEL_NAME)"
AI_SEARCH_NAME="$(out AI_SEARCH_NAME)"
AI_SEARCH_ENDPOINT="$(out AI_SEARCH_ENDPOINT)"
AI_SEARCH_CONNECTION_ID="$(out AI_SEARCH_CONNECTION_ID)"
AI_SEARCH_ID="$(out AI_SEARCH_ID)"
PROJECT_PRINCIPAL_ID="$(out PROJECT_PRINCIPAL_ID)"
WORKLOAD_IDENTITY_NAME="$(out WORKLOAD_IDENTITY_NAME)"
TOOLS_FUNCTION_APP="$(out TOOLS_FUNCTION_APP)"
APIM_MCP_URL="$(out APIM_MCP_URL)"
SITE_API_URL="$(out SITE_API_URL)"

if [[ -n "$TOOLS_FUNCTION_APP" ]]; then
  echo "Zip-deploying the Site APIs to $TOOLS_FUNCTION_APP..."
  rm -rf tools-api/shared && mkdir -p tools-api/shared
  cp ../00-shared/site_tools.py tools-api/shared/ && cp -r ../00-shared/data tools-api/shared/data
  rm -rf tools-api/shared/data/knowledge
  ( cd tools-api && rm -f ../.tools-api.zip && "$PY" -c "import shutil; shutil.make_archive('../.tools-api', 'zip', '.')" )
  az functionapp deployment source config-zip -g "$RESOURCE_GROUP" -n "$TOOLS_FUNCTION_APP" --src .tools-api.zip --build-remote true --output none
  rm -f .tools-api.zip
fi

echo "Reading the site-ops-team subscription key from APIM..."
APIM_SUBSCRIPTION_KEY="$(az rest --method post \
  --url "https://management.azure.com${APIM_SUBSCRIPTION_RESOURCE_ID}/listSecrets?api-version=2024-05-01" \
  --query primaryKey -o tsv)"

cat > .env <<ENV
# Generated by deploy.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ). Do not commit.
AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID
AZURE_LOCATION=$AZURE_LOCATION
RESOURCE_GROUP=$RESOURCE_GROUP
FOUNDRY_ACCOUNT_NAME=$FOUNDRY_ACCOUNT_NAME
FOUNDRY_PROJECT_ENDPOINT=$FOUNDRY_PROJECT_ENDPOINT
FOUNDRY_MODEL_NAME=$FOUNDRY_MODEL_NAME
AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT
APIM_NAME=$APIM_NAME
APIM_GATEWAY_URL=$APIM_GATEWAY_URL
APIM_SUBSCRIPTION_KEY=$APIM_SUBSCRIPTION_KEY
APPLICATIONINSIGHTS_CONNECTION_STRING="$APPLICATIONINSIGHTS_CONNECTION_STRING"
WORKLOAD_IDENTITY_CLIENT_ID=$WORKLOAD_IDENTITY_CLIENT_ID
WORKLOAD_CONTAINER_GROUP=$WORKLOAD_CONTAINER_GROUP
ENV

# One .env for the whole course: modules 03 and 04 load ../00-shared/.env (see 00-shared/.env.example).
cat > ../00-shared/.env <<ENV
# Generated by demos/02-identity-policy-ai-gateway/deploy.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ). Do not commit.
AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID
AZURE_LOCATION=$AZURE_LOCATION
RESOURCE_GROUP=$RESOURCE_GROUP
FOUNDRY_ACCOUNT_NAME=$FOUNDRY_ACCOUNT_NAME
FOUNDRY_PROJECT_NAME=$FOUNDRY_PROJECT_NAME
FOUNDRY_PROJECT_ENDPOINT=$FOUNDRY_PROJECT_ENDPOINT
FOUNDRY_MODEL_NAME=$FOUNDRY_MODEL_NAME
FOUNDRY_EVAL_MODEL_NAME=$FOUNDRY_EVAL_MODEL_NAME
FOUNDRY_EMBEDDING_MODEL_NAME=${FOUNDRY_EMBEDDING_MODEL_NAME:-text-embedding-3-small}
FOUNDRY_AGENT_NAME=hbl-site-ops-advisor
AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT
AI_SEARCH_NAME=$AI_SEARCH_NAME
AI_SEARCH_ENDPOINT=$AI_SEARCH_ENDPOINT
AI_SEARCH_INDEX=hbl-site-knowledge
AI_SEARCH_CONNECTION_ID=$AI_SEARCH_CONNECTION_ID
AI_SEARCH_VECTOR_DIMENSIONS=1536
AI_SEARCH_QUERY_TYPE=vector_semantic_hybrid
APIM_NAME=$APIM_NAME
APIM_GATEWAY_URL=$APIM_GATEWAY_URL
APIM_SUBSCRIPTION_KEY=$APIM_SUBSCRIPTION_KEY
APPLICATIONINSIGHTS_CONNECTION_STRING="$APPLICATIONINSIGHTS_CONNECTION_STRING"
AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
WORKLOAD_IDENTITY_CLIENT_ID=$WORKLOAD_IDENTITY_CLIENT_ID
WORKLOAD_CONTAINER_GROUP=$WORKLOAD_CONTAINER_GROUP
AGENT_TOOLS=local
DEMO_MODE=
ENV

if [[ -n "$WORKLOAD_CONTAINER_GROUP" ]]; then
  # The container ran once during the deployment, usually before its role assignments had propagated; run it again now.
  az container start -g "$RESOURCE_GROUP" -n "$WORKLOAD_CONTAINER_GROUP" --no-wait --output none || true
fi

echo
echo "Deployed. Environment written to $(pwd)/.env and ../00-shared/.env (python-dotenv picks them up). To export in this shell:"
echo
sed -e 's/^#.*//' -e '/^$/d' -e 's/^/export /' .env
echo
echo "Next: python client/call_model.py --via direct     (Act 1)"
echo "      az deployment group create -g $RESOURCE_GROUP --template-file policy/noncompliant.bicep   (Act 2, expected to FAIL)"
echo "      python client/call_model.py --via gateway --repeat 4   (Act 3)"
if [[ -n "$WORKLOAD_CONTAINER_GROUP" ]]; then
  echo "      az container logs -g $RESOURCE_GROUP -n $WORKLOAD_CONTAINER_GROUP   (Act 1, managed identity from inside Azure)"
fi
echo
echo "Reminder: APIM $APIM_SKU bills hourly. Run ./cleanup.sh when the recording is done."
