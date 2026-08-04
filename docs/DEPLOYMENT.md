# Deployment Guide

## Prerequisites

- Python 3.12 or later
- An Azure subscription with access to Azure AI Foundry
- A Foundry project with:
  - A vector store containing the KB documents (for file_search)
  - Outbound internet access from the machine running the app (for Device Code auth)

---

## 1. Clone and install

```bash
git clone https://github.com/Git-Hub-Ran/telecom-ops-copilot.git
cd telecom-ops-copilot
pip install -r requirements.txt
```

---

## 2. Azure setup: finding the three required values

**AZURE_FOUNDRY_PROJECT_ENDPOINT**

Open the Azure AI Foundry portal. Navigate to your project. The endpoint URL
appears under **Project details** and has the form:

```
https://<hub-name>.api.azureml.ms/...
```

Copy the full URL including the project path segment.

**AZURE_TENANT_ID**

In the Azure portal, navigate to **Microsoft Entra ID > Overview**. The
**Tenant ID** is shown on that page. It is a UUID of the form
`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

**VECTOR_STORE_ID**

In the Foundry portal, navigate to **Storage > Vector stores** inside your
project. Copy the ID of the vector store that holds the KB documents. It
begins with `vs_`.

---

## 3. .env file setup

Create a `.env` file in the project root:

```
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://<hub-name>.api.azureml.ms/...
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VECTOR_STORE_ID=vs_...
```

All other settings have defaults and do not need to be set for a standard
deployment. Optional overrides:

```
# Model assignments (defaults shown)
CLASSIFIER_MODEL=gpt-4o-mini
ACT_MODEL=gpt-4o
ESCALATE_MODEL=gpt-4o
RESPOND_MODEL=gpt-4o

# Routing thresholds
CLASSIFICATION_CONFIDENCE_THRESHOLD=0.6
MAX_CONVERSATION_TURNS=10

# Billing data source (default: json)
BILLING_DATA_SOURCE=json
BILLING_DB_PATH=data/billing.db
```

---

## 4. First run and Device Code auth

On first startup, the app authenticates using Azure Device Code flow.

```bash
streamlit run src/ui/app.py
```

The terminal prints a message like:

```
To sign in, use a web browser to open the page https://login.microsoft.com/device
and enter the code XXXXXXXX to authenticate.
```

Open the URL in a browser, enter the code, and sign in with the Azure account
that has access to the Foundry project. Authentication is cached for the
session; re-authentication is required after a restart.

On first startup, **AgentFactory** creates the four Foundry agents
automatically using get-or-create semantics (it lists agents by name and
creates only those that are absent). This takes approximately 10-30 seconds
and is a one-time cost per Foundry project.

Agent names created:
- `classifier-agent`
- `act-agent`
- `escalate-agent`
- `respond-agent`

---

## 5. Running the app

```bash
streamlit run src/ui/app.py
```

The Streamlit UI opens at `http://localhost:8501`. Type a customer query in
the chat box and press Enter. The pipeline runs through ClassifyState,
RouteState, ActState (if applicable), EscalateState (if applicable), and
RespondState, then displays the agent's reply.

---

## 6. SQLite billing database (optional)

By default, `get_billing_info` reads from `mock-data/billing.json`. To use
the SQLite backend instead:

**Step 1:** Seed the database from the JSON fixture:

```bash
python scripts/setup_billing_db.py
```

This creates `data/billing.db` with 48 bill records. The script is idempotent
and safe to run multiple times.

**Step 2:** Add to `.env`:

```
BILLING_DATA_SOURCE=sqlite
```

Restart the app. `get_billing_info` will now query `data/billing.db` instead
of reading the JSON file.

To switch back to JSON, remove `BILLING_DATA_SOURCE` from `.env` or set it
to `json`.

---

## 7. Running tests

No Azure credentials are required. All 330 tests use mocks or local fixtures.

```bash
pytest tests/
```

To run a specific module:

```bash
pytest tests/data/
pytest tests/test_tools_billing.py
```

---

## 8. Updating agent prompts

Foundry agents are retrieved by name on startup and reused if they exist.
Changing a system prompt in `src/orchestrator/agents/prompts.py` has no effect
until the corresponding Foundry agent is deleted and recreated.

To apply a prompt update:

1. Edit the prompt in `src/orchestrator/agents/prompts.py`.
2. In the Foundry portal, delete the agent by name (e.g. `classifier-agent`).
3. Restart the app. AgentFactory recreates the agent with the updated prompt.

---

## 9. Model deprecation

`gpt-4o` and `gpt-4o-mini` retire **October 1 2026**. Before that date,
update the model deployment names in `.env`:

```
CLASSIFIER_MODEL=<replacement-model-deployment-name>
ACT_MODEL=<replacement-model-deployment-name>
ESCALATE_MODEL=<replacement-model-deployment-name>
RESPOND_MODEL=<replacement-model-deployment-name>
```

The values must match the deployment names in your Azure OpenAI resource, not
the base model names. Check the Azure OpenAI portal for available deployments.
