// A real workload inside Azure that calls the model with the user-assigned managed identity and nothing else:
// no key, no connection string, no certificate. Azure Container Instances running the Azure CLI image,
// restartPolicy Never, so it runs once on deployment and again on `az container start`.
// Read its output with `az container logs`.

param location string
param containerGroupName string

@description('Resource ID of the user-assigned managed identity (from identity.bicep).')
param identityResourceId string

@description('Client ID of that identity, used by `az login --identity --client-id`.')
param identityClientId string

@description('Foundry account OpenAI endpoint, e.g. https://aif-hbl-ops-xxxx.openai.azure.com')
param openAiEndpoint string

@description('Model deployment name to call.')
param modelDeploymentName string

param tags object = {}

// Bicep multi-line strings do not interpolate, so everything variable arrives through environment variables.
// gpt-5 is a reasoning model: reasoning_effort=minimal keeps a 300-token budget from being spent on hidden reasoning
// (120 tokens without it returned an empty answer). Keep this file LF (see .gitattributes).
var script = '''
set -e
echo "== Site Advisor workload (ACI) =="
echo "Signing in with the user-assigned managed identity ($AZURE_CLIENT_ID). No secret is present in this container."
az login --identity --client-id "$AZURE_CLIENT_ID" --output none
TOKEN=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)
echo "Entra token acquired. Claims:"
python3 - "$TOKEN" <<'PY' || true
import base64, json, sys
payload = sys.argv[1].split(".")[1]
claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
print(json.dumps({k: claims.get(k) for k in ("aud", "iss", "appid", "oid", "xms_mirid", "exp")}, indent=2))
PY
echo
echo "Calling $OPENAI_ENDPOINT/openai/v1/chat/completions (model=$MODEL) with Authorization: Bearer <token>"
az rest --method post --resource https://cognitiveservices.azure.com \
  --url "$OPENAI_ENDPOINT/openai/v1/chat/completions" \
  --headers "Content-Type=application/json" \
  --body "{\"model\":\"$MODEL\",\"max_completion_tokens\":300,\"reasoning_effort\":\"minimal\",\"messages\":[{\"role\":\"system\",\"content\":\"You are the Harbourline Site Operations Advisor. Answer in one sentence.\"},{\"role\":\"user\",\"content\":\"Why might chiller CH-SYD-008-1 at site HBL-SYD-008 trip twice in one afternoon during a Sydney heatwave?\"}]}" \
  --query "{model:model, answer:choices[0].message.content, usage:usage}" -o json
echo "== done =="
'''

resource workload 'Microsoft.ContainerInstance/containerGroups@2024-10-01-preview' = {
  name: containerGroupName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  properties: {
    osType: 'Linux'
    restartPolicy: 'Never'
    sku: 'Standard'
    containers: [
      {
        name: 'site-advisor-workload'
        properties: {
          image: 'mcr.microsoft.com/azure-cli:latest'
          command: [ '/bin/sh', '-c', script ]
          resources: {
            requests: {
              cpu: 1
              memoryInGB: 1
            }
          }
          environmentVariables: [
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'MODEL', value: modelDeploymentName }
          ]
        }
      }
    ]
  }
}

output containerGroupName string = workload.name
output containerGroupId string = workload.id
