"""Complete response formatting - REFERENCE SOLUTION"""
import json
from typing import List, Dict, Any
from src.core.agent_state import AgentState
from src.llm.llm_client import LLMClient
from src.llm.prompt_manager import PromptManager

class ResponseFormatter:
    def __init__(self, llm: LLMClient, prompt_mgr: PromptManager):
        self.llm = llm
        self.prompt_mgr = prompt_mgr

    def format_grounded_response(self, state: AgentState) -> str:
        """Generate response with citations.

        Grounds from whichever source this state actually has: retrieved
        knowledge-base documents (the retrieve_knowledge path), or live tool
        data (the invoke_tool path) - generate_response is the same graph
        node for both, so this has to handle both, not just retrieved_docs.
        Without this, any TOOL_REQUIRED query gets a generic "I don't have
        that information" response even though invoke_tool() already fetched
        the real answer into state["tool_results"].
        """
        prompt = self.prompt_mgr.get_prompt("response_generation_prompt")

        # Prepare knowledge context - documents if this came from retrieval,
        # otherwise the tool data if this came from invoke_tool.
        if state["retrieved_docs"]:
            knowledge = "\n\n".join([
                f"[{i+1}] {doc['content'][:500]}... (Source: {doc['source']})"
                for i, doc in enumerate(state["retrieved_docs"][:3])
            ])
        elif state.get("tool_results"):
            # No truncation: the full product catalog / branch directory is
            # ~15-19KB each, trivial for the model's context window. An
            # earlier [:3000] cutoff here silently dropped later entries
            # (e.g. credit_cards, or Bangalore branches) before the model
            # ever saw them, making an otherwise-correct tool lookup produce
            # "I don't see that" for data that was right there, just cut off.
            knowledge = json.dumps(state["tool_results"], indent=2)
        else:
            knowledge = ""

        # Generate response
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user_template"].format(
                query=state["query"],
                knowledge=knowledge if knowledge else "No specific documents retrieved."
            )}
        ]

        response = self.llm.generate(messages)

        # Add citations (only meaningful for document-grounded answers -
        # tool data doesn't have a source filename to cite)
        citations = self.extract_citations(state["retrieved_docs"])
        if citations:
            response += f"\n\n**Sources:** {', '.join(citations)}"

        return response
    
    def extract_citations(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Extract citations from documents."""
        return [doc.get("source", "Unknown") for doc in documents[:5]]
