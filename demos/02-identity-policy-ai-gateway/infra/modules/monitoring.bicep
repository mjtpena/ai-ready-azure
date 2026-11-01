// Observability for the gateway: Log Analytics + Application Insights, the APIM App Insights logger with
// LLM (prompt/completion) logging, Azure Monitor diagnostics with the GatewayLlmLogs category, and the
// request headers (x-team, x-site-group) captured in gateway logs for the KQL queries in ../../kql.

param location string
param workspaceName string
param appInsightsName string

@description('Existing APIM service in this resource group to attach loggers and diagnostics to.')
param apimName string

@description('Retention for course logs. Keep short; this is a demo.')
@minValue(30)
param retentionInDays int = 30

param tags object = {}

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
  }
}

resource apim 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

// App Insights logger: destination for request telemetry and for llm-emit-token-metric custom metrics.
resource appInsightsLogger 'Microsoft.ApiManagement/service/loggers@2024-05-01' = {
  parent: apim
  name: 'appinsights'
  properties: {
    loggerType: 'applicationInsights'
    description: 'Application Insights for the Harbourline AI gateway'
    credentials: {
      connectionString: appInsights.properties.ConnectionString
    }
    isBuffered: true
    resourceId: appInsights.id
  }
}

// Service-level App Insights diagnostics. 2024-06-01-preview is the first version with largeLanguageModel
// (prompt/completion logging); 2024-05-01 GA does not have it.
resource appInsightsDiagnostics 'Microsoft.ApiManagement/service/diagnostics@2024-06-01-preview' = {
  parent: apim
  name: 'applicationinsights'
  properties: {
    loggerId: appInsightsLogger.id
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'W3C'
    logClientIp: true
    verbosity: 'information'
    metrics: true
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: {
        headers: [ 'x-team', 'x-site-group' ]
        body: { bytes: 0 }
      }
      response: {
        headers: [ 'x-remaining-tokens', 'x-consumed-tokens', 'Retry-After' ]
        body: { bytes: 0 }
      }
    }
    largeLanguageModel: {
      logs: 'enabled'
      requests: {
        messages: 'all'
        maxSizeInBytes: 32768
      }
      responses: {
        messages: 'all'
        maxSizeInBytes: 32768
      }
    }
  }
}

// Azure Monitor diagnostics (the built-in "azuremonitor" logger) so GatewayLogs and GatewayLlmLogs reach
// Log Analytics with the same headers and LLM payload settings.
resource azureMonitorDiagnostics 'Microsoft.ApiManagement/service/diagnostics@2024-06-01-preview' = {
  parent: apim
  name: 'azuremonitor'
  properties: {
    loggerId: '${apim.id}/loggers/azuremonitor'
    alwaysLog: 'allErrors'
    logClientIp: true
    verbosity: 'information'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: {
        headers: [ 'x-team', 'x-site-group' ]
        body: { bytes: 0 }
      }
      response: {
        headers: [ 'x-remaining-tokens', 'x-consumed-tokens', 'Retry-After' ]
        body: { bytes: 0 }
      }
    }
    largeLanguageModel: {
      logs: 'enabled'
      requests: {
        messages: 'all'
        maxSizeInBytes: 32768
      }
      responses: {
        messages: 'all'
        maxSizeInBytes: 32768
      }
    }
  }
}

resource apimDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'to-log-analytics'
  scope: apim
  properties: {
    workspaceId: workspace.id
    // Resource-specific tables (ApiManagementGatewayLogs, ApiManagementGatewayLlmLog) instead of the legacy
    // AzureDiagnostics table; the KQL in ../../kql assumes them. without this, rows land in AzureDiagnostics.
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        category: 'GatewayLogs'
        enabled: true
      }
      {
        // Generative AI gateway logs (prompts, completions, token counts) -> ApiManagementGatewayLlmLog table. verify category name
        category: 'GatewayLlmLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output workspaceId string = workspace.id
output workspaceName string = workspace.name
output workspaceCustomerId string = workspace.properties.customerId
output appInsightsId string = appInsights.id
output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
