#!/bin/bash
# Quick Start Setup Script for local/OpenAI and optional Databricks modes

set -e

echo "========================================"
echo "Databricks Agent Quick Start Setup"
echo "========================================"
echo ""

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to the agent directory
cd "$(dirname "$0")"

BACKEND="${AGENT_BACKEND:-openai}"

echo "Step 1: Checking prerequisites..."
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}✗ uv is not installed${NC}"
    echo "Install uv from: https://docs.astral.sh/uv/getting-started/installation/"
    echo "Quick install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
else
    echo -e "${GREEN}✓ uv is installed${NC}"
fi

if [ "$BACKEND" = "databricks" ]; then
    if ! command -v databricks &> /dev/null; then
        echo -e "${RED}✗ Databricks CLI is not installed${NC}"
        echo "Install from: https://docs.databricks.com/dev-tools/cli/install.html"
        exit 1
    else
        echo -e "${GREEN}✓ Databricks CLI is installed${NC}"
    fi
else
    echo -e "${GREEN}✓ Databricks CLI not required for OpenAI mode${NC}"
fi

# Check for nvm/node
if [ "$BACKEND" = "databricks" ] && ! command -v node &> /dev/null; then
    echo -e "${YELLOW}⚠ Node.js not found. Installing via nvm...${NC}"
    if ! command -v nvm &> /dev/null; then
        echo "Installing nvm..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    nvm install 20
    nvm use 20
else
    if command -v node &> /dev/null; then
        echo -e "${GREEN}✓ Node.js is installed${NC}"
    else
        echo -e "${GREEN}✓ Node.js is optional in OpenAI mode${NC}"
    fi
fi

if [ "$BACKEND" = "openai" ]; then
    echo ""
    echo "Step 2: Configuring local/OpenAI mode..."
    echo ""

    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        cp .env.example .env
    fi

    if ! grep -q '^AGENT_BACKEND=' .env 2>/dev/null; then
        echo 'AGENT_BACKEND=openai' >> .env
    else
        sed -i 's/^AGENT_BACKEND=.*/AGENT_BACKEND=openai/' .env
    fi

    if ! grep -q '^MLFLOW_TRACKING_URI=' .env 2>/dev/null; then
        echo 'MLFLOW_TRACKING_URI=sqlite:///mlflow.db' >> .env
    else
        sed -i 's|^MLFLOW_TRACKING_URI=.*|MLFLOW_TRACKING_URI=sqlite:///mlflow.db|' .env
    fi

    echo -e "${GREEN}✓ OpenAI mode configured${NC}"
    echo ""
    echo "Step 3: Installing dependencies..."
    echo ""
    uv sync
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo ""
    echo "========================================"
    echo "Setup Complete!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "  1. Add OPENAI_API_KEY to .env"
    echo -e "  2. ${GREEN}uv run verify-setup${NC}"
    echo -e "  3. ${GREEN}uv run start-server --reload${NC}"
    exit 0
fi

echo ""
echo "Step 2: Setting up Databricks authentication..."
echo ""

# Check if already authenticated
if databricks current-user me &> /dev/null; then
    echo -e "${GREEN}✓ Already authenticated with Databricks${NC}"
    DATABRICKS_USERNAME=$(databricks current-user me | grep -o '"userName":"[^"]*' | cut -d'"' -f4)
    echo "  Logged in as: $DATABRICKS_USERNAME"
else
    echo "Authenticating with Databricks..."
    echo "This will open a browser window for OAuth authentication."
    databricks auth login

    if databricks current-user me &> /dev/null; then
        echo -e "${GREEN}✓ Authentication successful${NC}"
        DATABRICKS_USERNAME=$(databricks current-user me | grep -o '"userName":"[^"]*' | cut -d'"' -f4)
    else
        echo -e "${RED}✗ Authentication failed${NC}"
        exit 1
    fi
fi

echo ""
echo "Step 3: Creating MLflow experiment..."
echo ""

# Create MLflow experiment
EXPERIMENT_NAME="/Users/$DATABRICKS_USERNAME/agents-on-apps"
EXPERIMENT_OUTPUT=$(databricks experiments create-experiment "$EXPERIMENT_NAME" 2>&1 || true)

if echo "$EXPERIMENT_OUTPUT" | grep -q "RESOURCE_ALREADY_EXISTS"; then
    echo -e "${YELLOW}⚠ Experiment already exists, retrieving ID...${NC}"
    EXPERIMENT_ID=$(databricks experiments search --max-results 1000 | grep -A 5 "\"name\": \"$EXPERIMENT_NAME\"" | grep "experiment_id" | grep -o '[0-9]*' | head -1)
else
    EXPERIMENT_ID=$(echo "$EXPERIMENT_OUTPUT" | grep -o '"experiment_id":"[^"]*' | cut -d'"' -f4)
fi

if [ -z "$EXPERIMENT_ID" ]; then
    echo -e "${RED}✗ Failed to create or find experiment${NC}"
    exit 1
fi

echo -e "${GREEN}✓ MLflow experiment created/found${NC}"
echo "  Experiment ID: $EXPERIMENT_ID"
echo "  Experiment Name: $EXPERIMENT_NAME"

echo ""
echo "Step 4: Updating .env file..."
echo ""

# Update .env file with experiment ID
if [ -f ".env" ]; then
    # Update existing .env
    sed -i "s/^MLFLOW_EXPERIMENT_ID=.*/MLFLOW_EXPERIMENT_ID=$EXPERIMENT_ID/" .env
    echo -e "${GREEN}✓ Updated .env file with experiment ID${NC}"
else
    echo -e "${RED}✗ .env file not found${NC}"
    exit 1
fi

echo ""
echo "Step 5: Installing dependencies..."
echo ""

uv sync
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Your agent is now ready to run. Start it with:"
echo ""
echo -e "  ${GREEN}uv run start-app${NC}"
echo ""
echo "This will start:"
echo "  • Agent server at http://localhost:8000/invocations"
echo "  • Chat UI at http://localhost:3000"
echo ""
echo "To view traces and logs, visit your MLflow experiment:"
echo "  $EXPERIMENT_NAME"
echo ""
