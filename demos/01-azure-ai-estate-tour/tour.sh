#!/usr/bin/env bash
# A tour of Azure's AI estate from the control plane, in about two minutes.
# Usage:  ./tour.sh                          (live, needs `az login`)
#         DEMO_NO_PAUSE=1 ./tour.sh          (straight through: rehearsal, CI, recording)
#         TOUR_STEPS="1 3 4 5 7" ./tour.sh   (only those steps)
#         DEMO_MODE=mock ./tour.sh           (offline, prints the canned run in fallback/tour-output.txt)
set -euo pipefail
LOCATION="${AZURE_LOCATION:-australiaeast}"
ALT_LOCATION="${AZURE_ALT_LOCATION:-newzealandnorth}"

if [[ "${DEMO_MODE:-}" == "mock" ]]; then
  cat "$(dirname "$0")/fallback/tour-output.txt"
  exit 0
fi

step() { printf '\n\033[1;33m▶ %s\033[0m\n\033[2m$ %s\033[0m\n' "$1" "$2"; }
pause() { [[ -n "${DEMO_NO_PAUSE:-}" ]] && { echo; return; }; read -r -p $'\n\033[2m[enter to continue]\033[0m'; }
want() { [[ -z "${TOUR_STEPS:-}" ]] || [[ " ${TOUR_STEPS} " == *" $1 "* ]]; }

if want 1; then
step "1. One control plane: every Azure region, filtered to Australia and New Zealand" \
     "az account list-locations --query \"[?metadata.geographyGroup=='Asia Pacific' && (contains(name,'australia') || contains(name,'newzealand'))].{region:name, zones:length(availabilityZoneMappings||\\\`[]\\\`)}\" -o table"
az account list-locations \
  --query "[?metadata.geographyGroup=='Asia Pacific' && (contains(name,'australia') || contains(name,'newzealand'))].{region:name, zones:length(availabilityZoneMappings||\`[]\`)}" -o table
pause
fi

if want 2; then
step "2. The resource provider behind Foundry (Microsoft.CognitiveServices) and its resource types" \
     "az provider show -n Microsoft.CognitiveServices --query \"resourceTypes[].resourceType\" -o tsv | sort | head -25"
az provider show -n Microsoft.CognitiveServices --query "resourceTypes[].resourceType" -o tsv | sort | head -25
pause
fi

if want 3; then
step "3. Which models can be deployed in ${LOCATION} right now (first 25 by name)" \
     "az cognitiveservices model list -l ${LOCATION} --query \"sort_by([?kind=='AIServices' && model.format=='OpenAI'], &model.name)[].{name:model.name, version:model.version, skus:join(',', model.skus[].name)}\" -o table | head -27"
# kind=='AIServices': the catalogue lists every model once per account kind (AIServices and OpenAI); keep one copy.
az cognitiveservices model list -l "${LOCATION}" \
  --query "sort_by([?kind=='AIServices' && model.format=='OpenAI'], &model.name)[].{name:model.name, version:model.version, skus:join(',', model.skus[].name)}" -o table | head -27
pause
fi

if want 4; then
step "4. Same question for ${ALT_LOCATION}: the residency conversation starts here" \
     "az cognitiveservices model list -l ${ALT_LOCATION} --query \"[?model.format=='OpenAI'].model.name\" -o tsv | sort -u | wc -l"
echo -n "OpenAI model families available in ${ALT_LOCATION}: "
if alt_models="$(az cognitiveservices model list -l "${ALT_LOCATION}" --query "[?model.format=='OpenAI'].model.name" -o tsv 2>/dev/null)"; then
  echo "$alt_models" | sort -u | grep -c . || true
else
  echo "0  (Microsoft.CognitiveServices does not serve ${ALT_LOCATION} yet: no model catalogue, no Foundry accounts)"
fi
echo -n "OpenAI model families available in ${LOCATION}:    "
az cognitiveservices model list -l "${LOCATION}" --query "[?model.format=='OpenAI'].model.name" -o tsv | sort -u | grep -c . || true
pause
fi

if want 5; then
step "5. Quota is per subscription, per region, per model: current usage in ${LOCATION}" \
     "az cognitiveservices usage list -l ${LOCATION} --query \"[?contains(name.value,'OpenAI')].{quota:name.value, used:currentValue, limit:limit}\" -o table | head -20"
az cognitiveservices usage list -l "${LOCATION}" \
  --query "[?contains(name.value,'OpenAI')].{quota:name.value, used:currentValue, limit:limit}" -o table | head -20
pause
fi

if want 6; then
step "6. Guardrails exist out of the box: built-in Azure Policy definitions for Cognitive Services / Foundry" \
     "az policy definition list --query \"[?policyType=='BuiltIn' && (contains(displayName,'Cognitive Services') || contains(displayName,'Azure AI Services')) && !starts_with(displayName,'[Deprecated]')].{policy:displayName, effect:policyRule.then.effect}\" -o table"
az policy definition list \
  --query "[?policyType=='BuiltIn' && (contains(displayName,'Cognitive Services') || contains(displayName,'Azure AI Services')) && !starts_with(displayName,'[Deprecated]')].{policy:displayName, effect:policyRule.then.effect}" -o table
pause
fi

if want 7; then
step "7. What AI resources exist in the course's resource group (everything is an ARM resource with an id)"      "az resource list -g ${RESOURCE_GROUP:-rg-hbl-ops} --query \"[].{name:name, type:type, region:location}\" -o table"
az resource list -g "${RESOURCE_GROUP:-rg-hbl-ops}"   --query "sort_by([].{name:name, type:type, region:location}, &type)" -o table
fi

printf '\n\033[1;32mTour complete.\033[0m One control plane, one resource provider for models, quota per region, guardrails built in.\n'
