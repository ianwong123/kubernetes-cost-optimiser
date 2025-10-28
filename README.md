# AI-Driven Kubernetes Cost Optimser
An autonomous system that reduces cloud costs by dynamically right-sizing Kubernetes
resources, eliminating over-provisioning without performance degradation.

In this README:
* [How it works](#how-it-works)
* [Architecture overview](#architecture-overview)
* [More Information](#more-information)
<!--* [Install](#install)-->


## How it works
The system operates on a core design principle: **we assume fixed replica counts to optimise resource requests**, eliminating over-provisioning at its source. This focuses the optimisation on the fundamental unit of cost (i.e. individual pod request), rather than multiplying inefficiency by scaling replica counts. It functions as a continuous feedback loop with components running at different intervals: 

### Monitoring and Analysis
* **Prometheus** scrapes pod CPU/memory usage from a k3d cluster every **15 seconds**
* The **Forecast Engine** continuously analyses trends using Facebook Prophet
* The **Cost Engine** constantly calculates infrastructure cost based on current resource requests
* **Grafana** visualises cost, metrics, requests, etc,.

### AI Agent 
* The **AI Agent** is triggered every 15 mins, receiving a context of: forecasted demand, current usage, resource requests, and cost analysis.
* The agent **decides new, optimised resource requests** for individual pods 
* It generates an **explainable rationale** for each change.
* Decisions are committed as **YAML manifests to Git**.

### GitOps Deployment 
* **ArgoCD** automatically detects the Git commit and syncs the changes to the cluster.
* Every modification is **versioned, auditable, and reversible**.

## Architecture overview
```mermaid 
---
config:
  theme: neutral
  flowchart:
    curve: basis
---

flowchart TD
    %% Load testing / Traffic simulator    
    locust[Locust<br/>Synthetic Traffic Generator]

    %% Infrastructure Layer
    k8s[K3d Cluster<br/>Google Online Boutique]
    prom[Prometheus<br/>15s CPU/Memory Scrape Interval]
    promdb[(Prometheus TSDB<br/>Time-Series Storage)]
    grafana[Grafana Dashboard<br/>Cost & Usage Visualisation]

    %% Monitoring Trigger
    cron{{Forecast Trigger<br/>15-min Interval}}

    %% Forecast & Cost Engine
    subgraph Forecast & Cost Engine
        trend[Trend Analysis Module<br/>Facebook Prophet]
        azure-api[VM-Based Cost Calculator<br/>Azure Pricing]
        prompt-builder[Context Builder<br/>Forecast + Request + Cost]
    end

    %% AI Decision Engine
    subgraph AI Agent
        agent[LangChain Orchestrator]
        ollama[Ollama Runtime<br/>QWEN 2.5:7b]
        reasoning[Inference Engine<br/>Scaling Decisions]
        explanation[Decision Rationale Generator]
    end

    %% GitOps Deployment Pipeline
    generate-yaml[YAML Patch Generator]
    git-commit[GitOps Commit<br/>Versioned Deployment]
    argocd[ArgoCD Sync<br/>30s Interval]

    %% Flow connections
    locust -->|Simulates user load| k8s     
    k8s -->|Exposes pod-level metrics| prom
    prom -->|Stores time-series data| promdb
    promdb -->|Visualise metrics| grafana
    promdb -->|Historical + current usage| trend
    promdb -->|Current request| azure-api
    azure-api -->|VM count and cost| prompt-builder
    trend -->|Forecasted demand| prompt-builder
    prompt-builder -->|Structured context| agent
    cron -->|Triggers AI cycle| agent
    agent -->|Passes prompt| ollama
    ollama -->|Inference| reasoning
    reasoning -->|Optimisation decisions| explanation

    %% GitOps pipeline
    reasoning -->|Decisions| generate-yaml
    generate-yaml -->|Update YAML| git-commit
    git-commit -->|Triggers sync| argocd
    argocd -->|Applies scaling decisions| k8s
```
<!--## Install
1. **Start by cloning the repository**
```bash
git clone https://github.com/ianwong123/kubernetes-cost-optimiser.git
cd kubernetes-cost-optimiser
```

2. **Run the installation script**
```bash
./system.sh
```
-->

## More information
Here are some other documents you may wish to read:
* [cost-model.md](cost-model.md)
* agent-internal-workflow.md (TBA)

> Note: This is not a google project. This is an independent project and is still a work in progress.