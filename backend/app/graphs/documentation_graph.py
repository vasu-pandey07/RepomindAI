from langgraph.graph import StateGraph, START, END

from app.graphs.state import AgentState
from app.graphs.nodes import AgentNodes

# Initialize nodes
nodes = AgentNodes()

workflow = StateGraph(AgentState)

# Define pipeline
workflow.add_node("retrieve", nodes.retrieve_context_node)
workflow.add_node("analyze", nodes.analyze_code_node)
workflow.add_node("generate", nodes.generate_response_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "analyze")
workflow.add_edge("analyze", "generate")
workflow.add_edge("generate", END)

documentation_graph = workflow.compile()
