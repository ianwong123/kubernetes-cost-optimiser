# Cost Model Specification
This document defines the cost calculation model that converts CPU and memory **requests** into equivalent Virtual Machines (VM) instances to simulate infrastructure spending.

In this README:
* [The Concept](#the-concept)
* [Cost Model](#cost-model)
* [Initial VM Configuration](#initial-vm-configuration)
* [Example Calculation](#example-cacluation)
* [Implementation Notes](#implementation-notes)
* [Limitations](#limitations)

## The Concept
The ceiling function **represents** Kubernetes' scheduling and cloud billing:
* Kubernetes cannot allocate partial VMs - each pod must fit entirely on a node
* Cloud providers charge for entire VM instances, not partial capacity
* Matches real-world billing where you pay for **reserved capacity**, not usage

## Cost Model
The cost is calculated based on the most constrained resource, following Kubernetes' scheduling principle:

$$
Cost = \max\left(\left\lceil\frac{CPU_{request}}{CPU_{quota}}\right\rceil, \left\lceil\frac{Memory_{request}}{Memory_{quota}}\right\rceil\right) \times VM_{hourly\ rate}
$$

## Initial VM Configuration
The model currently uses **Azure D2as v4** instances:

| Resource | Capacity | Hourly Rate |
|----------|----------|-------------|
| CPU | 2 vCPU | $0.096 |
| Memory | 8 GB | $0.096 |

*Future research will include multiple VM types and specialised instances (e.g., databases).*


## Example Calculation
For a deployment with:
- **Total CPU Requests**: 3.6 vCPU  
- **Total Memory Requests**: 9 GB

$$
\begin{aligned}
\text{CPU VMs} &= \lceil 3.6 / 2 \rceil = \lceil 1.8 \rceil = 2 \\
\text{Memory VMs} &= \lceil 9 / 8 \rceil = \lceil 1.125 \rceil = 2 \\
\text{VMs Needed} &= \max(2, 2) = 2 \\
\text{Cost} &= 2 \times \$0.096 = \$0.192 \text{ per hour}
\end{aligned}
$$

The model calculates the **theoretical minimum** number of VMs needed if perfectly packed. In practice, resource fragmentation might require slightly more VMs, but this provides the optimal baseline for cost optimisation.


## Limitations
* **Single VM type** - uses one instance type instead of optimising across multiple families
* **No discounts** - doesn't account for spot instances, reserved instances, or enterprise discounts  
* **Excluded costs** - ignores storage, networking, load balancers, and other cloud services
* **Simplified scheduling** - assumes perfect bin-packing without fragmentation

*The current model focuses on establishing the core cost optimisation concept. Additional cost factors will be integrated once the main resource right-sizing mechanism is validated.*

> Note: This README is still a work in progress