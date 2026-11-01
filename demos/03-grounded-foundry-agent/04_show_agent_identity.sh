#!/usr/bin/env bash
# The agent is a principal: show the Entra agent identity Foundry provisioned for the project and its agents.
#   ./04_show_agent_identity.sh            (needs az login; reads demos/00-shared/.env)
# Foundry creates an Entra Agent ID blueprint and an agent identity per project (and per agent for new agents); the
# project's ARM properties carry their ids and Microsoft Graph lists them as #microsoft.graph.agentIdentity.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source ../00-shared/.env; set +a
export MSYS_NO_PATHCONV=1

step() { printf '\n\033[1;33m▶ %s\033[0m\n\033[2m$ %s\033[0m\n' "$1" "$2"; }

PROJECT_ID="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${FOUNDRY_ACCOUNT_NAME}/projects/${FOUNDRY_PROJECT_NAME}"

step "1. The Foundry project carries an agent identity (ARM properties.agentIdentity)" \
     "az rest --method get --url \"https://management.azure.com\${PROJECT_ID}?api-version=2025-10-01-preview\" --query properties.agentIdentity -o json"
az rest --method get --url "https://management.azure.com${PROJECT_ID}?api-version=2025-10-01-preview" --query properties.agentIdentity -o json

AGENT_IDENTITY_ID="$(az rest --method get --url "https://management.azure.com${PROJECT_ID}?api-version=2025-10-01-preview" --query properties.agentIdentity.agentIdentityId -o tsv)"

step "2. In Entra ID that identity is a service principal of type agentIdentity, not a user and not an app" \
     "az ad sp show --id \$AGENT_IDENTITY_ID --query '{name:displayName, type:servicePrincipalType, odata:\"@odata.type\", enabled:accountEnabled}' -o json"
az ad sp show --id "$AGENT_IDENTITY_ID" --query '{name:displayName, type:servicePrincipalType, odata:"@odata.type", enabled:accountEnabled}' -o json

step "3. Every agent identity in the tenant that belongs to this course (Graph, filtered on the name prefix)" \
     "az rest --method get --url 'https://graph.microsoft.com/beta/servicePrincipals/microsoft.graph.agentIdentity' --query \"value[?starts_with(displayName,'\${FOUNDRY_ACCOUNT_NAME}')].{name:displayName, created:createdDateTime}\" -o table"
az rest --method get --url 'https://graph.microsoft.com/beta/servicePrincipals/microsoft.graph.agentIdentity' \
  --query "value[?starts_with(displayName,'${FOUNDRY_ACCOUNT_NAME}')].{name:displayName, created:createdDateTime}" -o table

printf '\n\033[1;32mAn agent is a principal.\033[0m Conditional Access, access reviews and sign-in logs apply to it like any other identity.\n'
