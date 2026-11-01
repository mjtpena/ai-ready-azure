// DELIBERATELY NON-COMPLIANT (second example). Tries to deploy a model that is not on the approved list
// onto the existing, compliant Foundry account. Expected result: RequestDisallowedByPolicy from
// hbl-ops-allowed-model-deployments.
//   az deployment group create -g rg-hbl-ops --template-file policy/noncompliant-model.bicep \
//     --parameters accountName=$FOUNDRY_ACCOUNT_NAME
// If the model allow-list policy was not deployed (alias unavailable), this WILL succeed and create a real
// deployment: remove it with `az cognitiveservices account deployment delete`.
targetScope = 'resourceGroup'

@description('The compliant Foundry account created by infra/main.bicep.')
param accountName string

@description('A model that is not on the Harbourline approved list.')
param modelName string = 'gpt-35-turbo'
param modelVersion string = '0125'

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: accountName
}

resource unapprovedModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'unapproved-${modelName}'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}
