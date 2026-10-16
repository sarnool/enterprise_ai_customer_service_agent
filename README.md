<div align="center">

# 🏦 Enterprise AI Customer Operations Agent

### Bootcamp 1 · Building an Enterprise AI Customer Operations Agent

*A guided project for implementing an enterprise-grade AI agent that combines reasoning, knowledge retrieval, and business capabilities to support banking customer operations.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-Orchestration-1C3C3C?logo=langchain&logoColor=white)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent%20Workflow-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-412991?logo=openai&logoColor=white)](https://platform.openai.com/)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Search-0467DF)](https://github.com/facebookresearch/faiss)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Status](https://img.shields.io/badge/Status-Starter%20Solution-yellow)](#-project-status)

</div>

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Project Structure](#️-project-structure)
- [Quick Start](#-quick-start)
- [Getting Started with the Guided Lab](#-getting-started-with-the-guided-lab)
- [Technology Stack](#️-technology-stack)
- [Documentation](#-documentation)
- [Learning Objectives](#-learning-objectives)
- [What You'll Build](#-what-youll-build)
- [Testing](#-testing)
- [Project Status](#-project-status)
- [Support](#-support)
- [Next Steps](#-next-steps)

---

## 🎯 Overview

This project simulates a real-world enterprise AI implementation where you'll build an intelligent **Customer Operations Agent** for a retail bank. The agent assists customer support executives by:

| Capability | Description |
|---|---|
| 🧠 **Reasoning** | Understanding customer enquiries using LangGraph-based reasoning |
| 📚 **Knowledge Retrieval** | Retrieving relevant banking policies through RAG (Retrieval-Augmented Generation) |
| ✍️ **Grounded Responses** | Generating cited, policy-grounded answers |
| 🛠️ **Business Tools** | Invoking tools (product catalog, branch finder, eligibility checker) |
| 🤝 **Conversation Handling** | Managing clarification requests and escalation scenarios |

---

## 🏗️ Project Structure

```
AgenticAI-EnterpriseDelivery-Bootcamp1-GP_Solution/
│
├── src/                    # Source code (INCOMPLETE - Starter)
│   ├── core/               # Agent workflow and response generation
│   ├── knowledge/          # RAG components and vector database
│   ├── tools/               # Business tool integrations
│   ├── llm/                # LLM client and prompt management
│   └── utils/               # Logging, config, validation utilities
│
├── app/                    # Streamlit workbook app (Complete)
│   └── workbook_app.py     # Interactive guided lab: same
│                            # 9 activities, with live code hints and validation
│
├── data/                   # Data assets
│   ├── knowledge_base/     # Banking policy documents (20 docs)
│   ├── business_data/      # Product catalog, branches, eligibility
│   └── validation/         # Test scenarios
│
├── config/                 # Configuration files
│   ├── agent_config.yaml   # Agent workflow settings
│   ├── llm_config.yaml     # LLM parameters
│   └── prompts.yaml        # System prompts
│
├── tests/                  # Test framework
│
└── reference_solution/     # Complete implementation (Instructor only)
    └── src/                # Completed source code
```

> [!TIP]
> Everything in `src/` marked with `TODO` / `raise NotImplementedError` is what **you** implement during the guided lab. `reference_solution/` holds the completed version for comparison — try the activity yourself before peeking.

---

## 🚀 Quick Start

### Prerequisites

- 🐍 Python 3.10 or higher
- 🔑 An OpenRouter API key - on your lab desktop, double-click the **Lab Details** icon; it opens a page with your OpenRouter account's API key and a copy button

### Setup

<details open>
<summary><b>1. Install dependencies</b></summary>

```bash
pip install -r requirements.txt
```
</details>

<details open>
<summary><b>2. Configure environment</b></summary>

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and paste the API key from the Lab Details icon into OPENAI_API_KEY
```
</details>

<details>
<summary><b>3. Run the application</b></summary>

```bash
streamlit run app/workbook_app.py
```
</details>

> [!IMPORTANT]
> Run every command from the **project root** — the app resolves `data/` and `config/` paths relative to it.

---

## 📚 Getting Started with the Guided Lab

> [!NOTE]
> 👉 **Start here:** [`app/workbook_app.py`](app/workbook_app.py)

The guided workbook is an interactive Streamlit app and your one point of reference for the whole lab. It contains:

- ✅ 9 hands-on activities across 3 phases
- ✅ Business context and learning objectives
- ✅ Step-by-step implementation instructions
- ✅ A one-click Run/Validate for every activity

The exact method(s) to implement are highlighted live from your own file:

```bash
streamlit run app/workbook_app.py
```

**⏱️ Estimated completion time:** 3 hours

---

## 🛠️ Technology Stack

| Component | Technology |
|:---|:---|
| 🐍 Programming Language | Python 3.10+ |
| 🔗 AI Framework | LangChain |
| 🕸️ Workflow Orchestration | LangGraph |
| 🤖 LLM Provider | OpenAI GPT-4 |
| 🗂️ Vector Database | FAISS |
| 🧬 Embedding Model | OpenAI `text-embedding-3-small` |
| 🖥️ UI Framework | Streamlit |
| ⚙️ Configuration | YAML |

---

## 🎓 Learning Objectives

By completing this bootcamp, you will:

- [x] Design agent workflows using LangGraph for enterprise use cases
- [x] Implement Retrieval-Augmented Generation (RAG) with vector databases
- [x] Build semantic search using embeddings
- [x] Generate grounded, policy-aware responses with citations
- [x] Integrate business tools into agent workflows
- [x] Handle clarification and escalation scenarios
- [x] Work within enterprise software architecture
- [x] Apply prompt engineering for agent reasoning

---

## 🔍 What You'll Build

<table>
<tr><td width="33%" valign="top">

### Phase 1
**Enterprise AI Agent Foundation**
- LangGraph-based agent workflow
- Intent classification and routing
- Agent reasoning logic

</td><td width="33%" valign="top">

### Phase 2
**Enterprise Knowledge Integration**
- Vector knowledge base with FAISS
- RAG retrieval implementation
- Grounded response generation with citations

</td><td width="33%" valign="top">

### Phase 3
**Enterprise Enablement**
- Business tool integration (products, branches, eligibility)
- Clarification and escalation handling
- End-to-end validation

</td></tr>
</table>

---

## 🧪 Testing

Run the test suite to validate your implementation:

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=src tests/
```

---

## 📝 Project Status

**Current Status:** 🟡 Starter Solution

| Component | Status |
|:---|:---:|
| Project structure created | ✅ Done |
| Infrastructure provided (UI, utilities, config) | ✅ Done |
| Core agent logic | 🔨 To be implemented |
| RAG components | 🔨 To be implemented |
| Business tools | 🔨 To be implemented |

---

## 🤝 Support

- ✅ Reference solution available in [`reference_solution/`](reference_solution/) for comparison

---

## 📄 License

This is an educational project for the Agentic AI for Enterprise Delivery Bootcamp.

---

## 🎯 Next Steps

1. ⚙️ Follow the Quick Start above to configure your environment
2. 📓 Run `streamlit run app/workbook_app.py` to start Activity 1
3. 🚀 Begin implementing the agent workflow!

<div align="center">

**Good luck and happy coding! 🚀**

</div>
