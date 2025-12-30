# AI-Driven Kubernetes Cost Optimser
Autonomous system that reduces cloud costs by right-sizing Kubernetes resources using time-series forecasting and 
retrieval-augmented generation (RAG), with built-in safety controls.

[Watch the Demo](https://github.com/ianwong123/kubernetes-cost-optimiser/releases/tag/v0.1-demo)

Instead of presenting a final sanitised version of the product, details on system design, proposed designs, and both successful outcomes 
and rejected approaches are all documented.

In this README:
* [The Problem](#the-problem)
* [System Components](#system-components)
* [Architecture](#architecture)
* [Agent Lifecycle](#agent-lifecycle)
* [Scope, Constraints, and Implementation Decisions](#scope-constraints-and-implementation-decisions)
* [Results and Evaluation](#results-and-evaluation)
* [Further Reading](#further-reading)
* [Future Work and Reflections](#future-work-and-reflections)

## The Problem
"You pay for what you request, not what you use."

Over-provisioned pods waste money. Under-provisioned pods crash.

Consider a single VM that costs $0.04/hour, with 2 vCPU and 4 GiB RAM available. Whether workloads consume 90% of those resources or just 10%, the VM still costs $0.04/hour. From the cloud provider’s perspective, that capacity is reserved. At the pod level, this means resource requests and limits directly determine how much VM capacity is consumed. Over-requesting resources leads to underutilised nodes and wasted spend.

* **Low traffic + high requests** = idle capacity, wasted spend
* **High traffic + conservative limits** = throttling, OOM, degraded performance

Existing tools do not solve this when cost appears to be a priority:
* **HPA/KEDA** scale replicas but don't fix over-provisioned requests
* **VPA** adjusts resources reactively but can be disruptive
* **Cluster Autoscaler** provisions nodes based on inflated requests

**This project aims to reduce Kubernetes infrastructure costs by eliminating the gap between reserved capacity and actual resource consumption without degrading application performance.**

## System Components
[Google's Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) serves as the sample workload in `default` namespace to provide varied workload patterns to validate the optimisation approach.

The system runs as a continuous, event-driven loop across four layers:

### 1. Observability and Data Generation
* **K3d cluster** hosts Online Boutique application and supporting services across one control plane and two worker nodes
* **Prometheus** scrapes CPU/memory metrics, capturing container usage, and resource requests 
* **Grafana** displays optimisation impact, cost comparisons, resource utilisation, waste percentages, and forecasted demand
* **Cost Engine** queries Prometheus for resource requests, calculates VM requirements, and exposes cost metrics 
* **Forecast Service** retrieves historical usage, trains Prophet models, predicts resource requirements for next twenty-four hours
* **VPA Analyser** queries Kubernetes API for VPA recommendations without injecting changes

### 2. Data Ingestion, Aggregation, and Dispatch
* **Metric Hub** validates payloads, merges asynchronous cost and forecast streams, evaluates thresholds using business logic
* **Redis Stack** stores cost/forecast snapshots, manages job queue, provides vector search for Agent's RAG system

### 3. Reasoning and Execution
* **Ollama** runs Qwen 2.5 (7B) model locally for agent reasoning without external API dependencies
* **Agent** polls queue, retrieves past optimisations via RAG, generates patches using CoT prompting, creates GitHub PRs
* **Learner Server** listens for webhook events from GitHub repo, extracts reasoning from merged PRs, stores success embeddings in Redis Stack **in real-time**

### 4. Continuous Delivery
* **GitHub** stores deployment manifests, enforces PR review workflow before cluster changes
* **ArgoCD** watches the Git repo and applies merged changes to the cluster

## Architecture 
<img src="img/architecture.png" alt="Architecture Diagram" width="1000">

## Agent Lifecycle
A detailed breakdown of the agent's state machine and execution flow: [Agent Design](./docs/agent-design.md)

<img src="img/agent-lifecycle.png" alt="Agent Lifecycle Diagram" width="1000">


> **Real-Time Learning:** Each merged PR immediately updates the knowledge base. The agent retrieves 3 relevant precedents depending on how many successful optimisations have occurred, demonstrating progressive learning without model retraining

## Scope, Constraints and Implementation Decisions
The system adheres to best practices such as separation of concerns and keeping the codebase modular for testability and future extensibility. 

**Scope:**
* This project focuses exclusively on optimising CPU and memory requests for individual Kubernetes pods defined in a single namespace where the sample workload runs
* The project assumes some fixed replica counts, where possible, to target vertical resource efficiency rather than horizontal scaling
* The project assumes a conscious trade-off between stability and efficiency
* System performance is evaluated against VPA (Vertical Pod Autoscaler) recommendations as a baseline

**Constraints:**
* Cost calculations are simplied and based on a single VM pricing model rather cloud provider billing APIs
* Development and testing runs on WSL, which constrains available resources and performance for testing larger workloads
* The implementation prioritises the core optimisation pipeline over production-grade hardening (e.g. security policies, node affinity , etc)

**Implementation Decisions:**

The current infrastructure only contains basic secret management. It does not include, and is not limited to some of the best/advanced practices such as:
* Control plane harderning, security policies, node affinity 
* Scheduling policies (Taints/tolerations)
* Rate limiting, TLS configuration
* Automated Grafana dashboard provisioning

or any sort of design that introduces additional complexity and overhead towards the development of this project.

> **Note:** This is a prototype demonstrating feasibility of AI-driven Kubernetes cost optimisation. It is **not production-ready.**

## Results and Evaluation
The system was evaluated against the **Vertical Pod Autoscaler (VPA)** using the Google Online Boutique workload.

| Metric | Baseline | Agent Optimisation | VPA (Reference) |
| :--- | :--- | :--- | :--- |
| **VM Count** | 12 | **5** | 3 - 4 |
| **Cost/Hour** | £0.48 | **£0.20** | £0.12 - £0.16 |
| **Reduction** | - | **58%** | ~67-75% |

> **Note on Trade-offs:** While VPA achieves higher raw savings, the agent prioritises **stability**. It enforces a safety buffer and maintains explainability via Chain-of-Thought reasoning.

Evaluation report and analysis here: [Evaluation](./docs/evaluation.md)

## Further Reading
* [Agent Design](./docs/agent-design.md) - Agent lifecycle design and state machine 
* [Cost Model](./docs/cost-model.md) - Cost calculation methodology
* [Evaluation](./docs/evaluation.md) - Evaluation results
* [Metric Hub](./docs/metric-hub.md) - Metric Hub design 
* [Proposed Designs](./docs/proposed-designs.md) - Previously proposed designs, rejected approaches, challenges, and outcomes
* [Testing Strategy](./docs/testing.md) - Test strategies and validation


## Future Work and Reflections
This project started out of genuine curiousity. I kept reading about cost efficiencies and in the cloud industry while autonomous agents were becoming a growing topic of interest across the IT industry. So I thought:

_"Why not try building something to see whether an autonomous agent could actually reduce infrastructure cost?"_

This is despite having no real production experience, and only some exposure to several industry tools. Still, it felt like an interesting problem to explore, so I decided to take on the challenge and see how far I could push it.

The current system remains a prototype, validated using a sample workload, and is still undergoing continuous improvements. Since it is designed with extensibility in mind, one could easily swap out concrete implementations (like the Redis Queue) for more robust solutions.

Some potential extensions include:
* Extend to multi-namespace cost aggregation
* Integrate with external observability tools
* Support multiple cloud providers (AWS, GCP, Azure)
* Allowing configuration through a single YAML file for containing VM types, names, and provider details to decouple the system from cluster-specific assumptions
* Add priority queuing for risk-based alert handling

### Final Thoughts
It's unlikely that I will maintain this as a long-term project, as there are other areas I want to explore next. However, I plan to revisit it occasionally to apply new techniques as I learn them.

My next project will likely focus on developer experience, inspired by on one of the challenges found here. Specifically, spinning up some preview environment in the cluster to test code before making PRs, and destroy automatically when its done.

_Hi job market, pls be kind_ (┳◡┳)

### With that said... (눈_눈) 
This is one of the first times I have designed and implemented a system of this complexity from start to finish. It's not the best, there are certainly far better ways to build this, and in a more realistic production setting, I expect tools, data, and constraints to be more diverse and complex than this.

But for the scope of this project, I'm genuinely really proud and satisfied with the outcome ┐(´～｀)┌ 

I gave my all using the resources I had, and I shall end it here.

**I rest my case.**

~ Ian 

(シ_ _)シ


> **Note**: This is an independent project, not affiliated with Google or any cloud provider.