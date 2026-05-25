#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Installing Azure Cosmos DB CLI extension..."
az extension add --name cosmosdb-preview --yes || az extension update --name cosmosdb-preview

echo "🔧 Creating default Cosmos DB environment variables..."
if ! grep -q "# Cosmos DB defaults" ~/.bashrc 2>/dev/null; then
cat <<'EOF' >> ~/.bashrc

# Cosmos DB defaults
export COSMOS_ACCOUNT=""
export COSMOS_RG=""
export COSMOS_DB="grantsystem"
export COSMOS_CONTAINER="documents"
EOF
fi

echo "✅ Cosmos DB environment prepared."
