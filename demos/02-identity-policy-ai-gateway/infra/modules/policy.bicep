// Policy guardrails for the course resource group: definitions at subscription scope (module),
// assignments at resource-group scope. Deny effects need no managed identity.
// The non-compliance messages are what the engineer sees in the failed deployment - make them helpful.

@description('Regions where Foundry / AI Services accounts may be created.')
param allowedLocations array = [ 'australiaeast', 'newzealandnorth' ]

@description('Model names teams may deploy.')
param allowedModels array = [ 'gpt-5-mini', 'gpt-5', 'gpt-5.1', 'gpt-5.2', 'gpt-4.1', 'gpt-4.1-mini', 'text-embedding-3-small', 'text-embedding-3-large' ]

@description('Create and assign the model allow-list policy (requires the deployments model.name alias).')
param deployModelAllowList bool = true

@description('Audit (default, demo-friendly) or Deny public network access on AI accounts.')
@allowed([ 'Audit', 'Deny', 'Disabled' ])
param publicNetworkEffect string = 'Audit'

module definitions 'policy-definitions.bicep' = {
  name: 'hbl-ops-policy-definitions'
  scope: subscription()
  params: {
    deployModelAllowList: deployModelAllowList
  }
}

resource denyLocalAuthAssignment 'Microsoft.Authorization/policyAssignments@2025-01-01' = {
  name: 'hbl-ops-deny-local-auth'
  properties: {
    displayName: 'Harbourline AI: Entra-only authentication on AI accounts'
    description: 'Foundry / AI Services accounts in this resource group must set disableLocalAuth=true.'
    policyDefinitionId: definitions.outputs.denyLocalAuthDefinitionId
    enforcementMode: 'Default'
    parameters: {
      effect: { value: 'Deny' }
    }
    nonComplianceMessages: [
      {
        message: 'Harbourline guardrail: AI accounts must disable key-based (local) authentication. Set properties.disableLocalAuth = true and use Entra ID (managed identity) instead. Owner: Platform team.'
      }
    ]
  }
}

resource allowedLocationsAssignment 'Microsoft.Authorization/policyAssignments@2025-01-01' = {
  name: 'hbl-ops-allowed-ai-locations'
  properties: {
    displayName: 'Harbourline AI: approved regions for AI accounts'
    description: 'Foundry / AI Services accounts may only be created in the approved NZ/AU regions.'
    policyDefinitionId: definitions.outputs.allowedLocationsDefinitionId
    enforcementMode: 'Default'
    parameters: {
      allowedLocations: { value: allowedLocations }
      effect: { value: 'Deny' }
    }
    nonComplianceMessages: [
      {
        message: 'Harbourline guardrail: AI accounts must be deployed in an approved region (${join(allowedLocations, ', ')}). Building and tenant data stays in NZ/AU. Owner: Platform team.'
      }
    ]
  }
}

resource restrictPublicNetworkAssignment 'Microsoft.Authorization/policyAssignments@2025-01-01' = {
  name: 'hbl-ops-restrict-public-network'
  properties: {
    displayName: 'Harbourline AI: restrict public network access on AI accounts'
    description: 'Audit in the course (the demo needs public reachability); Deny once private endpoints are in place.'
    policyDefinitionId: definitions.outputs.restrictPublicNetworkDefinitionId
    enforcementMode: 'Default'
    parameters: {
      effect: { value: publicNetworkEffect }
    }
    nonComplianceMessages: [
      {
        message: 'Harbourline guardrail: AI accounts should use private endpoints (publicNetworkAccess=Disabled) or an IP allow-list (networkAcls.defaultAction=Deny).'
      }
    ]
  }
}

resource allowedModelsAssignment 'Microsoft.Authorization/policyAssignments@2025-01-01' = if (deployModelAllowList) {
  name: 'hbl-ops-allowed-model-deployments'
  properties: {
    displayName: 'Harbourline AI: approved model allow-list'
    description: 'Only models reviewed by the platform team may be deployed.'
    policyDefinitionId: definitions.outputs.allowedModelsDefinitionId
    enforcementMode: 'Default'
    parameters: {
      allowedModels: { value: allowedModels }
      effect: { value: 'Deny' }
    }
    nonComplianceMessages: [
      {
        message: 'Harbourline guardrail: this model is not on the approved list (${join(allowedModels, ', ')}). Request a review from the Platform team to add it.'
      }
    ]
  }
}

output assignmentNames array = concat(
  [ denyLocalAuthAssignment.name, allowedLocationsAssignment.name, restrictPublicNetworkAssignment.name ],
  deployModelAllowList ? [ 'hbl-ops-allowed-model-deployments' ] : []
)
output definitionNames array = definitions.outputs.definitionNames
