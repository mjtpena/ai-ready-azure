// Workload identity for the Site Operations Advisor: a user-assigned managed identity with data-plane roles
// on the Foundry account. No secret is created anywhere; the roles are the whole story.
// The same roles are optionally granted to the author (az login user) so client/call_model.py
// works from the laptop through the identical DefaultAzureCredential code path.

param location string

@description('Name of the user-assigned managed identity.')
param identityName string

@description('Existing Foundry account in this resource group that the identity may call.')
param foundryAccountName string

@description('Object ID of the author / developer user to grant the same roles (empty to skip).')
param authorObjectId string = ''

param tags object = {}

// Built-in role definition IDs (stable across tenants).
var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // inference on OpenAI models
var roleAzureAIUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'                 // Foundry project data plane (agents, evals) used by later modules

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: identityName
  location: location
  tags: tags
}

resource identityOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, roleCognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesOpenAIUser)
    description: 'Site Advisor workload identity: call models on the Foundry account.'
  }
}

resource identityAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identity.id, roleAzureAIUser)
  scope: foundry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
    description: 'Site Advisor workload identity: Foundry project data plane.'
  }
}

resource authorOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(authorObjectId)) {
  name: guid(foundry.id, authorObjectId, roleCognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    principalId: authorObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesOpenAIUser)
    description: 'Author laptop (az login) for the live demo.'
  }
}

resource authorAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(authorObjectId)) {
  name: guid(foundry.id, authorObjectId, roleAzureAIUser)
  scope: foundry
  properties: {
    principalId: authorObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
    description: 'Author laptop (az login) for the live demo.'
  }
}

output identityId string = identity.id
output identityName string = identity.name
output clientId string = identity.properties.clientId
output principalId string = identity.properties.principalId
