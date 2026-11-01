#!/usr/bin/env bash
# Removes everything deploy.sh created, including the soft-deleted Foundry account and APIM instance
# (both would otherwise block a redeploy with the same names) and the subscription-scope policy definitions.
set -euo pipefail
cd "$(dirname "$0")"

: "${RESOURCE_GROUP:=rg-hbl-ops}"
: "${AZURE_LOCATION:=australiaeast}"
AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

if ! az group show --name "$RESOURCE_GROUP" --output none 2>/dev/null; then
  echo "Resource group $RESOURCE_GROUP does not exist; only purging leftovers."
  FOUNDRY_ACCOUNTS=""
  APIM_SERVICES=""
else
  FOUNDRY_ACCOUNTS="$(az cognitiveservices account list -g "$RESOURCE_GROUP" --query "[].name" -o tsv)"
  APIM_SERVICES="$(az apim list -g "$RESOURCE_GROUP" --query "[].name" -o tsv)"
  read -r -p "Delete resource group $RESOURCE_GROUP and everything in it? [y/N] " answer
  [[ "${answer,,}" == "y" ]] || { echo "Aborted."; exit 1; }
  az group delete --name "$RESOURCE_GROUP" --yes
fi

for acct in $FOUNDRY_ACCOUNTS; do
  echo "Purging soft-deleted Foundry account $acct..."
  az cognitiveservices account purge --name "$acct" --resource-group "$RESOURCE_GROUP" --location "$AZURE_LOCATION" || true
done

for apim in $APIM_SERVICES; do
  echo "Purging soft-deleted API Management service $apim..."
  az apim deletedservice purge --service-name "$apim" --location "$AZURE_LOCATION" || true
done

for def in hbl-ops-deny-local-auth hbl-ops-allowed-ai-locations hbl-ops-restrict-public-network hbl-ops-allowed-model-deployments; do
  if az policy definition show --name "$def" --output none 2>/dev/null; then
    echo "Deleting policy definition $def..."
    az policy definition delete --name "$def"
  fi
done

rm -f .env .deploy-outputs.json ../00-shared/.env
echo "Clean."
