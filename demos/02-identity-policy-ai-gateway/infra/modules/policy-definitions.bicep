// Custom policy definitions live at subscription scope (policyDefinitions cannot be created in a resource group).
// Called from policy.bicep with scope: subscription(). The rules themselves are the JSON files in
// ../../policy/definitions so they can also be created with `az policy definition create`.
targetScope = 'subscription'

@description('Also create the model allow-list definition. Set false if the deployments alias is not available in your tenant (see policy JSON description).')
param deployModelAllowList bool = true

var denyLocalAuth = loadJsonContent('../../policy/definitions/deny-local-auth.json')
var allowedLocations = loadJsonContent('../../policy/definitions/allowed-locations.json')
var restrictPublicNetwork = loadJsonContent('../../policy/definitions/deny-public-network-access.json')
var allowedModels = loadJsonContent('../../policy/definitions/allowed-model-deployments.json')

resource denyLocalAuthDef 'Microsoft.Authorization/policyDefinitions@2025-01-01' = {
  name: denyLocalAuth.name
  properties: denyLocalAuth.properties
}

resource allowedLocationsDef 'Microsoft.Authorization/policyDefinitions@2025-01-01' = {
  name: allowedLocations.name
  properties: allowedLocations.properties
}

resource restrictPublicNetworkDef 'Microsoft.Authorization/policyDefinitions@2025-01-01' = {
  name: restrictPublicNetwork.name
  properties: restrictPublicNetwork.properties
}

resource allowedModelsDef 'Microsoft.Authorization/policyDefinitions@2025-01-01' = if (deployModelAllowList) {
  name: allowedModels.name
  properties: allowedModels.properties
}

output denyLocalAuthDefinitionId string = denyLocalAuthDef.id
output allowedLocationsDefinitionId string = allowedLocationsDef.id
output restrictPublicNetworkDefinitionId string = restrictPublicNetworkDef.id
output allowedModelsDefinitionId string = deployModelAllowList ? allowedModelsDef.id : ''
output definitionNames array = concat(
  [ denyLocalAuth.name, allowedLocations.name, restrictPublicNetwork.name ],
  deployModelAllowList ? [ allowedModels.name ] : []
)
