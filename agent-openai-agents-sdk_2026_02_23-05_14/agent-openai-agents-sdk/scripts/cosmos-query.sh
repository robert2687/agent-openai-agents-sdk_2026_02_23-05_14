#!/usr/bin/env bash
set -euo pipefail

: "${COSMOS_ACCOUNT:?COSMOS_ACCOUNT is required}"
: "${COSMOS_RG:?COSMOS_RG is required}"
: "${COSMOS_DB:?COSMOS_DB is required}"
: "${COSMOS_CONTAINER:?COSMOS_CONTAINER is required}"

QUERY="${1:-}"
if [[ -z "$QUERY" ]]; then
  echo "Usage: $0 \"SELECT * FROM c\"" >&2
  exit 1
fi

az cosmosdb sql query \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$COSMOS_RG" \
  --database-name "$COSMOS_DB" \
  --container-name "$COSMOS_CONTAINER" \
  --query "$QUERY"
