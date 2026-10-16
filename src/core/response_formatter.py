"""
Response formatting with citations.
"""
import json
from typing import List, Dict, Any
from src.core.agent_state import AgentState
from src.llm.llm_client import LLMClient
from src.llm.prompt_manager import PromptManager

class ResponseFormatter:
    """Format responses with citations."""

    def __init__(self, llm: LLMClient, prompt_mgr: PromptManager):
        """Store the LLM client and prompt manager for use by this formatter."""
        self.llm = llm
        self.prompt_mgr = prompt_mgr

    def format_grounded_response(self, state: AgentState) -> str:
        """
        Generate response with document citations.

        Grounds the answer in retrieved documents if there are any, otherwise
        in the tool results (not truncated, so the entry the query asks about
        isn't cut off). Document sources are appended as citations; tool
        answers have no source files, so they get none.

        Args:
            state: Current agent state with retrieved docs

        Returns:
            Formatted response string with citations
        """
        prompt = self.prompt_mgr.get_prompt("response_generation_prompt")

        if state["retrieved_docs"]:
            knowledge = "\n\n".join(
                f"[{i+1}] {doc['content'][:500]}... (Source: {doc['source']})"
                for i, doc in enumerate(state["retrieved_docs"])
            )
        elif state.get("tool_results"):
            knowledge = json.dumps(state["tool_results"], indent=2)
        else:
            knowledge = ""

        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user_template"].format(
                query=state["query"], knowledge=knowledge
            )}
        ]
        response = self.llm.generate(messages)

        citations = self.extract_citations(state["retrieved_docs"])
        if citations:
            # Several chunks can come from the same file; list each file once.
            response += "\n\n**Sources:** " + ", ".join(dict.fromkeys(citations))
        return response

    def extract_citations(self, documents: List[Dict[str, Any]]) -> List[str]:
        """
        Extract citation information from documents.

        Returns the `source` field of each of the first five documents.
        """
        return [doc["source"] for doc in documents[:5]]
