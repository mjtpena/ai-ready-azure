// Azure AI Search for the Site Advisor knowledge index (module 3) plus every role the demos need.
// Entra-only (disableLocalAuth=true) to match the "no keys" story; the semantic ranker is on the free plan,
// which the Basic tier supports for the handful of queries a course makes.

param location string

@description('Globally unique search service name (lower-case letters, digits and dashes).')
@minLength(2)
@maxLength(60)
param searchName string

@description('Search tier. Basic is the cheapest tier with the semantic ranker.')
@allowed([ 'basic', 'standard' ])
param skuName string = 'basic'

@description('Existing Foundry account in this resource group (the embedding model lives here).')
param foundryAccountName string

@description('Name of the Foundry project under that account (its managed identity runs the agent search tool).')
param foundryProjectName string

@description('Principal id of the Site Advisor user-assigned identity (reads the index from a workload).')
param workloadPrincipalId string = ''

@description('Object id of the author (builds the index from the laptop). Empty to skip.')
param authorObjectId string = ''

param tags object = {}

// Built-in role definition IDs.
var roleSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var roleSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var roleSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var roleCognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName

  resource project 'projects' existing = {
    name: foundryProjectName
  }
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: true
    semanticSearch: 'free'
  }
}

// The project's identity queries the index through the agent's azure_ai_search tool (project connection, AAD).
resource projectIndexReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundry::project.id, roleSearchIndexDataReader)
  scope: search
  properties: {
    principalId: foundry::project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataReader)
    description: 'Foundry project: agent AI Search tool reads the knowledge index.'
  }
}

// The Azure AI Search tool also needs Search Index Data Contributor and Search Service Contributor on the project
// identity (with Reader only the agent returns "Access denied ... managed identity access
// to the search service"). Same shape as the Microsoft docs for the AI Search tool with an AAD connection.
resource projectIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundry::project.id, roleSearchIndexDataContributor)
  scope: search
  properties: {
    principalId: foundry::project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataContributor)
    description: 'Foundry project: agent AI Search tool (data plane).'
  }
}

resource projectServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundry::project.id, roleSearchServiceContributor)
  scope: search
  properties: {
    principalId: foundry::project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchServiceContributor)
    description: 'Foundry project: agent AI Search tool (reads index definitions).'
  }
}

resource accountIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundry.id, roleSearchIndexDataContributor)
  scope: search
  properties: {
    principalId: foundry.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataContributor)
    description: 'Foundry account: agent AI Search tool (data plane).'
  }
}

resource accountServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundry.id, roleSearchServiceContributor)
  scope: search
  properties: {
    principalId: foundry.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchServiceContributor)
    description: 'Foundry account: agent AI Search tool (reads index definitions).'
  }
}

// The account identity too (Foundry resolves some connections with the account identity).
resource accountIndexReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, foundry.id, roleSearchIndexDataReader)
  scope: search
  properties: {
    principalId: foundry.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataReader)
    description: 'Foundry account: read the knowledge index.'
  }
}

// The search service embeds queries with the Foundry embedding deployment (index vectorizer).
resource searchOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, search.id, roleCognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesOpenAIUser)
    description: 'AI Search vectorizer: embed queries with the Foundry embedding model.'
  }
}

resource workloadIndexReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(workloadPrincipalId)) {
  name: guid(search.id, workloadPrincipalId, roleSearchIndexDataReader)
  scope: search
  properties: {
    principalId: workloadPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataReader)
    description: 'Site Advisor workload identity: read the knowledge index.'
  }
}

resource authorServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(authorObjectId)) {
  name: guid(search.id, authorObjectId, roleSearchServiceContributor)
  scope: search
  properties: {
    principalId: authorObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchServiceContributor)
    description: 'Author: create and update the index definition (01_create_index.py).'
  }
}

resource authorIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(authorObjectId)) {
  name: guid(search.id, authorObjectId, roleSearchIndexDataContributor)
  scope: search
  properties: {
    principalId: authorObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataContributor)
    description: 'Author: upload chunks to the index (01_create_index.py).'
  }
}

output searchName string = search.name
output searchId string = search.id
output endpoint string = 'https://${search.name}.search.windows.net'
output principalId string = search.identity.principalId
