// Foundry project connections used by modules 3 and 4:
//   * CognitiveSearch (AAD)  -> the agent's azure_ai_search tool resolves the index through this connection
//   * AppInsights (ApiKey)   -> project_client.telemetry.get_application_insights_connection_string() and the
//                               portal Traces / Evaluations tabs
// Both are children of the project, so they are created here after the project and the targets exist.

@description('Existing Foundry account in this resource group.')
param foundryAccountName string

@description('Existing Foundry project under that account.')
param foundryProjectName string

@description('Azure AI Search service resource id.')
param searchServiceId string

@description('Azure AI Search endpoint, e.g. https://srch-hbl-ops-xxxx.search.windows.net')
param searchEndpoint string

@description('Region of the search service (recorded in the connection metadata).')
param searchLocation string

@description('Application Insights resource id.')
param appInsightsId string

@description('Application Insights connection string (stored as the connection credential).')
@secure()
param appInsightsConnectionString string

@description('Connection names (what AI_SEARCH_CONNECTION_ID ends with).')
param searchConnectionName string = 'hbl-ops-search'
param appInsightsConnectionName string = 'hbl-ops-appinsights'

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName

  resource project 'projects' existing = {
    name: foundryProjectName
  }
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: foundry::project
  name: searchConnectionName
  properties: {
    category: 'CognitiveSearch'
    target: searchEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchServiceId
      location: searchLocation
    }
  }
}

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: foundry::project
  name: appInsightsConnectionName
  properties: {
    category: 'AppInsights'
    target: appInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: appInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsightsId
    }
  }
}

output searchConnectionId string = searchConnection.id
output searchConnectionName string = searchConnection.name
output appInsightsConnectionName string = appInsightsConnection.name
