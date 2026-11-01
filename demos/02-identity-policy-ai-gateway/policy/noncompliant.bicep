// DELIBERATELY NON-COMPLIANT. This deployment is meant to FAIL with RequestDisallowedByPolicy.
// It breaks two guardrails at once: the region (eastus is not NZ/AU) and key-based auth (disableLocalAuth=false).
//   az deployment group create -g rg-hbl-ops --template-file policy/noncompliant.bicep
// Nothing is created when Azure Policy denies the request; the error lists every assignment that fired.
targetScope = 'resourceGroup'

@description('Outside the approved regions on purpose.')
param location string = 'eastus'

param name string = 'aif-hbl-ops-shadow-${uniqueString(resourceGroup().id)}'

resource shadowAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    allowProjectManagement: true
    // Keys enabled: the "I will just put the key in the app settings" shortcut.
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

output endpoint string = shadowAccount.properties.endpoint
