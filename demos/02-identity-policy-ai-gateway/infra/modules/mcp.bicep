// Tools through the same front door: the Site APIs imported into API Management as the REST API site-ops-api
// (backed by the Functions app) and exported as the MCP server hbl-site-tools, both bound to the hbl-site-ai product.
// The Functions key lives in a named value the policies read; clients present an Entra token and a subscription key.
// MCP server resources use the 2025-09-01-preview API (type 'mcp' plus apis/tools children referencing REST operations).

param apimName string
param toolsAppName string
param toolsApiUrl string
param productName string = 'hbl-site-ai'
param mcpName string = 'hbl-site-tools'

resource apim 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

resource toolsApp 'Microsoft.Web/sites@2024-04-01' existing = {
  name: toolsAppName
}

resource product 'Microsoft.ApiManagement/service/products@2024-05-01' existing = {
  parent: apim
  name: productName
}

// The backend credential, held by the gateway only.
resource nvSiteApiKey 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = {
  parent: apim
  name: 'site-api-key'
  properties: {
    displayName: 'site-api-key'
    value: listKeys('${toolsApp.id}/host/default', '2024-04-01').functionKeys.default
    secret: true
  }
}

resource siteBackend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: apim
  name: 'site-api-backend'
  properties: {
    description: 'The Site APIs (Azure Functions). The key is added by the policy from the site-api-key named value.'
    protocol: 'http'
    url: toolsApiUrl
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

resource siteApi 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  parent: apim
  name: 'site-ops-api'
  properties: {
    displayName: 'Harbourline Site APIs'
    description: 'The four Site API tools behind the AI gateway: site summary, open work orders, incidents, inspections.'
    path: 'site'
    protocols: [ 'https' ]
    format: 'openapi'
    value: loadTextContent('../../apim/site-ops-openapi.yaml')
    serviceUrl: toolsApiUrl
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
  }
}

resource siteApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: siteApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../../apim/policies/site-api.xml')
  }
  dependsOn: [ nvSiteApiKey, siteBackend ]
}

resource siteApiProduct 'Microsoft.ApiManagement/service/products/apis@2024-05-01' = {
  parent: product
  name: siteApi.name
}

// ---- The MCP server: the same four operations, served as tools ----
var tools = [
  { name: 'get_site_summary', description: 'Summary for one site over the last 7 days: what needs attention, open work orders, faults, inspections, energy.' }
  { name: 'get_open_work_orders', description: 'Open work orders in a region (or ALL) for one system (or any) open for more than N hours.' }
  { name: 'get_incidents', description: 'Incidents over the last N days (1 to 14) for a region or ALL and a system or any.' }
  { name: 'get_inspection_schedule', description: 'Statutory certificate inspections due in a month for a site, a region or ALL, plus everything overdue.' }
]

#disable-next-line BCP036 BCP037
resource mcp 'Microsoft.ApiManagement/service/apis@2025-09-01-preview' = {
  parent: apim
  name: mcpName
  properties: {
    displayName: 'Harbourline site tools (MCP server)'
    description: 'The Site APIs as MCP tools, governed by the same gateway: Entra token, request budget per caller, metering.'
    type: 'mcp'
    path: 'site-tools'
    protocols: [ 'https' ]
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'api-key'
    }
  }
  dependsOn: [ siteApi ]
}

#disable-next-line BCP036 BCP037
resource mcpTools 'Microsoft.ApiManagement/service/apis/tools@2025-09-01-preview' = [for t in tools: {
  parent: mcp
  name: t.name
  properties: {
    displayName: t.name
    description: t.description
    operationId: resourceId('Microsoft.ApiManagement/service/apis/operations', apimName, siteApi.name, t.name)
  }
}]

resource mcpPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: mcp
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../../apim/policies/mcp-server.xml')
  }
  dependsOn: [ nvSiteApiKey, mcpTools ]
}

resource mcpProduct 'Microsoft.ApiManagement/service/products/apis@2024-05-01' = {
  parent: product
  name: mcp.name
}

output mcpUrl string = '${apim.properties.gatewayUrl}/site-tools/mcp'
output siteApiUrl string = '${apim.properties.gatewayUrl}/site'
