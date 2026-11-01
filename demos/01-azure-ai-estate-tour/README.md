# Module 1 · The estate is ordinary Azure

**Layer:** Foundation. **Point:** AI resources are ARM resources; model choice is a region choice; the guardrails already exist.

`tour.sh` walks the AI estate from the control plane in about two minutes:

| Step | Command | What it shows |
|---|---|---|
| 1 | `az account list-locations` filtered to Australia and New Zealand | One control plane, both regions with three zones |
| 2 | `az provider show -n Microsoft.CognitiveServices` | The resource provider behind Foundry and its resource types |
| 3 | `az cognitiveservices model list -l australiaeast` | The model catalogue and the SKU per model (the residency menu) |
| 4 | the same for `newzealandnorth` | Zero: data can rest there, inference cannot, today |
| 5 | `az cognitiveservices usage list` | Quota is per subscription, per region, per model |
| 6 | `az policy definition list` filtered to AI services | Built-in guardrails to assign |
| 7 | `az resource list` for AI accounts, search services and gateways | What already exists in the subscription |

```bash
./tour.sh                     # live, pauses between steps
DEMO_NO_PAUSE=1 ./tour.sh     # straight through
DEMO_MODE=mock ./tour.sh      # offline: prints fallback/tour-output.txt
```

[estate-map.md](estate-map.md) is the one-page map of Azure's AI estate by layer, with the Harbourline lens. The
Cloud Adoption Framework now calls the environment an AI workload lands in a **workload landing zone** (October 2026)
and says AI needs no separate landing zone design; the [Azure/AI-Landing-Zones](https://github.com/Azure/AI-Landing-Zones)
reference implementation (Bicep, Terraform, preview) is the accelerator for it.
