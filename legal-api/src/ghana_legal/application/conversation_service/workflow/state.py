from langgraph.graph import MessagesState


class LegalExpertState(MessagesState):
    """State class for the LangGraph workflow. It keeps track of the information necessary to maintain a coherent
    conversation between the Legal Expert and the user.

    Attributes:
        legal_context (str): The retrieved legal context (articles, cases, etc.).
        expert_name (str): The name of the legal expert.
        expertise (str): The area of expertise.
        style (str): The communication style.
        summary (str): A summary of the conversation.
    """

    legal_context: str
    expert_name: str
    expertise: str
    style: str
    summary: str


def state_to_str(state: LegalExpertState) -> str:
    if "summary" in state and bool(state["summary"]):
        conversation = state["summary"]
    elif "messages" in state and bool(state["messages"]):
        conversation = state["messages"]
    else:
        conversation = ""

    return f"""
LegalExpertState(legal_context={state.get("legal_context", "")}, 
expert_name={state.get("expert_name", "")}, 
expertise={state.get("expertise", "")}, 
style={state.get("style", "")}, 
conversation={conversation})
        """
