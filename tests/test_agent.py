"""Test suite for agent workflow."""
import pytest
from unittest.mock import MagicMock
from src.core.agent_state import AgentState
from src.core.agent_workflow import CustomerOperationsAgent
from src.core.response_formatter import ResponseFormatter
from src.llm.prompt_manager import PromptManager

def make_state(query="Test query", **overrides):
    state = AgentState(
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
    state.update(overrides)
    return state

@pytest.fixture
def agent():
    """Agent with a fake LLM and retriever - no API calls."""
    agent = CustomerOperationsAgent.__new__(CustomerOperationsAgent)
    agent.prompt_mgr = PromptManager()
    agent.llm = MagicMock()
    agent.llm.generate.return_value = "LLM response"
    agent.retriever = MagicMock()
    agent.retriever.retrieve.return_value = [
        {"content": "Policy text", "source": "policy.md", "category": "accounts", "score": 0.9}
    ]
    agent.formatter = ResponseFormatter(agent.llm, agent.prompt_mgr)
    agent.workflow = agent.build_workflow()
    return agent

def test_agent_state_creation():
    """Test agent state initialization."""
    state = AgentState(
        query="Test query",
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
    assert state["query"] == "Test query"
    assert state["confidence"] == 0.0

# --- Classification ---

@pytest.mark.parametrize("llm_output, intent, confidence", [
    ("Category: KNOWLEDGE_QUERY\nConfidence: 0.95\nReasoning: policy", "KNOWLEDGE_QUERY", 0.95),
    ("Category: TOOL_REQUIRED\nConfidence: 0.9", "TOOL_REQUIRED", 0.9),
    ("Category: CLARIFICATION_NEEDED\nConfidence: .6", "CLARIFICATION_NEEDED", 0.6),
    ("Category: ESCALATION_REQUIRED\nConfidence: 0.88", "ESCALATION_REQUIRED", 0.88),
])
def test_classify_intent_parses_category_and_confidence(agent, llm_output, intent, confidence):
    agent.llm.classify.return_value = llm_output
    state = agent.classify_intent(make_state())
    assert state["intent"] == intent
    assert state["confidence"] == pytest.approx(confidence)

def test_classify_intent_sets_clarification_flag(agent):
    agent.llm.classify.return_value = "Category: CLARIFICATION_NEEDED\nConfidence: 0.7"
    state = agent.classify_intent(make_state())
    assert state["needs_clarification"] is True
    assert state["needs_escalation"] is False

def test_classify_intent_escalation_sets_reason(agent):
    agent.llm.classify.return_value = "Category: ESCALATION_REQUIRED\nConfidence: 0.9"
    state = agent.classify_intent(make_state("Why was my loan rejected?"))
    assert state["needs_escalation"] is True
    assert "rejected" in state["escalation_reason"]

def test_classify_intent_unparseable_output_fails_safe_to_escalation(agent):
    agent.llm.classify.return_value = "I'm not sure."
    state = agent.classify_intent(make_state())
    assert state["intent"] == "ESCALATION_REQUIRED"
    assert state["needs_escalation"] is True
    assert state["confidence"] == 0.0

def test_classify_intent_includes_few_shot_examples(agent):
    agent.llm.classify.return_value = "Category: KNOWLEDGE_QUERY\nConfidence: 0.9"
    agent.classify_intent(make_state("My query"))
    query, system_prompt = agent.llm.classify.call_args[0]
    assert query == "My query"
    for example in agent.prompt_mgr.prompts["classification_examples"]:
        assert f"Query: {example['query']}" in system_prompt

def test_detect_escalation_reason_matches_keyword_case_insensitively(agent):
    assert "fraud" in agent._detect_escalation_reason("I want to report FRAUD")

def test_detect_escalation_reason_fallback(agent):
    reason = agent._detect_escalation_reason("Something unusual")
    assert reason == "Request requires human review"

# --- Routing ---

@pytest.mark.parametrize("overrides, expected", [
    ({"needs_clarification": True, "intent": "CLARIFICATION_NEEDED"}, "clarify"),
    ({"needs_escalation": True, "intent": "ESCALATION_REQUIRED"}, "escalate"),
    ({"intent": "TOOL_REQUIRED"}, "invoke_tool"),
    ({"intent": "KNOWLEDGE_QUERY"}, "retrieve_knowledge"),
    ({"intent": None}, "retrieve_knowledge"),
])
def test_route_decision(agent, overrides, expected):
    assert agent.route_decision(make_state(**overrides)) == expected

def test_route_decision_clarification_takes_priority(agent):
    state = make_state(intent="TOOL_REQUIRED", needs_clarification=True, needs_escalation=True)
    assert agent.route_decision(state) == "clarify"

# --- Workflow nodes ---

def test_retrieve_knowledge_node(agent):
    state = agent.retrieve_knowledge(make_state("savings policy"))
    agent.retriever.retrieve.assert_called_once_with("savings policy", top_k=5)
    assert state["retrieved_docs"][0]["source"] == "policy.md"

@pytest.mark.parametrize("query", [
    "Where is the nearest branch?", "Branch locations in Delhi", "I want to visit you",
])
def test_invoke_tool_branch_queries(agent, query):
    state = agent.invoke_tool(make_state(query))
    assert list(state["tool_results"]) == ["branches"]
    assert state["tool_results"]["branches"]

def test_invoke_tool_product_queries(agent):
    state = agent.invoke_tool(make_state("What credit cards do you offer?"))
    assert list(state["tool_results"]) == ["products"]
    assert "credit_cards" in state["tool_results"]["products"]

def test_generate_response_with_documents_adds_citations(agent):
    docs = [{"content": "A", "source": "a.md"}, {"content": "B", "source": "a.md"},
            {"content": "C", "source": "b.md"}]
    state = agent.generate_response(make_state(retrieved_docs=docs))
    assert state["response"] == "LLM response\n\n**Sources:** a.md, b.md"
    assert state["citations"] == ["a.md", "a.md", "b.md"]

def test_generate_response_with_tool_results_has_no_citations(agent):
    state = agent.generate_response(make_state(tool_results={"branches": [{"city": "Pune"}]}))
    assert state["response"] == "LLM response"
    assert state["citations"] == []
    user_message = agent.llm.generate.call_args[0][0][1]["content"]
    assert "Pune" in user_message

def test_clarify_node(agent):
    agent.llm.generate.return_value = "Which fee do you mean?"
    state = agent.clarify(make_state("Can I get a fee waiver?"))
    assert state["clarification_question"] == "Which fee do you mean?"
    assert state["response"] == "Which fee do you mean?"

def test_escalate_node_uses_reason(agent):
    state = agent.escalate(make_state("My loan was denied", escalation_reason="Loan decision"))
    assert state["response"] == "LLM response"
    user_message = agent.llm.generate.call_args[0][0][1]["content"]
    assert "Loan decision" in user_message

def test_escalate_node_fallback_reason(agent):
    agent.escalate(make_state("Help"))
    user_message = agent.llm.generate.call_args[0][0][1]["content"]
    assert "Request requires human review" in user_message

# --- End-to-end workflow ---

def test_run_knowledge_query(agent):
    agent.llm.classify.return_value = "Category: KNOWLEDGE_QUERY\nConfidence: 0.9"
    result = agent.run("What is the minimum balance?")
    assert result["retrieved_docs"]
    assert result["citations"] == ["policy.md"]
    assert "**Sources:** policy.md" in result["response"]

def test_run_tool_query(agent):
    agent.llm.classify.return_value = "Category: TOOL_REQUIRED\nConfidence: 0.9"
    result = agent.run("Which branch is nearest?")
    assert "branches" in result["tool_results"]
    assert result["response"] == "LLM response"
    agent.retriever.retrieve.assert_not_called()

def test_run_clarification(agent):
    agent.llm.classify.return_value = "Category: CLARIFICATION_NEEDED\nConfidence: 0.6"
    result = agent.run("Can I get a waiver?")
    assert result["clarification_question"] == "LLM response"
    agent.retriever.retrieve.assert_not_called()

def test_run_escalation(agent):
    agent.llm.classify.return_value = "Category: ESCALATION_REQUIRED\nConfidence: 0.9"
    result = agent.run("I want to file a complaint")
    assert result["needs_escalation"] is True
    assert "complaint" in result["escalation_reason"]
    assert result["response"] == "LLM response"
