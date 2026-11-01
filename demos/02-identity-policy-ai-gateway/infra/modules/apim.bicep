// Azure API Management as the single front door for models (the AI gateway).
// v2 SKU (Basicv2 default; Standardv2 for VNet integration). System-assigned identity authenticates to the
// Foundry account; the API is secured with Entra ID JWT validation plus a per-team subscription.
// The policy applied to the API is ../../apim/policies/all.xml.

param location string

@description('Globally unique APIM service name.')
param apimName string

@description('APIM v2 tier. llm-token-limit and llm-content-safety are NOT available on Consumption.')
@allowed([ 'Basicv2', 'Standardv2' ])
param skuName string = 'Basicv2'

param publisherEmail string
param publisherName string = 'Harbourline Platform Team'

@description('Existing Foundry account in this resource group used as the model and content-safety backend.')
param foundryAccountName string

@description('Audience the caller token must carry. Default: the Cognitive Services resource, so the same Entra token works direct and via the gateway. Hardening: an app registration URI such as api://hbl-ai-gateway.')
param entraAudience string = 'https://cognitiveservices.azure.com'

@description('Tokens per minute per site group before the gateway returns 429. Small on purpose so it trips live.')
@minValue(50)
param tokensPerMinute int = 500

param tags object = {}

var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // model inference
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'       // Content Safety (shield prompt, analyze text)

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource apim 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: 1
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: 'Enabled'
  }
}

// ---- RBAC: the gateway identity may call models and Content Safety on the Foundry account ----
resource apimOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, apim.id, roleCognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesOpenAIUser)
    description: 'AI gateway: forward inference calls to Foundry with its managed identity.'
  }
}

resource apimCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, apim.id, roleCognitiveServicesUser)
  scope: foundry
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
    description: 'AI gateway: llm-content-safety calls Content Safety on the Foundry account.'
  }
}

// ---- Named values referenced from the policy XML as {{name}} ----
resource nvTenantId 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: apim
  name: 'tenant-id'
  properties: {
    displayName: 'tenant-id'
    value: tenant().tenantId
    secret: false
  }
}

resource nvAudience 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: apim
  name: 'entra-audience'
  properties: {
    displayName: 'entra-audience'
    value: entraAudience
    secret: false
  }
}

resource nvTokensPerMinute 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: apim
  name: 'tokens-per-minute'
  properties: {
    displayName: 'tokens-per-minute'
    value: string(tokensPerMinute)
    secret: false
  }
}

// ---- Backends ----
resource foundryBackend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: apim
  name: 'foundry-backend'
  properties: {
    description: 'Foundry account (Azure OpenAI v1 inference surface). Auth is added by authentication-managed-identity in the policy.'
    protocol: 'http'
    url: 'https://${foundry.name}.openai.azure.com/openai'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// llm-content-safety authenticates with the credentials configured on its backend. Managed-identity backend
// credentials are what the Microsoft AI-Gateway labs use; the Bicep type bundle does not list the property yet,
// so the linter warning is suppressed. verify: deployment accepts credentials.managedIdentity (see README).
resource contentSafetyBackend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: apim
  name: 'content-safety-backend'
  properties: {
    description: 'Azure AI Content Safety on the Foundry account, called by llm-content-safety with the gateway identity.'
    protocol: 'http'
    url: 'https://${foundry.name}.cognitiveservices.azure.com'
    credentials: {
      #disable-next-line BCP037
      managedIdentity: {
        resource: 'https://cognitiveservices.azure.com'
      }
    }
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// ---- The API: Azure OpenAI v1 surface exposed at {gateway}/openai ----
resource api 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  parent: apim
  name: 'foundry-inference'
  properties: {
    displayName: 'Harbourline Foundry inference (AI gateway)'
    description: 'Front door for Foundry models. Entra ID token required; one APIM subscription per team.'
    path: 'openai'
    protocols: [ 'https' ]
    apiType: 'http'
    serviceUrl: 'https://${foundry.name}.openai.azure.com/openai'
    subscriptionRequired: true
    // The OpenAI SDKs send their key as "api-key", so accept the APIM subscription key there.
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
  }
}

var operations = [
  { name: 'chat-completions', displayName: 'Chat completions (v1)', method: 'POST', urlTemplate: '/v1/chat/completions' }
  { name: 'responses', displayName: 'Responses (v1)', method: 'POST', urlTemplate: '/v1/responses' }
  { name: 'embeddings', displayName: 'Embeddings (v1)', method: 'POST', urlTemplate: '/v1/embeddings' }
  { name: 'list-models', displayName: 'List models (v1)', method: 'GET', urlTemplate: '/v1/models' }
]

resource apiOperations 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = [for op in operations: {
  parent: api
  name: op.name
  properties: {
    displayName: op.displayName
    method: op.method
    urlTemplate: op.urlTemplate
  }
}]

// Legacy deployment-scoped route for clients still using the AzureOpenAI SDK class with api-version.
resource legacyChatOperation 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = {
  parent: api
  name: 'chat-completions-legacy'
  properties: {
    displayName: 'Chat completions (deployment-scoped, api-version)'
    method: 'POST'
    urlTemplate: '/deployments/{deployment-id}/chat/completions'
    templateParameters: [
      {
        name: 'deployment-id'
        type: 'string'
        required: true
      }
    ]
  }
}

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../../apim/policies/all.xml')
  }
  dependsOn: [ nvTenantId, nvAudience, nvTokensPerMinute, foundryBackend, contentSafetyBackend ]
}

// ---- Product and per-team subscriptions ----
resource product 'Microsoft.ApiManagement/service/products@2024-05-01' = {
  parent: apim
  name: 'hbl-site-ai'
  properties: {
    displayName: 'Harbourline Site AI'
    description: 'Model access for Harbourline site operations teams. One subscription per team; the subscription is the metering and budget unit.'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

resource productApi 'Microsoft.ApiManagement/service/products/apis@2024-05-01' = {
  parent: product
  name: api.name
}

var teams = [
  { name: 'site-ops-team', displayName: 'Site Operations team' }
  { name: 'facilities-finance-team', displayName: 'Facilities Finance team' }
]

resource teamSubscriptions 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = [for team in teams: {
  parent: apim
  name: team.name
  properties: {
    displayName: team.displayName
    scope: product.id
    state: 'active'
    allowTracing: false
  }
}]

output apimName string = apim.name
output apimId string = apim.id
output gatewayUrl string = apim.properties.gatewayUrl
output principalId string = apim.identity.principalId
output apiPath string = api.properties.path
output primarySubscriptionName string = teams[0].name
output primarySubscriptionResourceId string = teamSubscriptions[0].id
output secondarySubscriptionResourceId string = teamSubscriptions[1].id
