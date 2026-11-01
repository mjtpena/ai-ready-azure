// Module 2 demo: managed identity, policy guardrail and AI gateway.
// Resource-group scope. deploy.sh creates rg-hbl-ops and runs this template.
//
//   policy.bicep      -> guardrails (definitions at subscription scope, assignments on this RG)
//   foundry.bicep     -> Foundry account (Entra-only) + project + model deployment
//   identity.bicep    -> user-assigned managed identity + roles (and the author's roles)
//   apim.bicep        -> API Management v2, managed-identity backend, Entra JWT + token limit + metrics + content safety
//   monitoring.bicep  -> Log Analytics, Application Insights, LLM logging
//   workload.bicep    -> optional ACI container proving the identity story from inside Azure
//   search.bicep      -> Azure AI Search for the module 3 knowledge index, with every role the demos need
//   connections.bicep -> Foundry project connections (AI Search, Application Insights) for modules 3 and 4
targetScope = 'resourceGroup'

@description('Primary region. Australia East for model availability; verify in the Foundry portal before recording.')
param location string = 'australiaeast'

@description('Resource name prefix shared across the course (hbl = Harbourline, ops = site operations).')
param prefix string = 'hbl-ops'

@description('Chat model deployment name clients call (FOUNDRY_MODEL_NAME).')
param modelDeploymentName string = 'gpt-5-mini'

@description('Model name in the Foundry catalogue.')
param modelName string = 'gpt-5-mini'

@description('Model version. verify in the Foundry model catalogue')
param modelVersion string = '2025-08-07'

@description('Model capacity in thousands of tokens per minute.')
param modelCapacity int = 50

@description('Judge model for the module 4 evaluators, deployed under its own name (FOUNDRY_EVAL_MODEL_NAME).')
param evalModelName string = 'gpt-5'

@description('Judge model version.')
param evalModelVersion string = '2025-08-07'

@description('Judge capacity in thousands of tokens per minute.')
param evalCapacity int = 250

@description('API Management v2 tier (Consumption lacks llm-token-limit and llm-content-safety).')
@allowed([ 'Basicv2', 'Standardv2' ])
param apimSku string = 'Basicv2'

@description('APIM publisher e-mail (required by APIM).')
param publisherEmail string

@description('APIM publisher name.')
param publisherName string = 'Harbourline Platform Team'

@description('Gateway token budget per site group per minute. Small so the 429 can be shown live.')
param tokensPerMinute int = 500

@description('Object ID of the author (az ad signed-in-user show --query id). Grants model roles for the laptop demo.')
param authorObjectId string = ''

@description('Deploy the policy guardrails (needs rights to create policy definitions at subscription scope).')
param deployPolicy bool = true

@description('Create the model allow-list policy. Set false if the deployments model.name alias is unavailable.')
param deployModelAllowListPolicy bool = true

@description('Audit (default) or Deny public network access on AI accounts. Deny breaks this demo without private endpoints.')
@allowed([ 'Audit', 'Deny', 'Disabled' ])
param publicNetworkEffect string = 'Audit'

@description('Approved regions for AI accounts.')
param allowedLocations array = [ 'australiaeast', 'newzealandnorth' ]

@description('Approved model names. The chat model above is always added.')
param allowedModels array = [ 'gpt-5-mini', 'gpt-5', 'gpt-5.1', 'gpt-5.2', 'gpt-4.1', 'gpt-4.1-mini', 'text-embedding-3-small', 'text-embedding-3-large' ]

@description('Stage 2: deploy the Site APIs as a Functions app, import them into APIM and export them as the MCP server hbl-site-tools.')
param deployMcp bool = true

@description('Deploy the ACI workload that calls the model with the managed identity.')
param deployWorkloadDemo bool = true

@description('Deploy Azure AI Search, the embedding deployment and the project connections used by modules 3 and 4.')
param deploySearch bool = true

@description('Embedding model for the knowledge index (FOUNDRY_EMBEDDING_MODEL_NAME).')
param embeddingModelName string = 'text-embedding-3-small'

@description('Azure AI Search tier.')
@allowed([ 'basic', 'standard' ])
param searchSku string = 'basic'

param tags object = {
  course: 'ai-ready-azure'
  module: '02-trust-and-control'
  owner: 'course-author'
  'delete-after': 'course-day'
}

var suffix = toLower(uniqueString(subscription().id, resourceGroup().id))
var foundryAccountName = 'aif-${prefix}-${suffix}'
var apimName = 'apim-${prefix}-${suffix}'
var searchName = 'srch-${prefix}-${suffix}'
var toolsAppName = 'func-${prefix}-site-api-${suffix}'
var toolsStorageName = toLower(take(replace('st${prefix}${suffix}', '-', ''), 24))

module policy 'modules/policy.bicep' = if (deployPolicy) {
  name: 'hbl-ops-policy'
  params: {
    allowedLocations: allowedLocations
    allowedModels: union(allowedModels, [ modelName ])
    deployModelAllowList: deployModelAllowListPolicy
    publicNetworkEffect: publicNetworkEffect
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'hbl-ops-foundry'
  params: {
    location: location
    accountName: foundryAccountName
    projectName: 'proj-${prefix}'
    modelDeploymentName: modelDeploymentName
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
    embeddingModelName: deploySearch ? embeddingModelName : ''
    evalModelName: evalModelName
    evalModelVersion: evalModelVersion
    evalCapacity: evalCapacity
    tags: tags
  }
}

module identity 'modules/identity.bicep' = {
  name: 'hbl-ops-identity'
  params: {
    location: location
    identityName: 'id-${prefix}-site-advisor'
    foundryAccountName: foundry.outputs.accountName
    authorObjectId: authorObjectId
    tags: tags
  }
}

module apim 'modules/apim.bicep' = {
  name: 'hbl-ops-apim'
  params: {
    location: location
    apimName: apimName
    skuName: apimSku
    publisherEmail: publisherEmail
    publisherName: publisherName
    foundryAccountName: foundry.outputs.accountName
    tokensPerMinute: tokensPerMinute
    tags: tags
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'hbl-ops-monitoring'
  params: {
    location: location
    workspaceName: 'log-${prefix}'
    appInsightsName: 'appi-${prefix}'
    apimName: apim.outputs.apimName
    tags: tags
  }
}

module workload 'modules/workload.bicep' = if (deployWorkloadDemo) {
  name: 'hbl-ops-workload'
  params: {
    location: location
    containerGroupName: 'ci-${prefix}-site-advisor'
    identityResourceId: identity.outputs.identityId
    identityClientId: identity.outputs.clientId
    openAiEndpoint: foundry.outputs.openAiEndpoint
    modelDeploymentName: foundry.outputs.modelDeploymentName
    tags: tags
  }
}

module search 'modules/search.bicep' = if (deploySearch) {
  name: 'hbl-ops-search'
  params: {
    location: location
    searchName: searchName
    skuName: searchSku
    foundryAccountName: foundry.outputs.accountName
    foundryProjectName: foundry.outputs.projectName
    workloadPrincipalId: identity.outputs.principalId
    authorObjectId: authorObjectId
    tags: tags
  }
}

module connections 'modules/connections.bicep' = if (deploySearch) {
  name: 'hbl-ops-connections'
  params: {
    foundryAccountName: foundry.outputs.accountName
    foundryProjectName: foundry.outputs.projectName
    searchServiceId: search!.outputs.searchId
    searchEndpoint: search!.outputs.endpoint
    searchLocation: location
    appInsightsId: monitoring.outputs.appInsightsId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
  }
}

module toolsApi 'modules/tools-api.bicep' = if (deployMcp) {
  name: 'hbl-ops-tools-api'
  params: {
    location: location
    appName: toolsAppName
    planName: 'plan-${prefix}-site-api'
    storageName: toolsStorageName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    tags: tags
  }
}

module mcp 'modules/mcp.bicep' = if (deployMcp) {
  name: 'hbl-ops-mcp'
  params: {
    apimName: apim.outputs.apimName
    toolsAppName: toolsApi!.outputs.appName
    toolsApiUrl: toolsApi!.outputs.apiUrl
  }
}

// ---- Outputs, named after the environment variables in docs/SCENARIO.md ----
output AZURE_LOCATION string = location
output RESOURCE_GROUP string = resourceGroup().name
output FOUNDRY_ACCOUNT_NAME string = foundry.outputs.accountName
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output FOUNDRY_PROJECT_NAME string = foundry.outputs.projectName
output FOUNDRY_MODEL_NAME string = foundry.outputs.modelDeploymentName
output FOUNDRY_EVAL_MODEL_NAME string = foundry.outputs.evalDeploymentName
output FOUNDRY_EMBEDDING_MODEL_NAME string = foundry.outputs.embeddingDeploymentName
output AI_SEARCH_NAME string = deploySearch ? search!.outputs.searchName : ''
output AI_SEARCH_ENDPOINT string = deploySearch ? search!.outputs.endpoint : ''
output AI_SEARCH_CONNECTION_ID string = deploySearch ? connections!.outputs.searchConnectionId : ''
output AI_SEARCH_CONNECTION_NAME string = deploySearch ? connections!.outputs.searchConnectionName : ''
output AZURE_OPENAI_ENDPOINT string = foundry.outputs.openAiEndpoint
output APIM_NAME string = apim.outputs.apimName
output APIM_GATEWAY_URL string = apim.outputs.gatewayUrl
output APIM_SUBSCRIPTION_RESOURCE_ID string = apim.outputs.primarySubscriptionResourceId
output APIM_SECONDARY_SUBSCRIPTION_RESOURCE_ID string = apim.outputs.secondarySubscriptionResourceId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
output APPINSIGHTS_NAME string = monitoring.outputs.appInsightsName
output LOG_ANALYTICS_WORKSPACE_NAME string = monitoring.outputs.workspaceName
output WORKLOAD_IDENTITY_CLIENT_ID string = identity.outputs.clientId
output WORKLOAD_IDENTITY_NAME string = identity.outputs.identityName
output WORKLOAD_CONTAINER_GROUP string = deployWorkloadDemo ? workload!.outputs.containerGroupName : ''
output PROJECT_PRINCIPAL_ID string = foundry.outputs.projectPrincipalId
output AI_SEARCH_ID string = deploySearch ? search!.outputs.searchId : ''
output TOOLS_FUNCTION_APP string = deployMcp ? toolsApi!.outputs.appName : ''
output APIM_MCP_URL string = deployMcp ? mcp!.outputs.mcpUrl : ''
output SITE_API_URL string = deployMcp ? mcp!.outputs.siteApiUrl : ''
output POLICY_ASSIGNMENTS array = deployPolicy ? policy!.outputs.assignmentNames : []
output POLICY_DEFINITIONS array = deployPolicy ? policy!.outputs.definitionNames : []
