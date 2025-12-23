# Proposed Designs
This document outlines the main concern of the project, proposed designs, approaches that were rejected, challenges, trade-offs, and successful outcomes that produced significant results

In this document:
* [The Concern](#background)
* [Proposed Architecture](#proposed-architecture)
* To be updated
<!--
* [Capturing Data](#capturing-data)
* [Structuring Data](#structuring-data)
* [Storing Data](#storing-data)
* [Forwarding Data](#forwarding-data)
* [Revised Architecture](#revised-architecture)
-->

## The Concern
There were a lot of uncertainties and questions that were raised on data flow through the system during project development and 
required on-the-fly learning and iterative experimentation while maitaining an agile approach.

Infrastructure has been provisioned, Prometheus scrapes data, Grafana provides visualisaton, Cost Engine and Forecast Service exposes the correct metrics
and is ready to be sent to the agent for optimisation.

But: **how exactly will this data reach the agent?**

In one sentence, the problem can be summarised as:

_"How will real-time data be captured, structured, stored, and forwarded to the agent for further action?"_

The document walks through the early ideas and approaches used to solve this problem, including what worked and what didn't. 

## Proposed Architecture
**Status**: Rejected

**Reason**: The first architecture proposed at the start of the project simply has insufficient detail to show how the goal would actually be achieved. 

It presents the following questions:
* How will the Cost Engine and Forecast Service forward its data to the Context Builder?
* What kind of data will be sent to the Context Builder?
* How will the Context Builder formulate a structured context for the agent?
* How will the structured context be passed to the agent?
* If the agent triggers every 15 minutes, where will this context be stored?
* How will LangChain and Ollama integrate?
* How exactly will reasoning and decision-making be achieved?

Not only does this design add complexity, but also posed risks and disruptions. For instance, everytime the agent makes a bad decision and pushed to production, rolling back via `git revert` would be cumbersome and defeats the purpose of continuous delivery.

<img src="../img/initial-architecture.png" alt="Proposed Architecture" width="700">

## To Be Updated

<!--
## Capturing Data
fwef

## Structuring Data
fwef

## Storing Data
fwef

## Fowarding Data to the Agent
fwef

## Revised Design
Eventually, the components form the finalised design: 

<img src="img/architecture-overview.png" alt="Architecture Diagram" width="700">
-->
