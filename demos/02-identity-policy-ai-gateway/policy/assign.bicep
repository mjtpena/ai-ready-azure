// Stand-alone entry point to create the guardrail definitions and assign them to a resource group,
// without the rest of the demo stack. Same module main.bicep uses.
//   az deployment group create -g rg-hbl-ops --template-file policy/assign.bicep
targetScope = 'resourceGroup'

param allowedLocations array = [ 'australiaeast', 'newzealandnorth' ]
param allowedModels array = [ 'gpt-5-mini', 'gpt-5', 'gpt-5.1', 'gpt-5.2', 'gpt-4.1', 'gpt-4.1-mini', 'text-embedding-3-small', 'text-embedding-3-large' ]
param deployModelAllowList bool = true

@allowed([ 'Audit', 'Deny', 'Disabled' ])
param publicNetworkEffect string = 'Audit'

module guardrails '../infra/modules/policy.bicep' = {
  name: 'hbl-ops-policy-standalone'
  params: {
    allowedLocations: allowedLocations
    allowedModels: allowedModels
    deployModelAllowList: deployModelAllowList
    publicNetworkEffect: publicNetworkEffect
  }
}

output assignmentNames array = guardrails.outputs.assignmentNames
