# Troubleshooting Guide

---

## 1. Authentication errors

### DeviceCodeCredential timeout

**Symptom:** The terminal prints the device code prompt but the app hangs or
raises `ClientAuthenticationError` after a minute or two.

**Cause:** The device code expires after approximately 15 minutes. If the
browser sign-in is not completed in time, the credential times out.

**Fix:** Restart the app and complete the browser sign-in within the time
limit. Navigate to `https://login.microsoft.com/device`, enter the code shown
in the terminal, and sign in before returning to the app.

---

### Wrong tenant ID

**Symptom:** `ClientAuthenticationError: AADSTS90002: Tenant not found`

**Cause:** `AZURE_TENANT_ID` in `.env` does not match the tenant that owns
the Foundry project.

**Fix:** In the Azure portal, navigate to **Microsoft Entra ID > Overview**
and copy the **Tenant ID** from that page. Update `.env` and restart.

---

### Expired token after idle period

**Symptom:** Requests succeed on first run but fail with
`ClientAuthenticationError` after the app has been idle for several hours.

**Cause:** The access token issued at startup has expired. `DeviceCodeCredential`
does not automatically re-prompt in the middle of a session.

**Fix:** Restart the app and re-authenticate.

---

## 2. AgentFactory errors

### Wrong endpoint URL

**Symptom:** `ServiceRequestError` or `HttpResponseError` on startup, often
with a connection refused or DNS resolution failure.

**Cause:** `AZURE_FOUNDRY_PROJECT_ENDPOINT` in `.env` is incorrect or
incomplete. The value must include the full project path segment, not just
the hub hostname.

**Fix:** In the Foundry portal, open your project, go to **Project details**,
and copy the full endpoint URL. It should look like:

```
https://<hub-name>.api.azureml.ms/agents/v1.0/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.MachineLearningServices/workspaces/<project>
```

---

### Agent not found on first startup

**Symptom:** `ResourceNotFoundError` when the pipeline tries to run the first
query, even though the app started without errors.

**Cause:** AgentFactory uses get-or-create semantics and creates agents
asynchronously on first use. If the Foundry project has strict quota limits
or the endpoint is slow, agent creation can fail silently during startup.

**Fix:** Check the terminal output during startup for any warnings from
AgentFactory. If agents were not created, restart the app; creation is
retried on startup. If the error persists, open the Foundry portal and
verify that the agents (`classifier-agent`, `act-agent`, `escalate-agent`,
`respond-agent`) exist under **My assets > Agents**.

---

### Stale agent after a prompt update

**Symptom:** The pipeline is running an old system prompt after you edited
`src/orchestrator/agents/prompts.py`.

**Cause:** Foundry agents are retrieved by name and reused if they exist.
The updated prompt is not applied until the agent is deleted and recreated.

**Fix:** In the Foundry portal, delete the relevant agent by name. On the
next startup, AgentFactory recreates it with the updated prompt.

---

## 3. JSON parsing errors from agents

### Empty response or unparseable output

**Symptom:** `JSONDecodeError` in the logs, or the pipeline falls through to
an error state with `data_invalid`.

**Cause:** The agent returned an empty message or a message that could not
be parsed as JSON. This happened frequently before the Phase 2.11 fix that
strips markdown code fences before parsing.

**What was fixed:** Prior to Phase 2.11, agents occasionally wrapped their
JSON output in triple-backtick fences (` ```json ... ``` `). The JSON parser
failed on the fence characters. The fix strips any leading/trailing code
fence before attempting to parse.

**If this recurs:** Check the structured logs for the raw `agent_response`
field on the failed turn. If the response contains markdown formatting, the
agent prompt may need to be updated to enforce JSON-only output. The
`ACT_SYSTEM_PROMPT` and `CLASSIFIER_SYSTEM_PROMPT` both include explicit
JSON-only enforcement instructions added in Phase 2.11.

---

## 4. SQLite billing database errors

### FileNotFoundError: data/billing.db

**Symptom:**

```
sqlite3.OperationalError: unable to open database file
```

or

```
FileNotFoundError: [Errno 2] No such file or directory: '.../data/billing.db'
```

**Cause:** `BILLING_DATA_SOURCE=sqlite` is set in `.env` but the database
has not been created yet.

**Fix:** Run the setup script from the project root:

```bash
python scripts/setup_billing_db.py
```

This creates `data/billing.db` and seeds it with 48 records from
`mock-data/billing.json`. The script is idempotent and safe to run again
if the database is corrupted or out of date.

---

### Switching back to JSON

If you want to stop using SQLite, remove `BILLING_DATA_SOURCE=sqlite` from
`.env` or change it to `BILLING_DATA_SOURCE=json`. The JSON backend requires
no setup and works out of the box.

---

## 5. Azure AI Agents SDK version mismatch

### Agent calls fail with AttributeError or unexpected keyword argument

**Symptom:** Errors like `AttributeError: 'ProjectClient' object has no
attribute 'create_thread'` or `TypeError: unexpected keyword argument`.

**Cause:** The Azure AI Agents SDK changed its client structure between
versions. The project uses the sub-client pattern introduced in a later
version:

```python
client.threads.create()
client.messages.create(thread_id=..., ...)
client.runs.create_and_process(thread_id=..., agent_id=...)
```

Older versions exposed these methods directly on the top-level client or
used different method names.

**Fix:** Check the installed SDK version:

```bash
pip show azure-ai-agents
```

Then compare against `requirements.txt`. If the version is older, upgrade:

```bash
pip install -r requirements.txt --upgrade
```

If you are pinned to an older SDK version for other reasons, the relevant
sub-client calls are in `src/orchestrator/agents/factory.py` and the state
modules under `src/orchestrator/states/`.

---

## 6. Streamlit won't start

### Port already in use

**Symptom:**

```
OSError: [Errno 98] Address already in use
```

**Cause:** Another process is already using port 8501 (the Streamlit default).

**Fix:** Either stop the other process or start Streamlit on a different port:

```bash
streamlit run src/ui/app.py --server.port 8502
```

---

### Missing .env file

**Symptom:** `ValidationError` from Pydantic on startup, listing
`AZURE_FOUNDRY_PROJECT_ENDPOINT`, `AZURE_TENANT_ID`, and `VECTOR_STORE_ID`
as missing.

**Cause:** No `.env` file exists in the project root, or the file is in the
wrong location.

**Fix:** Create `.env` in the project root (the same directory as
`requirements.txt`). See [DEPLOYMENT.md](DEPLOYMENT.md) for the required
values.

---

### ModuleNotFoundError: No module named 'src'

**Symptom:** Streamlit starts but immediately shows:

```
ModuleNotFoundError: No module named 'src'
```

**Cause:** Python cannot find the `src/` package because the project root is
not on the Python path. This happens when Streamlit is launched directly
without setting `PYTHONPATH`.

**Fix (Windows):**

```
set PYTHONPATH=C:\path\to\telecom-ops-copilot
streamlit run src/ui/app.py
```

Replace the path with your actual project root. Run both commands in the
same terminal window.

**Fix (Mac/Linux):**

```bash
PYTHONPATH=. streamlit run src/ui/app.py
```

---

## 7. Reading the structured logs

The pipeline emits one JSON log line per event to stdout. Each line has the
following fields:

| Field | Description |
|---|---|
| `timestamp` | ISO 8601 UTC timestamp of the event |
| `level` | Log level: `INFO`, `WARNING`, or `ERROR` |
| `correlation_id` | UUID that ties all events for a single customer turn together |
| `event` | Short name for the event (e.g. `classify_start`, `route_decision`, `act_tool_call`, `escalate_ticket_created`, `respond_complete`) |
| `state` | The pipeline state that emitted the log (`ClassifyState`, `RouteState`, etc.) |
| `account_id` | Account identifier if known at that point in the pipeline |
| `intent` | Detected intent, present from `classify_complete` onward |
| `duration_ms` | Wall-clock duration of the step in milliseconds, where applicable |
| `error` | Error message if `level` is `ERROR` |

### Tracing a failed turn

1. Find the `correlation_id` for the failed turn. It appears in every log
   line for that turn. If you know the approximate time, filter by
   `timestamp`. If you have the Streamlit session, the correlation ID is
   also visible in the UI under the turn metadata (if enabled).

2. Filter all log lines for that `correlation_id`:

   ```bash
   grep '"correlation_id": "YOUR-UUID-HERE"' app.log
   ```

3. Read the lines in `timestamp` order. Look for the first line where
   `level` is `ERROR` or where the `event` name indicates a failure
   (e.g. `classify_failed`, `act_tool_error`).

4. The `error` field on that line contains the exception message. Cross-
   reference with the sections above to identify the cause.

### Common event sequence for a successful billing query

```
classify_start       -> ClassifyState sends query to classifier agent
classify_complete    -> intent=billing, confidence=0.92
route_decision       -> RoutingDecision=BILLING_PATH
act_tool_call        -> tool=get_billing_info, account_id=ACC-10001
act_tool_result      -> success=True, total_bills=3
respond_complete     -> duration_ms=18432
```

If any step is missing from this sequence for a given `correlation_id`,
the pipeline exited early at the last logged step.

---

## Data handling

### What is logged

The structured logger writes the following fields to stdout for every pipeline turn:

| Field | Content |
|---|---|
| `correlation_id` | UUID generated per turn, not tied to any persistent customer identifier |
| `account_id` | The raw account ID parsed from the customer message (e.g. `ACC-10001`) |
| `intent` | Classified intent label |
| `event` | Pipeline event name |
| `agent_response` | Truncated model response text at DEBUG level |

### Why this is acceptable for the current deployment

All account data in this pilot is synthetic mock data. Account IDs (`ACC-10001` through `ACC-10005`) do not correspond to real customers, so logging them in full has no privacy impact.

Escalation tickets are appended to `data/escalations.jsonl`. This file contains the full conversation transcript and the customer account ID. It is excluded from version control via `.gitignore` and should be treated as sensitive on any machine that connects to real customer data.

### What a production deployment would change

Before connecting to real customer data:

- **Hash or truncate `account_id` in logs.** Log `sha256(account_id)[:8]` for correlation without exposing the raw value.
- **Drop `agent_response` at INFO level.** Full model responses at INFO create large log volumes and may contain PII echoed from tool results. Retain at DEBUG only, with DEBUG disabled in production by default.
- **Set a retention window.** Configure log storage (Azure Monitor, Splunk, or equivalent) with a 30 to 90 day retention window to match your data retention policy.
- **Escalation tickets.** Write to a managed store (Cosmos DB, Service Bus) with access controls and field-level encryption on `transcript` and `customer.account_id`, rather than a local file.
