# Evaluation & Performance Analysis

The system was evaluated against the **Vertical Pod Autoscaler (VPA)** to serve as a baseline for autonomous resource optimisation.

## Executive Summary

| Metric | Baseline (Pre-Optimisation) | Agent Optimisation | VPA (Reference) |
| :--- | :--- | :--- | :--- |
| **VM Configuration** | 12 VMs | **5 VMs** | 3-4 VMs |
| **Cost Per Hour** | £0.48 | **£0.20** | £0.12 - £0.16 |
| **Total Reduction** | - | **58%** | ~67-75% |

### Success Criteria
✅ **58% cost reduction** without performance degradation  
✅ **Explainable decisions** via Chain-of-Thought reasoning  
✅ **Safety control** through PR approval workflow  
✅ **Progressive learning** from validated outcomes  
⚠️ **Lower raw reduction than VPA** (Intentional trade-off for stability)


## Analysis

### Cost vs. Stability Trade-off
The £0.04/hour difference between the agent and VPA stems from the agent's deliberate architectural choice to prioritise stability over maximum efficiency.

The agent enforces strict minimum thresholds of **100m CPU** and **128Mi memory** while applying a safety buffer that caps reductions at **50%-70% per optimisation event**. In contrast, VPA recommendations were significantly more aggressive, with some CPU requests dropping as low as 25m based on observed usage patterns. While the VPA approach yields higher raw savings, the agent’s conservative boundaries provide a necessary safety margin for production environments where aggressive scaling can introduce stability risks.

### Local LLM Overhead & Latency
A significant trade-off observed during evaluation was the operational overhead introduced by running the AI model locally.

Unlike the VPA, the agent’s reliance on a locally hosted **7-billion-parameter model** introduced noticeable latency, with inference times averaging between **45 seconds to 2 minute per job**. This processing overhead also necessitated increasing the host environment’s memory allocation to **14GB** to prevent system instability. While this latency is acceptable for non-critical background optimisations, it highlights that running large language models on the edge requires substantial compute resources compared to traditional algorithmic scalers.

### Forecast Service & Validation Limits
Performance validation presented challenges due to the limitations of the Online Boutique load generator. Simulating realistic traffic proved difficult because load intensity adjustments produced minimal impact on resource consumption and the workload lacked seasonal patterns. Consequently, validation focused on the **absence of degradation** rather than quantitative metrics. The system maintained service stability with **no pod restarts, OOM kills, or CPU throttling events** during evaluation.

The Forecast Service provided limited utility in this specific context. The local environment exhibited stable and low-variance usage, meaning forecast predictions merely tracked current usage with minimal deviation. As a result, Capacity Risk triggers rarely activated. However, in production environments with variable traffic patterns, this component would likely provide greater value.