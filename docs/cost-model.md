# Cost Model Specification
This document defines the cost calculation model that converts CPU and memory **requests** into equivalent Virtual Machines (VM) instances to simulate infrastructure spending.

In this document:
* [The Concept](#the-concept)
* [Cost Model](#cost-model)
* [Initial Configuration](#initial-configuration)
* [Example Calculation](#example-cacluation)
* [Limitations](#limitations)

## The Concept
"You pay for what you request, not what you use."

Cloud providers charge for an entire VM instance regardless of how much resources are used, while Kubernetes scheduling requires pods to fit completely on nodes. This combination forces over-provisioning.

Consider a deployment requesting 4 vCPU and 8 GiB memory running on 2 vCPU and 4 GiB nodes. The cluster must reserve two full VMs even if actual usage averages just 10%. You're paying for 20x more capacity than you need. This could be a direct result of risk-averse resource allocation.

## Cost Model
To capture this financial impact, the cost model below translates resource requests into VM costs using Kubernetes' own scheduling logic. The calculation identifies the most constrained resource, whether CPU or memory, and uses the **ceil** function to **conceptually represent** real-world cloud billing:

$$
\mathit{Cost} = \max\left(
\text{ceil}\!\left\lceil \frac{TotalCPU_{request}}{CPU_{quota}} \right\rceil,
\text{ceil}\!\left\lceil \frac{TotalMemory_{request}}{Memory_{quota}} \right\rceil
\right)
\times VM_{hourly\ rate}
$$

## Initial Configuration
For initial validation, the model uses **Azure B2s** instances as a reference point:

| VM Instance | CPU | Memory | Hourly Rate |
|-------------|-----|--------|-------------|
| Azure B2s | 2 vCPU | 4 GiB | $0.04 |

This single-instance approach establishes a consistent baseline. Future iterations will incorporate multiple VM types and specialised instances (e.g., storage, databases, containers, etc,.) once the core optimisation is proven.

## Example Calculation
Take a deployment with:
- **Total CPU Requests**: 3.6 vCPU  
- **Total Memory Requests**: 9 GiB

$$
\begin{aligned}
\text{CPU VMs} &= \lceil 3.6 / 2 \rceil = \lceil 1.8 \rceil = 2 \\
\text{Memory VMs} &= \lceil 9 / 4 \rceil = \lceil 2.25 \rceil = 3 \\
\text{VMs Needed} &= \max(2, 3) = 3 \\
\text{Cost} &= 3 \times \$0.04 = \$0.12 \text{ per hour}
\end{aligned}
$$

This calculates the **theoretical minimum** number of VMs required to fit all pods based on their resource requests. While real clusters may need additional nodes due to mixed workloads and scheduling constraints, this provides the optimal baseline for cost optimisation.

## Limitations
* The current implementation uses a single VM type rather than optimising across instance families
* Real-world discounts like spot instances and reserved commitments aren't yet factored in
* Additional costs for storage, networking, load balancers, and other cloud services remain outside scope
* The model calculates optimal packing but doesn't account for real-world scheduling constraints like node affinity rules or mixed workload patterns that can increase the actual VM count needed.

> Note: The current model focuses on establishing the core cost optimisation concept.
