#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# VoC Engine — Azure Infrastructure Provisioning
#
# Usage:
#   export AZURE_SUBSCRIPTION_ID=<your-subscription-id>
#   bash infra/provision.sh
#
# What this creates (all in region af-south-1 / South Africa North):
#   - Resource group:     rg-voc-engine-staging
#   - Container Registry: vocengineacr  (Basic SKU)
#   - PostgreSQL:         voc-pg-staging (Flexible Server, Burstable B1ms)
#   - Redis Cache:        voc-redis-staging (Basic C0)
#
# After running, copy the printed env var block into your .env file.
# Store all secrets in Azure Key Vault or GitHub Actions Secrets — not in .env.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

LOCATION="southafricanorth"
RG="rg-voc-engine-staging"
ACR_NAME="vocengineacr"
PG_SERVER="voc-pg-staging"
PG_DB="voc_engine"
PG_USER="voc"
REDIS_NAME="voc-redis-staging"

# ── Prompt for secrets that must not be hardcoded ────────────────────────────
read -rsp "PostgreSQL admin password (min 8 chars, 1 upper, 1 digit): " PG_PASSWORD
echo
read -rsp "VOC_API_KEY (random string, e.g. openssl rand -hex 32): " VOC_API_KEY
echo

echo ""
echo "▶ Setting subscription: ${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# ── Resource Group ────────────────────────────────────────────────────────────
echo "▶ Creating resource group $RG ..."
az group create --name "$RG" --location "$LOCATION" --output none

# ── Azure Container Registry ─────────────────────────────────────────────────
echo "▶ Creating ACR $ACR_NAME ..."
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

ACR_URL=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# ── PostgreSQL Flexible Server ────────────────────────────────────────────────
echo "▶ Creating PostgreSQL Flexible Server $PG_SERVER ..."
az postgres flexible-server create \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --location "$LOCATION" \
  --admin-user "$PG_USER" \
  --admin-password "$PG_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 15 \
  --storage-size 32 \
  --public-access 0.0.0.0 \
  --output none

az postgres flexible-server db create \
  --resource-group "$RG" \
  --server-name "$PG_SERVER" \
  --database-name "$PG_DB" \
  --output none

PG_HOST="${PG_SERVER}.postgres.database.azure.com"

# ── Azure Cache for Redis ─────────────────────────────────────────────────────
echo "▶ Creating Redis Cache $REDIS_NAME ..."
az redis create \
  --resource-group "$RG" \
  --name "$REDIS_NAME" \
  --location "$LOCATION" \
  --sku Basic \
  --vm-size c0 \
  --output none

REDIS_HOST=$(az redis show --resource-group "$RG" --name "$REDIS_NAME" --query hostName -o tsv)
REDIS_KEY=$(az redis list-keys --resource-group "$RG" --name "$REDIS_NAME" --query primaryKey -o tsv)

# ── Storage Account for Blob ──────────────────────────────────────────────────
STORAGE_ACCOUNT="vocenginestorage"
echo "▶ Creating storage account $STORAGE_ACCOUNT ..."
az storage account create \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --output none

az storage container create \
  --account-name "$STORAGE_ACCOUNT" \
  --name "voc-engine" \
  --output none

STORAGE_CONN=$(az storage account show-connection-string \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --query connectionString -o tsv)

# ── Print env block ───────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Copy the block below into your .env file"
echo "  Store all of these in GitHub Actions Secrets as well."
echo "════════════════════════════════════════════════════════════"
cat <<EOF

# Azure Container Registry
AZURE_REGISTRY_URL=${ACR_URL}
AZURE_REGISTRY_USERNAME=${ACR_USERNAME}
AZURE_REGISTRY_PASSWORD=${ACR_PASSWORD}

# PostgreSQL
POSTGRES_HOST=${PG_HOST}
POSTGRES_DB=${PG_DB}
POSTGRES_USER=${PG_USER}
POSTGRES_PASSWORD=${PG_PASSWORD}
DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/${PG_DB}?sslmode=require

# Redis
REDIS_URL=${REDIS_HOST}:6380,password=${REDIS_KEY},ssl=True

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=${STORAGE_CONN}
AZURE_STORAGE_CONTAINER_NAME=voc-engine

# API Key
VOC_API_KEY=${VOC_API_KEY}

EOF
echo "════════════════════════════════════════════════════════════"
echo "Done. Resource group: $RG"
