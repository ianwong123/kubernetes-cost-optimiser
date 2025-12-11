# this file defines the nodes and edges of the graph
from langgraph.graph import StateGraph, START, END
from nodes.reasoner import reason_optimisation
from nodes.recall import recall_memory
from nodes.action import execute_pr
from state import AgentState

# initialise graph with state
workflow = StateGraph(AgentState)

# add nodes
workflow.add_node("recall", recall_memory)
workflow.add_node("reasoner", reason_optimisation)
workflow.add_node("action", execute_pr)

# define edges
workflow.add_edge(START, "recall")
workflow.add_edge("recall", "reasoner")
workflow.add_edge("reasoner", "action")
workflow.add_edge("action", END)

app = workflow.compile()