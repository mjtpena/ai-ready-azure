#!/usr/bin/env bash
# AI red teaming in the cloud runs only from a Foundry project in East US 2 or North Central US (October 2026), and the
# course's project is in Australia East. This stands up a minimal project in East US 2 next to the course, publishes a
# copy of the production agent there (instructions only: the cloud red team cannot run function tools, and the knowledge index stays in Australia East), and starts the
# red-team run against it. The scorecard then lives in that project's Evaluations page.
#
#   ./red_team_region.sh up        # resource group + Foundry account/project/models (about 10 minutes), roles, agent, run
#   ./red_team_region.sh status    # the run's status and attack success rate
#   ./red_team_region.sh down      # delete the resource group
#
# Needs: az login with Owner (or User Access Administrator) on the subscription, the course .env in demos/00-shared.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="$ROOT/.venv/Scripts/python.exe"; [ -x "$PY" ] || PY=python
RG="${RED_TEAM_RG:-rg-hbl-ops-redteam}"
LOCATION="${RED_TEAM_LOCATION:-eastus2}"
STATE="$HERE/eval/red_team_region.env"
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1

# shellcheck disable=SC1091
set -a; source "$ROOT/demos/00-shared/.env"; set +a

up() {
  local suffix; suffix="$(date +%s | tail -c 6)"
  az group create -n "$RG" -l "$LOCATION" --tags course=ai-ready-azure module=04 owner=course-author delete-after=recording purpose=red-teaming -o none
  az deployment group create -g "$RG" -n foundry-redteam \
    --template-file "$ROOT/demos/02-identity-policy-ai-gateway/infra/modules/foundry.bicep" \
    --parameters location="$LOCATION" accountName="aif-hbl-ops-rt$suffix" projectName=proj-hbl-ops-rt \
      modelDeploymentName=gpt-5-mini modelName=gpt-5-mini modelVersion=2025-08-07 modelCapacity=50 \
      embeddingModelName='' evalModelName=gpt-5 evalModelVersion=2025-08-07 evalCapacity=100 \
    --query "properties.outputs" -o json > "$HERE/eval/red_team_region.json"
  local endpoint account_id
  endpoint="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['projectEndpoint']['value'])" "$HERE/eval/red_team_region.json")"
  account_id="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['accountId']['value'])" "$HERE/eval/red_team_region.json")"
  # the signed-in user needs the data plane (Foundry User) on the new account; the project identity got it from the module
  az role assignment create --assignee-object-id "$(az ad signed-in-user show --query id -o tsv)" --assignee-principal-type User \
    --role "Foundry User" --scope "$account_id" -o none 2>/dev/null || true
  printf 'FOUNDRY_PROJECT_ENDPOINT=%s\nFOUNDRY_MODEL_NAME=gpt-5-mini\nFOUNDRY_EVAL_MODEL_NAME=gpt-5\nAGENT_TOOLS=local\nRED_TEAM_STRATEGIES=Flip,Base64\n' "$endpoint" > "$STATE"
  echo "project $endpoint"
  echo "waiting 120 s for the role to take effect"; sleep 120
  run
}

with_region() {  # run a course script against the red-team project
  # shellcheck disable=SC1090
  ( set -a; source "$STATE"; set +a; "$@" )
}

run() {
  ( cd "$HERE/../03-grounded-foundry-agent" && with_region "$PY" 02_create_agent.py --no-tools | tail -3 )
  ( cd "$HERE" && with_region "$PY" 05_red_team.py )
}

status() {
  local run_id; run_id="$(cd "$HERE" && "$PY" -c "import json; print(json.load(open('eval/red_team.json'))['run_id'])")"
  ( cd "$HERE" && with_region "$PY" 05_red_team.py --status "$run_id" )
}

down() { az group delete -n "$RG" --yes --no-wait; echo "deleting $RG"; }

case "${1:-up}" in up) up ;; run) run ;; status) status ;; down) down ;; *) echo "usage: $0 up|run|status|down"; exit 2 ;; esac
