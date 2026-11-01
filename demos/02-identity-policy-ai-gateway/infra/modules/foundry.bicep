// Microsoft Foundry account (kind AIServices) with a project, the agents' chat model, an embedding model for the
// knowledge index and a separate judge model for evaluation (module 4), so scoring never competes with the agent.
// Entra-only: disableLocalAuth=true, so the account has no usable API keys. That is what the
// "deny-local-auth" guardrail in ../../policy enforces for every other account in the resource group.

@description('Azure region. Australia East for model availability; New Zealand North is the data-residency alternative.')
param location string

@description('Globally unique Foundry account name (becomes the custom subdomain and the endpoint host).')
@minLength(3)
@maxLength(63)
param accountName string

@description('Foundry project name (child of the account).')
param projectName string

@description('Model deployment name the clients call (FOUNDRY_MODEL_NAME).')
param modelDeploymentName string

@description('Model name in the Foundry catalogue, e.g. gpt-5-mini.')
param modelName string

@description('Model version. Verify the current version in the Foundry model catalogue before recording.')
param modelVersion string

@description('Deployment SKU. GlobalStandard is the pay-per-token default.')
@allowed([ 'GlobalStandard', 'Standard', 'DataZoneStandard' ])
param modelSkuName string = 'GlobalStandard'

@description('Capacity in thousands of tokens per minute (TPM).')
@minValue(1)
param modelCapacity int = 50

@description('Embedding model deployment for the module 3 knowledge index (FOUNDRY_EMBEDDING_MODEL_NAME). Empty to skip.')
param embeddingModelName string = 'text-embedding-3-small'

@description('Embedding model version in the Foundry catalogue.')
param embeddingModelVersion string = '1'

@description('Embedding deployment capacity in thousands of tokens per minute.')
@minValue(1)
param embeddingCapacity int = 50

@description('Judge model deployment for the module 4 evaluators (FOUNDRY_EVAL_MODEL_NAME). Empty to judge with the chat model.')
param evalModelName string = 'gpt-5'

@description('Judge model version in the Foundry catalogue.')
param evalModelVersion string = '2025-08-07'

@description('Judge deployment capacity in thousands of tokens per minute. Evaluation bursts: 12 cases x 5 evaluators at once.')
@minValue(1)
param evalCapacity int = 250

@description('Keep public access on for the demo so the laptop and APIM v2 (no VNet) can reach it. Production: Disabled + private endpoints.')
@allowed([ 'Enabled', 'Disabled' ])
param publicNetworkAccess string = 'Enabled'

param tags object = {}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: accountName
    allowProjectManagement: true
    // No keys. Every caller (laptop, container, APIM) presents an Entra ID token.
    disableLocalAuth: true
    publicNetworkAccess: publicNetworkAccess
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Harbourline Site Operations'
    description: 'AI-Ready Azure course: identity, policy guardrails, the AI gateway, a grounded agent and its evaluation gate.'
  }
}

resource chatModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  // Cognitive Services serialises deployments per account; wait for the project first.
  dependsOn: [ project ]
}

// Second deployment: embeddings for the AI Search index and its vectorizer. Serialised after the chat model.
resource embeddingModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (!empty(embeddingModelName)) {
  parent: account
  name: embeddingModelName
  sku: {
    name: modelSkuName
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [ chatModel ]
}

// Third deployment: the evaluation judge. Serialised after the embedding model.
resource evalModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (!empty(evalModelName) && evalModelName != modelDeploymentName) {
  parent: account
  name: evalModelName
  sku: {
    name: modelSkuName
    capacity: evalCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: evalModelName
      version: evalModelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [ embeddingModel ]
}

// The project's managed identity needs the Foundry data plane on its own account for continuous evaluation (module 4):
// the evaluation rule reads datasets and writes runs as the project identity. Verified live: without it the rule is refused.
var roleAzureAIUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
resource projectAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, project.id, roleAzureAIUser)
  scope: account
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
    description: 'Foundry project identity: continuous evaluation reads datasets and writes runs.'
  }
}

output accountName string = account.name
output accountId string = account.id
output accountPrincipalId string = account.identity.principalId
output endpoint string = account.properties.endpoint
output openAiEndpoint string = 'https://${account.name}.openai.azure.com'
output cognitiveServicesEndpoint string = 'https://${account.name}.cognitiveservices.azure.com'
output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${project.name}'
output projectName string = project.name
output modelDeploymentName string = chatModel.name
output evalDeploymentName string = !empty(evalModelName) && evalModelName != modelDeploymentName ? evalModel!.name : chatModel.name
output embeddingDeploymentName string = !empty(embeddingModelName) ? embeddingModel!.name : ''
output projectPrincipalId string = project.identity.principalId
