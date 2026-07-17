# Azure Boards API notes

The helper uses Azure CLI's bundled Azure DevOps SDK and local authentication; it never reads or prints a PAT.

- Work item create location: `62d3d110-0047-428c-ad3c-4fe872c91c74`
- Work item read/update location: `72c7ddf8-2cdc-4f60-90cd-ab71c14a399b`
- Comment location: `608aac0a-32e1-4493-a863-b9cf4566d257`
- Comments API: `7.1-preview.4`

Descriptions set `/multilineFieldsFormat/System.Description` to `markdown` in the same JSON Patch as `System.Description`. Updates include a `/rev` test for optimistic concurrency. Mutations validate first and persisted writes are read back.

Native relation mapping:

| CLI kind | Azure relation | Meaning |
|---|---|---|
| `parent` | `System.LinkTypes.Hierarchy-Reverse` | Target is parent of current item |
| `predecessor` | `System.LinkTypes.Dependency-Reverse` | Target blocks current item |
| `related` | `System.LinkTypes.Related` | Symmetric related item |
