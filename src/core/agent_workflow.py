"""
Agent workflow implementation using LangGraph.
"""
import os
import re
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
    """Enterprise AI Customer Operations Agent."""

    def __init__(self):
        """Initialize the agent's dependencies and compile the workflow."""
        self.llm = LLMClient()
        self.prompt_mgr = PromptManager()
        self.kb = KnowledgeBase()
        self.retriever = Retriever(self.kb)
        self.formatter = ResponseFormatter(self.llm, self.prompt_mgr)

        # Load a previously built index if one exists. If Activity 2.1 hasn't
        # been completed yet, the agent still starts up - it will simply
        # retrieve no documents until an index is built and cached.
        try:
            self.kb.load_index(INDEX_PATH)
        except (FileNotFoundError, RuntimeError, OSError):
            logger.info("No cached knowledge base index found yet.")

        self.workflow = self.build_workflow()

    def build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        classify_intent branches (via route_decision) to retrieve_knowledge,
        invoke_tool, clarify, or escalate. Retrieval and tool results feed
        generate_response; generate_response, clarify, and escalate end the run.

        Returns:
            StateGraph: Compiled workflow
        """
        workflow = StateGraph(AgentState)
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("retrieve_knowledge", self.retrieve_knowledge)
        workflow.add_node("invoke_tool", self.invoke_tool)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("clarify", self.clarify)
        workflow.add_node("escalate", self.escalate)

        workflow.set_entry_point("classify_intent")
        workflow.add_conditional_edges("classify_intent", self.route_decision)

        workflow.add_edge("retrieve_knowledge", "generate_response")
        workflow.add_edge("invoke_tool", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("clarify", END)
        workflow.add_edge("escalate", END)

        return workflow.compile()

    def classify_intent(self, state: AgentState) -> AgentState:
        """
        Classify user intent.

        The few-shot examples from prompts.yaml's classification_examples are
        appended to the system prompt. Any LLM output that doesn't name a
        known category is treated as ESCALATION_REQUIRED, so unclear
        classifications fail safe to a human.
        """
        prompt = self.prompt_mgr.get_prompt("classification_prompt")

        examples = self.prompt_mgr.prompts.get("classification_examples", [])
        formatted_examples = "\n\n".join(
            f"Query: {ex['query']}\nCategory: {ex['category']}\nConfidence: {ex['confidence']}"
            for ex in examples
        )
        system_prompt = prompt["system"]
        if formatted_examples:
            system_prompt += "\n\nExamples:\n\n" + formatted_examples

        result = self.llm.classify(state["query"], system_prompt)

        if "KNOWLEDGE_QUERY" in result:
            state["intent"] = "KNOWLEDGE_QUERY"
        elif "TOOL_REQUIRED" in result:
            state["intent"] = "TOOL_REQUIRED"
        elif "CLARIFICATION" in result:
            state["intent"] = "CLARIFICATION_NEEDED"
            state["needs_clarification"] = True
        else:
            state["intent"] = "ESCALATION_REQUIRED"
            state["needs_escalation"] = True
            state["escalation_reason"] = self._detect_escalation_reason(state["query"])

        match = re.search(r"Confidence:\s*([0-9]*\.?[0-9]+)", result)
        state["confidence"] = float(match.group(1)) if match else 0.0

        logger.info(f"Classified intent: {state['intent']} (confidence {state['confidence']})")
        return state

    def _detect_escalation_reason(self, query: str) -> str:
        """
        Match the query against configured escalation keywords for a
        human-readable reason.

        Uses workflow.routing.escalation_keywords from agent_config.yaml and
        returns a reason naming the first keyword found in `query`
        (case-insensitive), or a generic fallback reason if none match.
        """
        config = load_yaml_config("config/agent_config.yaml")
        keywords = config.get("workflow", {}).get("routing", {}).get("escalation_keywords", [])

        query_lower = query.lower()
        for keyword in keywords:
            if keyword.lower() in query_lower:
                return f"Sensitive request - query mentions '{keyword}'"
        return "Request requires human review"

    def route_decision(self, state: AgentState) -> Literal[
        "retrieve_knowledge", "invoke_tool", "clarify", "escalate"
    ]:
        """
        Route based on classified intent.

        Clarification and escalation flags take priority over intent; any
        intent other than TOOL_REQUIRED goes to knowledge retrieval.
        """
        if state["needs_clarification"]:
            return "clarify"
        if state["needs_escalation"]:
            return "escalate"
        if state["intent"] == "TOOL_REQUIRED":
            return "invoke_tool"
        return "retrieve_knowledge"

    def retrieve_knowledge(self, state: AgentState) -> AgentState:
        """
        Retrieve relevant documents from the knowledge base.
        """
        state["retrieved_docs"] = self.retriever.retrieve(state["query"], top_k=5)
        return state

    def invoke_tool(self, state: AgentState) -> AgentState:
        """
        Invoke a business tool based on the query.

        Branch/location queries use find_branch_info(); everything else uses
        get_product_catalog(). Tool selection is a simple keyword check, not
        NLU-based.
        """
        from src.tools.product_tools import get_product_catalog
        from src.tools.branch_tools import find_branch_info

        query_lower = state["query"].lower()

        branch_keywords = ("branch", "location", "nearest", "visit")
        if any(keyword in query_lower for keyword in branch_keywords):
            state["tool_results"] = {"branches": find_branch_info()}
        else:
            state["tool_results"] = {"products": get_product_catalog()}
        return state

    def generate_response(self, state: AgentState) -> AgentState:
        """
        Generate the grounded, cited response.

        Wires together format_grounded_response() and extract_citations(),
        both implemented in Activity 2.3 (src/core/response_formatter.py).
        Pre-implemented here, same as __init__'s dependency wiring: calling
        two already-implemented methods isn't a new concept this lab is
        teaching.
        """
        state["response"] = self.formatter.format_grounded_response(state)
        state["citations"] = self.formatter.extract_citations(state["retrieved_docs"])
        return state

    def clarify(self, state: AgentState) -> AgentState:
        """
        Ask the customer a clarification question.
        """
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
        """
        Produce an escalation message for a sensitive/unsupported request.
        """
        prompt = self.prompt_mgr.get_prompt("escalation_prompt")

        reason = state.get("escalation_reason") or "Request requires human review"
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user_template"].format(
                query=state["query"], reason=reason
            )}
        ]
        state["response"] = self.llm.generate(messages, temperature=0.3, max_tokens=200)
        return state

    def run(self, query: str) -> Dict[str, Any]:
        """Run the agent workflow.

        Pre-implemented, same as __init__'s dependency wiring: invoking a
        compiled LangGraph graph is not a new concept this lab is teaching
        (that's Activity 1.2's build_workflow()). Every activity from here
        on, and Activity 3.3's final scorecard, calls agent.run(query).
        """
        if not self.workflow:
            self.workflow = self.build_workflow()

        initial_state = AgentState(
            query=query,
            intent=None,
            confidence=0.0,
            retrieved_docs=[],
            tool_results=None,
            response=None,
            citations=[],
            needs_clarification=False,
            needs_escalation=False,
            clarification_question=None,
            escalation_reason=None
        )

        return self.workflow.invoke(initial_state)
