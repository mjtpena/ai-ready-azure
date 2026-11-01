# Security

Nothing in this repository is a secret, and nothing in it should become one: every script authenticates with Entra ID
through `DefaultAzureCredential`, the Foundry and AI Search resources are deployed with key-based authentication
disabled, and `deploy.sh` writes the only generated value (an API Management subscription key, which identifies a team,
not a person) to a git-ignored `.env`.

If you find a credential, a live tenant or subscription identifier, or personal data anywhere in the history, please open
a private security advisory on the repository rather than a public issue.
