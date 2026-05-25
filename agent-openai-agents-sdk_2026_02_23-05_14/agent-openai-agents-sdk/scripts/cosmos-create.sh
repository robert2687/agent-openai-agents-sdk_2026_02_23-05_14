#!/usr/bin/env bash
set -euo pipefail

: "${COSMOS_ACCOUNT:?COSMOS_ACCOUNT is required}"
: "${COSMOS_RG:?COSMOS_RG is required}"
: "${COSMOS_DB:?COSMOS_DB is required}"
: "${COSMOS_CONTAINER:?COSMOS_CONTAINER is required}"

az cosmosdb create \
  --name "$COSMOS_ACCOUNT" \
  --resource-group "$COSMOS_RG" \
  --kind GlobalDocumentDB

az cosmosdb sql database create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$COSMOS_RG" \
  --name "$COSMOS_DB"

az cosmosdb sql container create \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$COSMOS_RG" \
  --database-name "$COSMOS_DB" \
  --name "$COSMOS_CONTAINER" \
  --partition-key-path "/id"

echo "✅ Cosmos DB created."
