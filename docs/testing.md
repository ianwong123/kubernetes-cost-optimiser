# Testing Strategy & Validation

The system followed a **Test-Driven Development (TDD)** approach. Testing occurred continuously throughout development rather than as a separate phase. 

This document covers unit and integration tests for the **Metric Hub (Go)** and **Agent (Python)**, covering API handling, data persistence, and LLM reasoning.

## 1. Metric Hub Validation (Go)
The Metric Hub acts as the API Gateway and Aggregator. Tests verified that it correctly handles asynchronous streams without blocking.

### API Server & Payload Validation
*Verifying that the API correctly rejects malformed data and accepts valid schemas.*

| Test Scenario | Input | Expected Behaviour | Status |
| :--- | :--- | :--- | :--- |
| **Valid Payload** | Correctly structured JSON with all required fields | `HTTP 201 Created` | ✅ PASS |
| **Missing Field** | Payload missing `namespace` field | `HTTP 400 Bad Request` | ✅ PASS |
| **Invalid Type** | `vm_count` as string instead of integer | `HTTP 400 Bad Request` | ✅ PASS |
| **Valid Forecast** | Correctly structured forecast JSON | `HTTP 201 Created` | ✅ PASS |

### Cost Ingestion & Persistence
*Integration test against a live Redis instance ensuring data is actually saved.*

| Component | Expected Behaviour | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| **Connectivity** | Connects to `localhost:6379` | Established connection immediately | ✅ PASS |
| **API Response** | Returns `201 Created` immediately (non-blocking) | API returned 201 | ✅ PASS |
| **Persistence** | Payload saved to Redis key `cost:latest` | Verified via `redis-cli GET cost:latest` | ✅ PASS |
| **Background Logic** | Threshold checks run asynchronously | Logs confirmed background execution | ✅ PASS |

### Aggregator Logic (Thresholds & Cooldowns)
*Verifying the threshold logic ensuring we don't spam the agent with redundant alerts.*

| Scenario | Metrics | Outcome | Status |
| :--- | :--- | :--- | :--- |
| **High Utilisation** | Memory > 90% | **Trigger:** "High Stability Risk" (Immediate) | ✅ PASS |
| **Efficiency Risk** | Waste > 50% | **Trigger:** "High Waste" | ✅ PASS |
| **Cooldown Active** | Triggered < 30 mins ago | **Skip:** Suppress trigger | ✅ PASS |
| **Forecast Risk** | Forecast predicts crash | **Trigger:** Immediate (Bypass Cooldown) | ✅ PASS |

---

## 2. Agent Validation (Python + LLM)
Testing the autonomous agent required verifying probabilistic LLM outputs and RAG retrieval.

### Poller Node (Ingestion)
*Verifying the agent correctly consumes jobs from the Redis Queue.*

| Component | Expected Behaviour | Status |
| :--- | :--- | :--- |
| **Queue Consumption** | Agent detects job immediately via `BRPOP` | ✅ PASS |
| **Data Integrity** | JSON payload parsed correctly into Python `AgentState` | ✅ PASS |
| **Type Safety** | Python types match Go struct definitions | ✅ PASS |

### Recall Node (RAG)
*Verifying the agent can learn from the past.*

| Scenario | Expected Behaviour | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| **Cold Start** | Returns 0 results; proceeds without context | Logs: "Found 0 past optimisations" | ✅ PASS |
| **Warm Start** | Retrieves injected success story via vector search | Logs: "Found 1 relevant past optimisation" | ✅ PASS |
| **Context Usage** | LLM references historical case in reasoning | Output: *"In a similar past case..."* | ✅ PASS |

### Reasoner Node (LLM Logic)
*Verifying `Qwen 2.5 7B` follows Chain-of-Thought prompts and does math correctly.*

| Component | Expectation | Result | Status |
| :--- | :--- | :--- | :--- |
| **Math Accuracy** | Calculate 110% of Forecast ($3.0 * 1.1$) | Calculated `3300m` (3.3 cores) | ✅ PASS |
| **Logic Adherence** | Prioritise Forecast risk over current low usage | Explicitly presented prioritisation in logs | ✅ PASS |
| **Unit Conversion** | Convert `0.4` cores to `400m` | Explicit conversion steps shown | ✅ PASS |
| **Strict JSON** | Output only valid JSON (no markdown preamble) | Successfully parsed by `json.loads` | ✅ PASS |

### Action Node (GitHub Ops)
*Verifying the agent can actually write code.*

| Component | Expectation | Status |
| :--- | :--- | :--- |
| **Branching** | Creates unique branch `optimise/<service>-<uuid>` | ✅ PASS |
| **Patching** | Modifies only `resources` block in YAML | ✅ PASS |
| **PR Creation** | Opens PR with LLM reasoning in body | ✅ PASS |

---

## 3. Feedback Loop Validation
*The "Learning" phase. Verifying that human decisions feed back into the system.*

| Component | Expected Behaviour | Status |
| :--- | :--- | :--- |
| **Webhook Receipt** | Server receives `POST /webhook` from GitHub | ✅ PASS |
| **Filtering** | Ignores closed-but-not-merged PRs | ✅ PASS |
| **Knowledge Storage** | Extracts reasoning & embeds into Vector Store | ✅ PASS |