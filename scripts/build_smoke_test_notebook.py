"""
build_smoke_test_notebook.py

Generates the smoke-test Colab notebook for the Telecom Ops Copilot project.

Why generate it from code instead of hand-writing the .ipynb JSON: it is
easier to read, edit, and version-control. If we want to add or reorder
cells, we change Python here and re-run, instead of hand-editing JSON.
"""

import json
from pathlib import Path


def md(*lines):
    """Helper to build a markdown cell from a sequence of lines."""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": list(lines),
    }


def code(*lines):
    """Helper to build a code cell from a sequence of lines."""
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": list(lines),
    }


# ------------------------------------------------------------------
# Build the cells
# ------------------------------------------------------------------

cells = []

cells.append(md(
    "# Telecom Ops Copilot - Smoke Test\n",
    "\n",
    "This notebook validates three things before we start building the agent:\n",
    "\n",
    "1. Your Azure OpenAI deployment is reachable from Colab\n",
    "2. Colab can fetch KB documents from your GitHub repo\n",
    "3. The model can produce a grounded answer using a KB document as context\n",
    "\n",
    "Run the cells top to bottom. If something fails, the error message tells you what to fix.\n",
    "\n",
    "This is intentionally simple. The full agent will use Azure AI Foundry Agent Service with a state machine. This notebook just proves the pieces work.\n",
))

cells.append(md(
    "## Step 0: Install packages\n",
    "\n",
    "We install the OpenAI Python SDK (which also supports Azure OpenAI) and the requests library to fetch files from GitHub.\n",
))

cells.append(code(
    "# In Colab, this only needs to run once per session.\n",
    "# The --quiet flag hides the install output to keep things readable.\n",
    "!pip install \"openai>=1.50.0\" requests --quiet\n",
    "print(\"Packages installed.\")\n",
))

cells.append(md(
    "## Step 1: Load Azure OpenAI credentials from Colab Secrets\n",
    "\n",
    "Colab has a built-in secrets manager. This way your API keys do not end up saved in the notebook file or in GitHub.\n",
    "\n",
    "**How to set this up (one time):**\n",
    "\n",
    "1. Click the key icon in the left sidebar of Colab (it looks like a small key)\n",
    "2. Click 'Add new secret'\n",
    "3. Add three secrets with these exact names:\n",
    "    - `AZURE_OPENAI_ENDPOINT` - your endpoint URL (looks like `https://your-resource.openai.azure.com`)\n",
    "    - `AZURE_OPENAI_API_KEY` - your API key\n",
    "    - `AZURE_OPENAI_DEPLOYMENT` - your deployment name (for example `gpt-4o-mini`)\n",
    "4. For each secret, toggle the 'Notebook access' switch on\n",
    "\n",
    "The cell below reads them. It only prints whether they loaded, not the values.\n",
))

cells.append(code(
    "from google.colab import userdata\n",
    "\n",
    "AZURE_OPENAI_ENDPOINT   = userdata.get('AZURE_OPENAI_ENDPOINT')\n",
    "AZURE_OPENAI_API_KEY    = userdata.get('AZURE_OPENAI_API_KEY')\n",
    "AZURE_OPENAI_DEPLOYMENT = userdata.get('AZURE_OPENAI_DEPLOYMENT')\n",
    "\n",
    "# Confirm they loaded. We do NOT print the key itself, only whether it exists.\n",
    "print(f\"Endpoint loaded:   {bool(AZURE_OPENAI_ENDPOINT)}\")\n",
    "print(f\"API key loaded:    {bool(AZURE_OPENAI_API_KEY)}\")\n",
    "print(f\"Deployment loaded: {bool(AZURE_OPENAI_DEPLOYMENT)}\")\n",
    "\n",
    "if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT]):\n",
    "    raise ValueError(\"One or more secrets are missing. Check the Secrets panel in Colab.\")\n",
))

cells.append(md(
    "## Step 2: Test the Azure OpenAI connection\n",
    "\n",
    "Create a client and send a tiny hello-world chat. If this works, your Azure OpenAI is reachable from Colab.\n",
))

cells.append(code(
    "from openai import AzureOpenAI\n",
    "\n",
    "# Build the client. The api_version string is the Azure OpenAI API version,\n",
    "# not the model version. If you get a 404 about the API version, try\n",
    "# changing it to a newer one like '2024-10-21'.\n",
    "client = AzureOpenAI(\n",
    "    azure_endpoint = AZURE_OPENAI_ENDPOINT,\n",
    "    api_key        = AZURE_OPENAI_API_KEY,\n",
    "    api_version    = \"2024-08-01-preview\",\n",
    ")\n",
    "\n",
    "# Send a very small test message\n",
    "response = client.chat.completions.create(\n",
    "    model = AZURE_OPENAI_DEPLOYMENT,\n",
    "    messages = [\n",
    "        {\"role\": \"system\", \"content\": \"You are a helpful assistant.\"},\n",
    "        {\"role\": \"user\",   \"content\": \"Say hello in 5 words or less.\"},\n",
    "    ],\n",
    "    max_tokens = 50,\n",
    ")\n",
    "\n",
    "print(\"Model said:\", response.choices[0].message.content)\n",
))

cells.append(md(
    "## Step 3: Load a KB file from your GitHub repo\n",
    "\n",
    "We will fetch one of the markdown files you uploaded to your repo. This proves the agent can read its knowledge base content.\n",
    "\n",
    "**The URL pattern for a public GitHub raw file is:**\n",
    "\n",
    "```\n",
    "https://raw.githubusercontent.com/{username}/{repo}/{branch}/{path}\n",
    "```\n",
    "\n",
    "Change the values below to match your own repo and username. If your repo is private, we need a different approach (a personal access token) - tell me and we will fix.\n",
))

cells.append(code(
    "import requests\n",
    "\n",
    "# Change these to match your repo:\n",
    "GITHUB_USER = \"Git-Hub-Ran\"\n",
    "GITHUB_REPO = \"telecom-ops-copilot\"\n",
    "GITHUB_BRANCH = \"Dev\"\n",
    "FILE_PATH = \"kb/plans/01-essential.md\"\n",
    "\n",
    "KB_URL = f\"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{FILE_PATH}\"\n",
    "print(\"Fetching:\", KB_URL)\n",
    "\n",
    "response = requests.get(KB_URL)\n",
    "\n",
    "if response.status_code == 200:\n",
    "    essential_plan_doc = response.text\n",
    "    print(f\"Loaded {len(essential_plan_doc)} characters from KB.\\n\")\n",
    "    print(\"First 500 characters of the document:\")\n",
    "    print(\"-\" * 50)\n",
    "    print(essential_plan_doc[:500])\n",
    "else:\n",
    "    print(f\"Failed to load. HTTP status code: {response.status_code}\")\n",
    "    print(\"\")\n",
    "    print(\"Common reasons:\")\n",
    "    print(\"  404 - the file path is wrong or the branch name is wrong\")\n",
    "    print(\"  401 - the repo is private\")\n",
    "    print(\"  403 - rate limited (rare for a single request)\")\n",
))

cells.append(md(
    "## Step 4: End-to-end grounded answer\n",
    "\n",
    "Now we combine the two pieces. We pass the KB document to the model as context and ask a customer-style question. The model should answer using only what is in the document.\n",
    "\n",
    "This is a tiny preview of what the full agent will do. The real version will retrieve the right document first (instead of always using the same one), call tools for customer data, and follow a state machine. But the grounded-answer pattern is the foundation.\n",
))

cells.append(code(
    "# A customer-style question that should be answerable from the Essential plan doc\n",
    "question = \"How much data does the Essential plan include and what happens when I go over?\"\n",
    "\n",
    "# Build the prompt. The system message tells the model:\n",
    "#   - who it is (a customer service agent)\n",
    "#   - what it can use (only the document below)\n",
    "#   - what to do if the answer is not in the document (say so)\n",
    "#   - how long the answer should be\n",
    "messages = [\n",
    "    {\n",
    "        \"role\": \"system\",\n",
    "        \"content\": (\n",
    "            \"You are a helpful customer service agent for TelSano, a telecom company. \"\n",
    "            \"Answer the customer's question using ONLY the policy document below. \"\n",
    "            \"If the answer is not in the document, say you do not know. \"\n",
    "            \"Keep the answer under 80 words.\\n\\n\"\n",
    "            f\"Document:\\n{essential_plan_doc}\"\n",
    "        ),\n",
    "    },\n",
    "    {\"role\": \"user\", \"content\": question},\n",
    "]\n",
    "\n",
    "response = client.chat.completions.create(\n",
    "    model = AZURE_OPENAI_DEPLOYMENT,\n",
    "    messages = messages,\n",
    "    max_tokens = 200,\n",
    ")\n",
    "\n",
    "print(\"Customer question:\")\n",
    "print(question)\n",
    "print(\"\")\n",
    "print(\"Agent answer:\")\n",
    "print(response.choices[0].message.content)\n",
))

cells.append(md(
    "## Step 5: Try a question that is NOT in the KB\n",
    "\n",
    "A well-behaved agent should refuse to make things up. Let's verify by asking something the document does not cover.\n",
))

cells.append(code(
    "question = \"Can I use my Essential plan to make calls to Japan?\"\n",
    "\n",
    "messages = [\n",
    "    {\n",
    "        \"role\": \"system\",\n",
    "        \"content\": (\n",
    "            \"You are a helpful customer service agent for TelSano, a telecom company. \"\n",
    "            \"Answer the customer's question using ONLY the policy document below. \"\n",
    "            \"If the answer is not in the document, say you do not know and suggest the customer contact support. \"\n",
    "            \"Keep the answer under 80 words.\\n\\n\"\n",
    "            f\"Document:\\n{essential_plan_doc}\"\n",
    "        ),\n",
    "    },\n",
    "    {\"role\": \"user\", \"content\": question},\n",
    "]\n",
    "\n",
    "response = client.chat.completions.create(\n",
    "    model = AZURE_OPENAI_DEPLOYMENT,\n",
    "    messages = messages,\n",
    "    max_tokens = 200,\n",
    ")\n",
    "\n",
    "print(\"Customer question:\")\n",
    "print(question)\n",
    "print(\"\")\n",
    "print(\"Agent answer:\")\n",
    "print(response.choices[0].message.content)\n",
    "\n",
    "# Expected behavior: the agent says it does not know and suggests contacting support.\n",
    "# If the agent makes up an answer (hallucinates), that is a problem we need to fix\n",
    "# in the prompt or in retrieval, before going to production.\n",
))

cells.append(md(
    "## What this notebook proved\n",
    "\n",
    "If all the cells above ran without errors:\n",
    "\n",
    "- Azure OpenAI is reachable from Colab\n",
    "- Your KB files in GitHub can be fetched on demand\n",
    "- The model can answer grounded questions and (hopefully) decline ungrounded ones\n",
    "\n",
    "## What comes next (after mentor approves the updated plan)\n",
    "\n",
    "1. Set up Azure AI Foundry Agent Service (a Foundry project + an agent definition)\n",
    "2. Migrate the grounded-chat pattern into a Foundry agent with file search\n",
    "3. Define tools as Azure Functions (get_customer_account, get_billing_info, etc.)\n",
    "4. Build the state machine orchestrator (classify, route, act, escalate, respond) using Microsoft Agent Framework\n",
    "5. Build the golden test set with adversarial cases\n",
    "6. Run evaluation: intent accuracy, tool selection correctness, escalation precision and recall, grounding faithfulness\n",
    "\n",
    "## Saving your work\n",
    "\n",
    "When the notebook runs end to end, save it via File > Save a copy in GitHub. Save it to your `telecom-ops-copilot` repo, **Dev branch**, into a new `notebooks/` folder. Commit message: `Add environment smoke test notebook`.\n",
))


# ------------------------------------------------------------------
# Assemble and save the notebook
# ------------------------------------------------------------------

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
        },
        "colab": {
            "provenance": [],
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main():
    output_path = Path(__file__).resolve().parent.parent / "notebooks" / "01-smoke-test.ipynb"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(notebook, f, indent=1)

    print(f"Wrote notebook: {output_path}")
    print(f"Cells: {len(cells)}")


if __name__ == "__main__":
    main()
