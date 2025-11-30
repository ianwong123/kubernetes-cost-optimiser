# this file defines the nodes and edges of the graph
from langgraph.graph import StateGraph, START, END
from nodes.reasoner import reason_optimisation
from state import AgentState

# initialise graph with state
workflow = StateGraph(AgentState)

# add nodes
workflow.add_node("reasoner", reason_optimisation)

# define edges
workflow.add_edge(START, "reasoner")

workflow.add_edge("reasoner", END)

app = workflow.compile()