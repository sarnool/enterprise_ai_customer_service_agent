"""Complete LangGraph workflow implementation - REFERENCE SOLUTION"""
import os
from pathlib import Path
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from src.core.agent_state import AgentState
from src.llm.llm_client import LLMClient
from src.llm.prompt_manager import PromptManager
from src.knowledge.knowledge_base import KnowledgeBase
from src.knowledge.retriever import Retriever
from src.core.response_formatter import ResponseFormatter
from src.utils.config_loader import load_yaml_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Where the FAISS index built in Activity 2.1 is cached on disk, so the agent
# can load a previously built index instead of re-embedding the knowledge
# base (and re-billing the OpenAI API) every time it starts up.
INDEX_PATH = str(Path(os.getenv("VECTOR_DB_PATH", "./vector_store")) / "kb_index")


class CustomerOperationsAgent:
    def __init__(self):
        self.llm = LLMClient()
        self.prompt_mgr = PromptManager()
        self.kb = KnowledgeBase()
        self.retriever = Retriever(self.kb)
        self.formatter = ResponseFormatter(self.llm, self.prompt_mgr)

        # Load a previously built index if one exists. If Activity 2.1
        # hasn't been completed yet, the agent still starts up - it will
        # simply retrieve no documents until an index is built and cached.
        try:
            self.kb.load_index(INDEX_PATH)
            logger.info(f"Loaded cached knowledge base index from {INDEX_PATH}")
        except (FileNotFoundError, RuntimeError, OSError):
            logger.info("No cached knowledge base index found yet.")

        self.workflow = self.build_workflow()

    def build_workflow(self) -> StateGraph:
        """Build complete LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("retrieve_knowledge", self.retrieve_knowledge)
        workflow.add_node("invoke_tool", self.invoke_tool)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("clarify", self.clarify)
        workflow.add_node("escalate", self.escalate)

        # Set entry point
        workflow.set_entry_point("classify_intent")

        # Add conditional edges
        workflow.add_conditional_edges("classify_intent", self.route_decision)
        workflow.add_edge("retrieve_knowledge", "generate_response")
        workflow.add_edge("invoke_tool", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("clarify", END)
        workflow.add_edge("escalate", END)

        return workflow.compile()

    def classify_intent(self, state: AgentState) -> AgentState:
        """Classify user intent."""
        prompt = self.prompt_mgr.get_prompt("classification_prompt")

        # Few-shot examples from config/prompts.yaml's classification_examples
        # actually get folded into the system prompt here - without this,
        # that YAML key is loaded but never used anywhere, silently
        # contradicting this lab's own "add an example, save, and re-run"
        # exercise (adding an example would have zero effect on behaviour).
        examples = self.prompt_mgr.prompts.get("classification_examples", [])
        if examples:
            examples_text = "\n".join(
                f'Query: "{ex["query"]}"\nCategory: {ex["category"]}\nConfidence: {ex["confidence"]}'
                for ex in examples
            )
            system_prompt = f"{prompt['system']}\n\nExamples:\n{examples_text}"
        else:
            system_prompt = prompt["system"]

        result = self.llm.classify(state["query"], system_prompt)

        # Parse classification result
        if "KNOWLEDGE_QUERY" in result:
            state["intent"] = "KNOWLEDGE_QUERY"
            state["confidence"] = 0.9
        elif "TOOL_REQUIRED" in result:
            state["intent"] = "TOOL_REQUIRED"
            state["confidence"] = 0.85
        elif "CLARIFICATION" in result:
            state["needs_clarification"] = True
            state["intent"] = "CLARIFICATION_NEEDED"
        else:
            # Fail safe: anything the classifier doesn't confidently recognize
            # is routed to a human rather than guessed at.
            state["needs_escalation"] = True
            state["intent"] = "ESCALATION_REQUIRED"
            state["escalation_reason"] = self._detect_escalation_reason(state["query"])

        return state

    def _detect_escalation_reason(self, query: str) -> str:
        """Match the query against configured escalation keywords for a human-readable reason."""
        try:
            agent_config = load_yaml_config("config/agent_config.yaml")
            keywords = agent_config.get("workflow", {}).get("routing", {}).get("escalation_keywords", [])
        except FileNotFoundError:
            keywords = []

        query_lower = query.lower()
        for keyword in keywords:
            if keyword in query_lower:
                return f"Query mentions '{keyword}', which requires human review per policy."
        return "This query involves a sensitive or complex matter requiring human review."

    def route_decision(self, state: AgentState) -> Literal["retrieve_knowledge", "invoke_tool", "clarify", "escalate"]:
        """Route based on intent."""
        if state.get("needs_clarification"):
            return "clarify"
        if state.get("needs_escalation"):
            return "escalate"
        if state["intent"] == "TOOL_REQUIRED":
            return "invoke_tool"
        return "retrieve_knowledge"

    def retrieve_knowledge(self, state: AgentState) -> AgentState:
        """Retrieve from knowledge base."""
        docs = self.retriever.retrieve(state["query"], top_k=5)
        state["retrieved_docs"] = docs
        return state

    def invoke_tool(self, state: AgentState) -> AgentState:
        """Invoke a business tool based on simple keyword matching on the query."""
        from src.tools.product_tools import get_product_catalog
        from src.tools.branch_tools import find_branch_info

        query_lower = state["query"].lower()
        branch_keywords = ["branch", "location", "nearest", "visit", "address"]

        if any(keyword in query_lower for keyword in branch_keywords):
            state["tool_results"] = {"branches": find_branch_info()}
        else:
            state["tool_results"] = {"products": get_product_catalog()}
        return state

    def generate_response(self, state: AgentState) -> AgentState:
        """Generate grounded response."""
        response = self.formatter.format_grounded_response(state)
        state["response"] = response
        state["citations"] = self.formatter.extract_citations(state["retrieved_docs"])
        return state

    def clarify(self, state: AgentState) -> AgentState:
        """Ask a clarification question using the LLM."""
        prompt = self.prompt_mgr.get_prompt("clarification_prompt")
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user_template"].format(query=state["query"])}
        ]
        question = self.llm.generate(messages, temperature=0.3, max_tokens=200)
        state["clarification_question"] = question
        state["response"] = question
        return state

    def escalate(self, state: AgentState) -> AgentState:
        """Generate a professional escalation message using the LLM."""
        prompt = self.prompt_mgr.get_prompt("escalation_prompt")
        reason = state.get("escalation_reason") or "This request requires specialized assistance."
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user_template"].format(query=state["query"], reason=reason)}
        ]
        state["response"] = self.llm.generate(messages, temperature=0.3, max_tokens=200)
        return state

    def run(self, query: str) -> Dict[str, Any]:
        """Execute workflow."""
        result = self.workflow.invoke(AgentState(
            query=query, intent=None, confidence=0.0, retrieved_docs=[],
            tool_results=None, response=None, citations=[],
            needs_clarification=False, needs_escalation=False,
            clarification_question=None, escalation_reason=None
        ))
        return result
