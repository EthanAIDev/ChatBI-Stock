from langgraph.graph import StateGraph, END
from backend.graph.state import PipelineState
from backend.graph.nodes import classify_intent, generate_sql, execute_sql, analyze_data


def build_graph():
    builder = StateGraph(PipelineState)

    builder.add_node("classify", classify_intent)
    builder.add_node("generate_sql", generate_sql)
    builder.add_node("execute", execute_sql)
    builder.add_node("analyze", analyze_data)

    builder.set_entry_point("classify")

    builder.add_conditional_edges(
        "classify",
        lambda s: "generate_sql" if s.get("data_query", True) else END,
        {"generate_sql": "generate_sql", END: END},
    )

    builder.add_conditional_edges(
        "generate_sql",
        lambda s: "execute" if not s.get("from_cache") else "analyze",
        {"execute": "execute", "analyze": "analyze"},
    )

    builder.add_edge("execute", "analyze")
    builder.add_edge("analyze", END)

    return builder.compile()


app = build_graph()
