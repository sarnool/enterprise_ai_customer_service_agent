"""
Guided Project Workbook: interactive Streamlit runner.

Reproduces Guided_Project_Workbook.ipynb as an in-browser experience: edit the
actual src/ files in your own IDE, then run each activity's validation
against them via a fresh subprocess (so results always reflect exactly
what's saved on disk, with no stale-import/kernel-state surprises). Every
script below is self-contained per activity (it rebuilds any earlier-activity
object it needs), unlike the notebook's cell-to-cell shared state, so
activities can be run in any order.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
# override=True: load_dotenv() otherwise refuses to replace an env var that's
# already set in the shell, so a stray OPENAI_API_KEY left over from some
# other project (or a global shell profile export) would silently shadow
# this project's own .env with no error, just a confusing wrong-key failure.
load_dotenv(PROJECT_ROOT / ".env", override=True)

st.set_page_config(
    page_title="Guided Project Workbook",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Streamlit's floating top toolbar (Deploy button, hamburger menu) is
       position:absolute with a very high z-index, so it renders on top of
       page content rather than pushing it down. 1.5rem was tuned against
       1.40.0's shorter toolbar; on 1.60.0 the toolbar is 60px tall and
       overlaps the first ~1.5rem of content underneath it (most visibly
       cutting through the first heading on a page, e.g. the phase-intro
       heading on an X.1 activity). 4.5rem clears it with room to spare. */
    .block-container {padding-top: 4.5rem;}
    .hero-banner {
        background: linear-gradient(120deg, #0b2545 0%, #13315c 35%, #1f6f78 70%, #13315c 100%);
        background-size: 300% 300%;
        animation: heroShift 14s ease-in-out infinite;
        border-radius: 14px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 18px rgba(11, 37, 69, 0.25);
    }
    @keyframes heroShift {
        0% {background-position: 0% 50%;}
        50% {background-position: 100% 50%;}
        100% {background-position: 0% 50%;}
    }
    @media (prefers-reduced-motion: reduce) {
        .hero-banner {animation: none;}
    }
    .hero-title {font-size: 1.7rem; font-weight: 700; color: #ffffff; margin: 0;}
    .hero-subtitle {font-size: 0.95rem; color: #cfe3ea; margin-top: 0.3rem;}
    textarea {font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace !important;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Animated agent workflow diagram (Overview → Solution Architecture tab):
# the same routing flow every activity implements a piece of, drawn as a
# live diagram instead of static ASCII art. Pure inline SVG + CSS, no JS or
# external assets, so it works the same in the sandboxed preview as anywhere
# else Streamlit renders it.
# ---------------------------------------------------------------------------

# Shared by every diagram below: one CSS block, reused per <svg> so each
# stays a single self-contained string for st.iframe (its own iframe, so
# identical class names across diagrams never collide).
WF_STYLE_BLOCK = """
<style>
    html, body {margin: 0; padding: 0; background: #ffffff;}
    .wf-line {
        stroke: #1f6f78; stroke-width: 2.5; fill: none;
        stroke-dasharray: 6 7; animation: wf-dash 1.1s linear infinite;
    }
    .wf-line-dashed {
        stroke: #4a5a6a; stroke-width: 1.5; fill: none; stroke-dasharray: 4 4;
    }
    @keyframes wf-dash { to { stroke-dashoffset: -26; } }
    .wf-node rect {
        fill: #eef3f6; stroke: #0b2545; stroke-width: 1.5; rx: 8;
        animation: wf-pulse 3.2s ease-in-out infinite;
    }
    .wf-node.wf-cross rect {
        fill: #f6f1e6; stroke: #93590b; stroke-dasharray: 5 4; animation: none;
    }
    /* Deliberately inert: used for the "single LLM call" side of the
       agentic-vs-not comparison, so the contrast with the pulsing/flowing
       agent side is visual, not just textual: one is a static pipe, the
       other is a live loop. */
    .wf-node.wf-static rect { fill: #f0f0f0; stroke: #8a8a8a; animation: none; }
    .wf-node.wf-static text { fill: #5a5a5a; }
    .wf-line-static {
        stroke: #9a9a9a; stroke-width: 2; fill: none;
    }
    .wf-node text { fill: #0b2545; font: 600 13px sans-serif; text-anchor: middle; }
    .wf-node .wf-sub { font: 400 11px sans-serif; fill: #4a5a6a; }
    .wf-label { font: 500 11px sans-serif; fill: #4a5a6a; text-anchor: middle; }
    .wf-section { font: 700 14px sans-serif; fill: #0b2545; }
    @keyframes wf-pulse {
        0%, 100% { filter: drop-shadow(0 0 0 rgba(31,111,120,0)); }
        50% { filter: drop-shadow(0 0 6px rgba(31,111,120,0.55)); }
    }
    @media (prefers-reduced-motion: reduce) {
        .wf-line { animation: none; }
        .wf-node rect { animation: none; }
    }
</style>
"""

WORKFLOW_DIAGRAM_SVG = WF_STYLE_BLOCK + """
<svg viewBox="0 0 800 560" style="width:100%; height:auto; max-width:760px; display:block; margin:0.5rem auto;">
    <defs>
        <marker id="wf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#1f6f78"/>
        </marker>
    </defs>

    <path class="wf-line" marker-end="url(#wf-arrow)" d="M400,50 L400,84"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M400,130 L400,164"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M400,210 L110,244"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M400,210 L300,244"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M400,210 L500,244"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M400,210 L690,244"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M110,290 L210,354"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M300,290 L260,354"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M250,400 L250,444"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M500,290 L500,444"/>
    <path class="wf-line" marker-end="url(#wf-arrow)" d="M690,290 L690,444"/>

    <g class="wf-node" style="animation-delay:0s">
        <rect x="320" y="10" width="160" height="40"/>
        <text x="400" y="35">Customer Query</text>
    </g>
    <g class="wf-node" style="animation-delay:0.3s">
        <rect x="290" y="90" width="220" height="40"/>
        <text x="400" y="112">classify_intent</text>
        <text class="wf-sub" x="400" y="126">Activity 1.3</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="300" y="170" width="200" height="40"/>
        <text x="400" y="192">route_decision</text>
        <text class="wf-sub" x="400" y="206">Activity 1.3</text>
    </g>

    <text class="wf-label" x="150" y="238">KNOWLEDGE_QUERY</text>
    <text class="wf-label" x="330" y="238">TOOL_REQUIRED</text>
    <text class="wf-label" x="545" y="238">CLARIFICATION_NEEDED</text>
    <text class="wf-label" x="700" y="238">ESCALATION_REQUIRED</text>

    <g class="wf-node" style="animation-delay:0.9s">
        <rect x="20" y="250" width="180" height="40"/>
        <text x="110" y="272">retrieve_knowledge</text>
        <text class="wf-sub" x="110" y="286">Activity 2.2</text>
    </g>
    <g class="wf-node" style="animation-delay:0.9s">
        <rect x="210" y="250" width="180" height="40"/>
        <text x="300" y="272">invoke_tool</text>
        <text class="wf-sub" x="300" y="286">Activity 3.1</text>
    </g>
    <g class="wf-node" style="animation-delay:0.9s">
        <rect x="410" y="250" width="180" height="40"/>
        <text x="500" y="272">clarify</text>
        <text class="wf-sub" x="500" y="286">Activity 3.2</text>
    </g>
    <g class="wf-node" style="animation-delay:0.9s">
        <rect x="600" y="250" width="180" height="40"/>
        <text x="690" y="272">escalate</text>
        <text class="wf-sub" x="690" y="286">Activity 3.2</text>
    </g>

    <g class="wf-node" style="animation-delay:1.2s">
        <rect x="115" y="360" width="270" height="40"/>
        <text x="250" y="382">generate_response</text>
        <text class="wf-sub" x="250" y="396">Activity 2.3</text>
    </g>

    <g class="wf-node" style="animation-delay:1.5s">
        <rect x="20" y="450" width="760" height="50"/>
        <text x="400" y="472">Grounded, cited response</text>
        <text class="wf-sub" x="400" y="488">back to the Customer Operations Executive</text>
    </g>
</svg>
"""

ARCHITECTURE_DIAGRAM_SVG = WF_STYLE_BLOCK + """
<svg viewBox="0 0 760 480" style="width:100%; height:auto; max-width:720px; display:block; margin:0.5rem auto;">
    <defs>
        <marker id="wf-arrow2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#1f6f78"/>
        </marker>
    </defs>

    <path class="wf-line" marker-end="url(#wf-arrow2)" d="M380,60 L380,94"/>
    <path class="wf-line" marker-end="url(#wf-arrow2)" d="M380,155 L200,194"/>
    <path class="wf-line" marker-end="url(#wf-arrow2)" d="M380,155 L560,194"/>
    <path class="wf-line" marker-end="url(#wf-arrow2)" d="M200,255 L370,299"/>
    <path class="wf-line" marker-end="url(#wf-arrow2)" d="M560,255 L390,299"/>

    <g class="wf-node" style="animation-delay:0s">
        <rect x="280" y="10" width="200" height="50"/>
        <text x="380" y="32">Presentation</text>
        <text class="wf-sub" x="380" y="48">app/workbook_app.py (this app)</text>
    </g>
    <g class="wf-node" style="animation-delay:0.3s">
        <rect x="210" y="100" width="340" height="55"/>
        <text x="380" y="124">Agent / Orchestration</text>
        <text class="wf-sub" x="380" y="140">CustomerOperationsAgent: src/core/agent_workflow.py</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="40" y="200" width="320" height="55"/>
        <text x="200" y="224">Knowledge Layer</text>
        <text class="wf-sub" x="200" y="240">src/knowledge/: RAG, chunking, embeddings, FAISS</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="400" y="200" width="320" height="55"/>
        <text x="560" y="224">Business Capability Layer</text>
        <text class="wf-sub" x="560" y="240">src/tools/: product/branch/eligibility lookups</text>
    </g>
    <g class="wf-node" style="animation-delay:0.9s">
        <rect x="230" y="305" width="300" height="55"/>
        <text x="380" y="329">LLM Integration Layer</text>
        <text class="wf-sub" x="380" y="345">src/llm/: OpenAI client + prompts</text>
    </g>
    <g class="wf-node wf-cross">
        <rect x="40" y="395" width="680" height="55"/>
        <text x="380" y="418">Cross-cutting: used by every layer above</text>
        <text class="wf-sub" x="380" y="434">config/*.yaml (prompts &amp; settings) · src/utils/ (logging, validation) · data/</text>
    </g>
</svg>
"""

AGENTIC_DIAGRAM_SVG = WF_STYLE_BLOCK + """
<svg viewBox="0 0 800 470" style="width:100%; height:auto; max-width:760px; display:block; margin:0.5rem auto;">
    <defs>
        <marker id="wf-arrow3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#1f6f78"/>
        </marker>
        <marker id="wf-arrow-static" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#9a9a9a"/>
        </marker>
    </defs>

    <text class="wf-section" x="20" y="20">A single LLM call: a straight line</text>
    <path class="wf-line-static" marker-end="url(#wf-arrow-static)" d="M180,65 L224,65"/>
    <path class="wf-line-static" marker-end="url(#wf-arrow-static)" d="M370,65 L414,65"/>
    <g class="wf-node wf-static">
        <rect x="40" y="45" width="140" height="40"/>
        <text x="110" y="70">Prompt</text>
    </g>
    <g class="wf-node wf-static">
        <rect x="230" y="45" width="140" height="40"/>
        <text x="300" y="70">LLM</text>
    </g>
    <g class="wf-node wf-static">
        <rect x="420" y="45" width="160" height="40"/>
        <text x="500" y="70">Response</text>
    </g>
    <text class="wf-label" x="400" y="108">No branching: can't look anything up, ask a question, or hand off to a human</text>

    <text class="wf-section" x="20" y="140">An AI agent: a loop that reasons first</text>

    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M400,195 L400,214"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M400,265 L107,304"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M400,265 L302,304"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M400,265 L498,304"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M400,265 L693,304"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M107,355 L280,399"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M302,355 L350,399"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M498,355 L450,399"/>
    <path class="wf-line" marker-end="url(#wf-arrow3)" d="M693,355 L520,399"/>

    <g class="wf-node" style="animation-delay:0s">
        <rect x="320" y="155" width="160" height="40"/>
        <text x="400" y="180">Query</text>
    </g>
    <g class="wf-node" style="animation-delay:0.3s">
        <rect x="230" y="215" width="340" height="50"/>
        <text x="400" y="238">Reason:</text>
        <text class="wf-sub" x="400" y="254">what does this request need?</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="20" y="305" width="175" height="50"/>
        <text x="107" y="326">look something up</text>
        <text class="wf-sub" x="107" y="342">(RAG)</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="215" y="305" width="175" height="50"/>
        <text x="302" y="332">call a tool</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="410" y="305" width="175" height="50"/>
        <text x="497" y="326">ask for</text>
        <text class="wf-sub" x="497" y="342">more info</text>
    </g>
    <g class="wf-node" style="animation-delay:0.6s">
        <rect x="605" y="305" width="175" height="50"/>
        <text x="692" y="326">hand off to</text>
        <text class="wf-sub" x="692" y="342">a human</text>
    </g>
    <g class="wf-node" style="animation-delay:0.9s">
        <rect x="20" y="400" width="760" height="50"/>
        <text x="400" y="430">Response</text>
    </g>
</svg>
"""


# ---------------------------------------------------------------------------
# Execution + file helpers
# ---------------------------------------------------------------------------

REFERENCE_PATH_PREFIX = """import sys as _sys
_sys.path.insert(0, "reference_solution")
"""


def run_snippet(code: str, timeout: int = 180, use_reference: bool = False) -> dict:
    """Run `code` in a fresh subprocess using this same interpreter, from the
    project root, so every run picks up exactly what's saved on disk right
    now, no module-cache or notebook-kernel staleness possible.

    With use_reference=True, `reference_solution` is inserted ahead of the
    project root on sys.path, so every `from src...` import in the script
    resolves to reference_solution/src instead of the participant's own
    src/, letting a stuck learner see the completed solution actually run,
    not just read its code. `config/` and `data/` paths are untouched since
    cwd stays the project root, and reference_solution/src mirrors src/'s
    package layout exactly, so no other code path needs to change."""
    code_to_run = (REFERENCE_PATH_PREFIX + code) if use_reference else code
    env = os.environ.copy()
    # Windows defaults a child process's stdout/stderr to the system codepage
    # (cp1252), which crashes on the emoji every activity script prints
    # ([WARN], ✓, ...). Force UTF-8 for the subprocess itself.
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            [sys.executable, "-c", code_to_run],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode, "timed_out": False}
    except subprocess.TimeoutExpired as e:
        return {"stdout": e.stdout or "", "stderr": e.stderr or "", "returncode": None, "timed_out": True}


def classify_run(result: dict) -> str:
    if result["timed_out"]:
        return "error"
    if result["returncode"] != 0:
        return "error"
    combined = result["stdout"] + result["stderr"]
    if "NotImplementedError" in combined or "[WARN]" in combined:
        return "warn"
    return "pass"


def read_file(rel_path: str) -> str:
    path = PROJECT_ROOT / rel_path
    if not path.exists():
        return f"# File not found: {rel_path}"
    # utf-8-sig strips a leading BOM if present (several files in src/ were
    # originally saved with one) and behaves exactly like plain utf-8
    # otherwise. Without this, ast.parse() in extract_method_source() sees
    # a literal U+FEFF character and rejects the whole file as a syntax
    # error, even though the file runs and compiles completely normally.
    return path.read_text(encoding="utf-8-sig")


if "activity_status" not in st.session_state:
    st.session_state.activity_status = {}
if "activity_output" not in st.session_state:
    st.session_state.activity_output = {}


# ---------------------------------------------------------------------------
# Activity content: mirrors Guided_Project_Workbook.ipynb section by section
# ---------------------------------------------------------------------------

ACTIVITIES = [
    dict(
        id="1.1", phase=1, title="Explore the Enterprise Solution",
        module="*No module to implement: orientation activity*",
        business_context="""Before writing any code, an enterprise AI engineer needs to understand the system they're extending: what already works, what's stubbed out, and how the pieces fit together. Jumping straight into implementation without this context is how enterprise features end up inconsistent with the rest of the codebase.""",
        objective="Ground the layered architecture from the Solution Architecture section in the actual repository, then become familiar with the project structure and the starter application.",
        instructions="""1. Skim the project tree and match each folder to its layer: `src/core/` (Agent/Orchestration, you'll implement this), `src/knowledge/` (Knowledge layer), `src/tools/` (Business Capability layer), `src/llm/` (LLM Integration, already complete), `app/` (Presentation, already complete), `config/` and `src/utils/` (cross-cutting), `data/` (Data layer), `reference_solution/` (instructor/self-check only, avoid looking unless you're stuck).
2. Open `config/agent_config.yaml` and `config/prompts.yaml` and skim them: you'll be reading from both throughout this lab instead of hardcoding values.
3. Scroll down and click **Run Activity 1.1** below to see a live orientation scan of the codebase: this is the same run-and-check pattern you'll use to validate every activity in this lab.""",
        ai_assist="**AI Assist:** Ask your AI coding assistant to summarize what a given `src/` module is responsible for before you start implementing it: it's a fast way to build context on unfamiliar code.",
        files=[],
        reference_only_files=["config/agent_config.yaml", "config/prompts.yaml"],
        milestone="You can explain the enterprise architecture and locate every module you'll implement in this lab.",
        validation="""Confirm that the scan lists 7 modules with TODO markers and stub methods, all under `src/core/`, `src/knowledge/`, and `src/tools/`: everything else in `src/` (`utils/`, `llm/`, `embeddings.py`) is already complete, and `config/*.yaml` is externalized rather than hardcoded. This is the layered architecture from the Solution Architecture section, visible in the scan itself: `agent_workflow.py` (Agent/Orchestration layer) spans Phases 1 and 3, `knowledge_base.py`/`retriever.py` (Knowledge layer) belong to Phase 2, and the `tools/` modules (Business Capability layer) belong to Phase 3. Every module you implement sits in exactly one layer, and never reaches into another layer's job.""",
        # This script only scans src/ for TODOs; it never touches a stub
        # method, so it "passes" the same whether 0% or 100% of the lab is
        # done. The generic "All checks passed" label (used everywhere
        # else, where a run genuinely does exercise the participant's code)
        # would misleadingly imply this one verified something it didn't.
        pass_label="Orientation scan complete: nothing to implement here yet",
        script="""from pathlib import Path

def scan_todos(base="src"):
    summary = []
    for py_file in sorted(Path(base).rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        todo_count = text.count("TODO")
        raises = text.count("raise NotImplementedError")
        if todo_count or raises:
            summary.append((str(py_file), todo_count, raises))
    return summary

todos = scan_todos()
print(f"{'Module':<45}{'TODO markers':<15}{'Stub methods'}")
print("-" * 70)
for path, todo_count, raises in todos:
    print(f"{path:<45}{todo_count:<15}{raises}")

print(f"\\n✓ {len(todos)} modules contain implementation work for you across this lab.")
print("  Everything else in src/ (utils/, llm/, embeddings.py) is already complete, use it as-is.")
""",
    ),
    dict(
        id="1.2", phase=1, title="Build the Agent Workflow",
        module="`src/core/agent_workflow.py`",
        business_context="""Every customer request an executive handles needs to go through a consistent process: understand the request, decide how to handle it, and produce a response. Without a structured workflow, that logic ends up scattered and inconsistent across the application. LangGraph lets you express this as an explicit state machine, a graph of nodes and edges, so the agent's behaviour is predictable, testable, and easy to extend later.""",
        objective="Wire up the `CustomerOperationsAgent`'s dependencies and build a compiled LangGraph workflow with all the nodes and routing edges the rest of this lab will implement.",
        concept_overview="""A LangGraph `StateGraph` is built from:
- **State**: a shared dictionary (here, `AgentState`) that flows through every node, already defined for you in `src/core/agent_state.py`.
- **Nodes**: functions that take the state and return an updated state (e.g. `classify_intent`, `retrieve_knowledge`).
- **Edges**: connections between nodes. A **conditional edge** picks the next node dynamically based on a routing function's return value, instead of always going to the same place.

Building the graph only *registers* these nodes and edges; it doesn't execute any of them. That means you can compile the full graph now, even though most of the node methods you're wiring in (`retrieve_knowledge`, `invoke_tool`, `generate_response`, `clarify`, `escalate`) still raise `NotImplementedError`. You'll implement each one in a later activity.""",
        instructions="""`__init__` is already wired for you: it constructs `self.llm`, `self.prompt_mgr`, `self.kb`, `self.retriever`, `self.formatter`, and tries to load a cached index. Your work is the graph itself:
1. Finish `__init__` by calling `self.workflow = self.build_workflow()`.
2. Implement `build_workflow()`. The `StateGraph` and the `classify_intent` node are registered for you as an example. Register the remaining five nodes named in its docstring, set `classify_intent` as the entry point, add a conditional edge from `classify_intent` using `self.route_decision`, connect `retrieve_knowledge` and `invoke_tool` to `generate_response`, connect `generate_response`, `clarify`, and `escalate` to `END`, then compile and return the graph.

This works even though most nodes still raise `NotImplementedError`; a `StateGraph` separates *structure* from *behaviour*, so you can validate the structure now. (`run()`, the method that actually executes the compiled graph, is pre-implemented for you, same as `__init__`'s dependency wiring - calling `.invoke()` isn't a new concept this lab is teaching, so it's provided rather than left as a TODO.)""",
        ai_assist="**AI Assist:** Ask your AI coding assistant to explain the difference between `add_edge` and `add_conditional_edges` in LangGraph before you write the routing logic: you'll need both.",
        files=["src/core/agent_workflow.py"],
        target_methods={"src/core/agent_workflow.py": ["__init__", "build_workflow"]},
        milestone="The AI agent successfully constructs and its workflow graph compiles with all expected nodes and routing in place.",
        validation="""Confirm that:
- `agent` was constructed without raising an exception
- `agent.workflow` is a compiled graph (not `None`)
- All six expected nodes appear in the graph

This works even though `retrieve_knowledge`, `invoke_tool`, `generate_response`, `clarify`, and `escalate` still raise `NotImplementedError`; a `StateGraph` separates **structure** (which nodes exist, how they connect) from **behaviour** (what each node does), so you can validate the structure now and implement each node's behaviour in a later activity.""",
        script="""from src.core.agent_workflow import CustomerOperationsAgent

try:
    agent = CustomerOperationsAgent()
except NotImplementedError as e:
    agent = None
    print(f"[WARN] Task 1.2 not yet implemented: {e}")
    print("   Implement CustomerOperationsAgent.__init__() and build_workflow() in src/core/agent_workflow.py")

if agent is not None:
    if agent.workflow is None:
        print("[WARN] agent.workflow is None, make sure __init__ calls self.build_workflow().")
    else:
        graph_nodes = list(agent.workflow.get_graph().nodes.keys())
        print(f"✓ Agent constructed successfully: {type(agent).__name__}")
        print(f"✓ Workflow compiled: {type(agent.workflow).__name__}")
        print(f"✓ Graph nodes ({len(graph_nodes)}): {graph_nodes}")

        expected_nodes = {"classify_intent", "retrieve_knowledge", "invoke_tool",
                           "generate_response", "clarify", "escalate"}
        missing_nodes = expected_nodes - set(graph_nodes)
        if missing_nodes:
            print(f"[WARN] Missing expected nodes: {missing_nodes}")
        else:
            print("✓ All expected nodes are registered in the graph.")
""",
    ),
    dict(
        id="1.3", phase=1, title="Implement Agent Reasoning",
        module="`src/core/agent_workflow.py`",
        business_context="""Not every customer message should be handled the same way. "What documents do I need to open a savings account?" is a knowledge lookup. "Which branch is closest to Mumbai Central?" needs a business tool. "Can I get a fee waiver?" is too ambiguous to answer safely. "Why was my loan application rejected?" is a compliance-sensitive issue that belongs with a human. The agent has to tell these apart *before* it can decide what to do next.""",
        objective="Implement intent classification and routing so the agent can analyze a customer request and decide which path through the workflow to take.",
        concept_overview="""`classify_intent` doesn't decide anything itself: the decision comes entirely from `config/prompts.yaml`'s `classification_prompt`, which `self.llm.classify()` sends to the model. Open that prompt and notice three prompt engineering patterns doing the actual work:
- **System/user separation**: the system message fixes the model's *role* (an intent classifier with four fixed categories); the user template carries only the *query*. The role never varies per request, so it belongs in the system message, not re-stated every call.
- **Few-shot examples**: `classification_examples` shows one worked case per category. This is what teaches the model the category *boundaries* (e.g. why a branch-location question is `TOOL_REQUIRED`, not `KNOWLEDGE_QUERY`) far more reliably than the category names alone.
- **A forced output format**: the prompt demands `Category: / Confidence: / Reasoning:` on fixed lines. That's not a formatting nicety; it's what makes `classify_intent`'s simple substring parsing reliable at all. A free-form response would be far harder to parse safely.

`classify_intent` calls the LLM with this prompt and parses the category out of the response; `route_decision` then maps the resulting state onto the name of the next node to run.""",
        instructions="""`classify_intent` already fetches `classification_prompt` for you: the model call and the decision logic are yours to write:
1. Implement `classify_intent()`: call `self.llm.classify(state["query"], prompt["system"])`, and parse the result into `state["intent"]` / `state["confidence"]`, setting `state["needs_clarification"]` or `state["needs_escalation"]` where appropriate.
2. Implement `_detect_escalation_reason()`: for escalations, `classify_intent` calls this to set a short `state["escalation_reason"]`. Load `agent_config.yaml` and check the query against `routing.escalation_keywords`.
3. Implement `route_decision()`: return `"clarify"`, `"escalate"`, `"invoke_tool"`, or `"retrieve_knowledge"` based on the state fields you set above.

**Try it yourself:** `classification_prompt` lives in `config/prompts.yaml`, not hardcoded in Python. Add one new entry to its `classification_examples` (e.g. a card-fee question should be `KNOWLEDGE_QUERY`, not `TOOL_REQUIRED`), save, and re-run: the script always reflects whatever is currently on disk.""",
        ai_assist="**AI Assist:** Use your AI coding assistant to draft the string-matching logic against the LLM's classification output, but check it against the four worked examples below yourself: an assistant can't tell you whether \"TOOL_REQUIRED\" appearing in the text was actually intentional or a coincidence.",
        files=["src/core/agent_workflow.py", "config/prompts.yaml"],
        target_methods={"src/core/agent_workflow.py": ["classify_intent", "_detect_escalation_reason", "route_decision"]},
        milestone="The AI agent can reason about incoming customer requests, and you can change that reasoning by editing a prompt: no code change required.",
        validation="""Review the table above - the script now checks `route_decision`'s actual return value for you, it isn't just eyeballing:
- Each query's **Classified** intent should reasonably match its **Expected** intent (the LLM won't always match exactly; that's fine, as long as the routing decision is sensible)
- The `ESCALATION_REQUIRED` row should include an `escalation_reason` referencing a keyword from `agent_config.yaml`
- **Routed to** is marked ✓ or ✗ against `route_decision`'s own documented mapping: `KNOWLEDGE_QUERY` → `retrieve_knowledge`, `TOOL_REQUIRED` → `invoke_tool`, `CLARIFICATION_NEEDED` → `clarify`, `ESCALATION_REQUIRED` → `escalate`. Any ✗ means `route_decision` isn't implemented correctly, even if it didn't raise an error.

Notice that `route_decision` checks `needs_clarification` and `needs_escalation` *before* `state["intent"]`: a query that's both `TOOL_REQUIRED` and flagged for escalation should still go to a human, not to a tool call.""",
        script="""from src.core.agent_workflow import CustomerOperationsAgent
from src.core.agent_state import AgentState

try:
    agent = CustomerOperationsAgent()
except NotImplementedError as e:
    agent = None
    print(f"[WARN] Cannot run: Activity 1.2 not complete yet ({e})")

sample_queries = [
    ("What documents do I need to open a savings account?", "KNOWLEDGE_QUERY"),
    ("Which branch is closest to Mumbai Central?", "TOOL_REQUIRED"),
    ("Can I get a fee waiver?", "CLARIFICATION_NEEDED"),
    ("Why was my loan application rejected?", "ESCALATION_REQUIRED"),
]

def expected_route(state):
    # Mirrors route_decision()'s own documented spec, so this check verifies
    # actual behaviour, not just whether it happened to avoid raising.
    if state.get("needs_clarification"):
        return "clarify"
    if state.get("needs_escalation"):
        return "escalate"
    if state.get("intent") == "TOOL_REQUIRED":
        return "invoke_tool"
    return "retrieve_knowledge"

if agent is None:
    print("[WARN] Cannot proceed: agent not available. Complete Activity 1.2 first.")
else:
    print(f"{'Query':<55}{'Expected':<22}{'Classified':<22}{'Routed to'}")
    print("-" * 110)
    all_routes_ok = True
    try:
        for query, expected in sample_queries:
            state = AgentState(
                query=query, intent=None, confidence=0.0, retrieved_docs=[],
                tool_results=None, response=None, citations=[],
                needs_clarification=False, needs_escalation=False,
                clarification_question=None, escalation_reason=None
            )
            state = agent.classify_intent(state)
            next_node = agent.route_decision(state)
            wanted_route = expected_route(state)
            route_ok = next_node == wanted_route
            all_routes_ok = all_routes_ok and route_ok
            marker = "✓" if state["intent"] == expected else "≈"
            route_marker = "✓" if route_ok else "✗"
            routed_display = f"{route_marker} {next_node}" if route_ok else f"{route_marker} {next_node} (expected {wanted_route})"
            print(f"{marker} {query[:50]:<53}{expected:<22}{str(state['intent']):<22}{routed_display}")
            if state.get("escalation_reason"):
                print(f"    escalation_reason: {state['escalation_reason']}")
        if not all_routes_ok:
            print()
            print("[WARN] route_decision() returned the wrong node for at least one query above - check the (expected ...) hints.")
    except NotImplementedError as e:
        print(f"[WARN] Task 1.3 not yet implemented: {e}")
        print("   Implement classify_intent() and route_decision() in src/core/agent_workflow.py")
""",
    ),
    dict(
        id="2.1", phase=2, title="Prepare the Enterprise Knowledge Base",
        module="`src/knowledge/knowledge_base.py`",
        business_context="""The 20 banking policy documents under `data/knowledge_base/` are the agent's single source of truth for grounded answers, but an LLM can't search raw Markdown files directly. To make them searchable, you need to chunk them into retrievable pieces, convert each chunk into a vector embedding, and index those vectors for fast similarity search.""",
        objective="Load and chunk the knowledge base documents, embed them, and build a FAISS vector index, then cache it to disk so it isn't rebuilt (and re-billed against the embedding API) every time this runs.",
        concept_overview="""**Chunking:** Documents are split into overlapping windows (`chunk_size=1000`, `chunk_overlap=200` per `agent_config.yaml`) so that a single chunk is small enough to embed meaningfully but still has enough surrounding context to be useful on its own. The sliding-window chunking algorithm (`_chunk_text`) is provided for you: it's string-slicing mechanics, not the RAG concept this activity is about.

**Indexing:** `KnowledgeBase.build_index()` embeds every chunk with `EmbeddingGenerator` (already implemented for you) and adds the vectors to a `faiss.IndexFlatL2` index, alongside the original documents so retrieval can map a matched vector back to its source text and filename.

**Caching:** Building the index costs one embedding API call per chunk. `save_index()` / `load_index()` persist the index to `INDEX_PATH` (imported from `src.core.agent_workflow`, backed by the `VECTOR_DB_PATH` environment variable) so it only needs to be built once.""",
        instructions="""1. Implement `load_documents()`: walk `data/knowledge_base/` for `.md` files, call the provided `self._chunk_text()` on each one's contents, and return a list of `{content, source, category, chunk_id}` dictionaries, one per chunk.
2. Implement `build_index()`: `self.documents` and the extracted `texts` are set up for you. Embed `texts`, create a `faiss.IndexFlatL2(self.dimension)`, and add the embeddings to it.
3. Implement `save_index()` and `load_index()` to persist/restore both the FAISS index and `self.documents` (the parent directory is already created for you in `save_index()`).""",
        ai_assist="**AI Assist:** Ask your AI coding assistant for a simple sliding-window chunking function: this doesn't need to be sophisticated for this lab, just consistent.",
        files=["src/knowledge/knowledge_base.py"],
        target_methods={"src/knowledge/knowledge_base.py": ["load_documents", "build_index", "save_index", "load_index"]},
        milestone="Enterprise knowledge has been successfully chunked, embedded, and indexed for semantic retrieval.",
        validation="""Confirm that:
- Roughly 60-100 chunks were produced from the 20 source documents (exact count depends on your chunking)
- The FAISS index's vector count matches the number of chunks
- An index cache file now exists under the path printed above: re-running this should now print "Loaded cached index" instead of rebuilding

Persisting the index to disk like this turns an expensive one-time operation (embedding every chunk) into a reusable enterprise asset, rather than something recomputed on every agent startup.""",
        script="""from src.knowledge.knowledge_base import KnowledgeBase
from src.core.agent_workflow import INDEX_PATH
from pathlib import Path

# Raised when your code runs but returns something other than what this activity expects.
class CheckFailed(Exception):
    pass

kb = KnowledgeBase()
cached = Path(f"{INDEX_PATH}.index").exists()

try:
    if cached:
        kb.load_index(INDEX_PATH)
        print(f"✓ Loaded cached index from {INDEX_PATH} ({len(kb.documents)} chunks), skipping rebuild.")
    else:
        documents = kb.load_documents("data/knowledge_base")
        if documents is None:
            raise CheckFailed("load_documents() returned None")
        print(f"✓ Loaded and chunked {len(documents)} document chunks from data/knowledge_base")

        kb.build_index(documents)
        if kb.index is None:
            raise CheckFailed("build_index() did not set self.index")
        print(f"✓ Built FAISS index with {kb.index.ntotal} vectors")

        kb.save_index(INDEX_PATH)
        if not Path(f"{INDEX_PATH}.index").exists():
            raise CheckFailed("save_index() did not write an index file to disk")
        print(f"✓ Saved index to {INDEX_PATH} for reuse in later activities and the Streamlit portal")

    # load_index() is a target method for this activity too, but the branches
    # above only call it on a second run (once a cache already exists) -
    # round-trip through a fresh instance so it's verified on every run.
    reloaded = KnowledgeBase()
    reloaded.load_index(INDEX_PATH)
    if reloaded.index is None or reloaded.index.ntotal != kb.index.ntotal:
        raise CheckFailed("load_index() did not restore the index correctly")
    print(f"✓ Verified load_index() restores {reloaded.index.ntotal} vectors correctly")
except NotImplementedError as e:
    print(f"[WARN] Task 2.1 not yet implemented: {e}")
    print("   Implement load_documents(), build_index(), save_index(), and load_index() in src/knowledge/knowledge_base.py")
except CheckFailed as e:
    print(f"[WARN] Task 2.1 check failed: {e}")
    print("   Your code ran without errors, but didn't produce the expected result. Re-read the method's docstring in src/knowledge/knowledge_base.py")
""",
    ),
    dict(
        id="2.2", phase=2, title="Integrate Enterprise Knowledge Retrieval",
        module="`src/knowledge/retriever.py`",
        business_context="""Having an index isn't useful on its own: the agent needs to turn a customer's question into a search over that index and get back the most relevant policy text, not just the closest match regardless of quality.""",
        objective="Implement semantic retrieval: embed the customer's query, search the FAISS index, and return only the documents that clear a similarity threshold.",
        instructions="""1. Implement `retrieve()` in `Retriever`: generate a query embedding, search `self.kb.index` for the top `top_k` matches, convert FAISS's L2 distance to a similarity score (`score = 1 / (1 + distance)`), filter out anything below `threshold`, and return the matches formatted as `{content, source, category, score}`.

Try lowering `threshold` to `0.0` and re-running to see the effect of the filter.""",
        ai_assist="**AI Assist:** Ask your AI coding assistant to explain why `score = 1 / (1 + distance)` is a reasonable way to turn an L2 distance into a 0-1 similarity score: understanding the conversion matters more than memorizing the formula.",
        files=["src/knowledge/retriever.py"],
        target_methods={"src/knowledge/retriever.py": ["retrieve"]},
        milestone="The AI agent retrieves relevant banking policies and operational procedures for customer queries.",
        validation="""For each query, confirm that:
- At least one document is retrieved
- The retrieved source filename is topically related to the query (e.g. the debit card query should surface `lost_stolen_card_procedures.md`)
- Similarity scores are between 0 and 1, with the top result having the highest score

Try lowering `threshold` to `0.0` and re-running: filtering by similarity threshold is what lets the agent later recognize "I don't have information about that" instead of forcing an answer from an unrelated document, so a threshold that's too low trades away that precision.""",
        script="""from pathlib import Path
from src.knowledge.knowledge_base import KnowledgeBase
from src.knowledge.retriever import Retriever
from src.core.agent_workflow import INDEX_PATH

kb = KnowledgeBase()
try:
    if Path(f"{INDEX_PATH}.index").exists():
        kb.load_index(INDEX_PATH)
    else:
        documents = kb.load_documents("data/knowledge_base")
        kb.build_index(documents)
        kb.save_index(INDEX_PATH)
except NotImplementedError as e:
    print(f"[WARN] Cannot proceed: Activity 2.1 not complete yet ({e})")
    kb = None

if kb is None or kb.index is None:
    print("[WARN] Cannot proceed: knowledge base not indexed. Complete Activity 2.1 first.")
else:
    retriever = Retriever(kb)
    test_queries = [
        "What documents do I need to open a savings account?",
        "How do I report a lost debit card?",
        "What is the interest rate on personal loans?",
    ]
    try:
        retrieval_ok = True
        for query in test_queries:
            results = retriever.retrieve(query, top_k=3)
            print(f"Query: {query}")
            if not results:
                print("  (no results, check your similarity threshold or index)")
                retrieval_ok = False
            for r in results:
                score = r.get("score")
                score_ok = isinstance(score, (int, float)) and 0 <= score <= 1
                if score_ok:
                    score_display = f"{score:.3f}"
                else:
                    retrieval_ok = False
                    score_display = f"{score} [WARN] out of [0,1] range"
                print(f"  [{score_display}] {r['source']} ({r['category']}): {r['content'][:80].strip()}...")
            print()
        if not retrieval_ok:
            print("[WARN] retrieve() returned no results (or an out-of-range score) for at least one query above.")
    except NotImplementedError as e:
        print(f"[WARN] Task 2.2 not yet implemented: {e}")
        print("   Implement retrieve() in src/knowledge/retriever.py")
""",
    ),
    dict(
        id="2.3", phase=2, title="Generate Grounded Enterprise Responses",
        module="`src/core/response_formatter.py`",
        business_context="""Retrieved documents are just raw text snippets: a customer operations executive needs a coherent, professional answer that's clearly grounded in the bank's actual policies, with sources they (and the customer) can verify.""",
        objective="Turn retrieved documents into a grounded response with citations, using the `response_generation_prompt` from `config/prompts.yaml`.",
        instructions="""`format_grounded_response()` already fetches `response_generation_prompt` for you:
1. Implement `format_grounded_response()`: build a `knowledge` string, call `self.llm.generate()` with the formatted prompt, and append citations to the response text. This node is shared by both the `retrieve_knowledge` path (Phase 2) and the `invoke_tool` path (Phase 3) - if `state["retrieved_docs"]` is non-empty, build `knowledge` from that; otherwise, if `state.get("tool_results")`, ground from that instead (e.g. `json.dumps(state["tool_results"], indent=2)`, no truncation - the catalog/branch data is ~15-19KB, trivial for the model's context window, and cutting it off can silently drop the entry the query is actually about before the model ever sees it). Skipping the tool-results case means every `TOOL_REQUIRED` query gets a generic "I don't have that information" response even though `invoke_tool()` already fetched the real answer.
2. Implement `extract_citations()`: pull the `source` field out of each retrieved document.

Note that `ResponseFormatter.__init__(self, llm, prompt_mgr)` is already implemented for you: it's simple constructor wiring, not part of this activity's learning objective. The `generate_response` graph node that calls both methods above is pre-implemented too, same reasoning - wiring two already-implemented calls together isn't a new concept.""",
        ai_assist="**AI Assist:** Ask your AI coding assistant to draft the citation formatting, but check it produces the `[Source: Document Name, Section]` style specified in the `response_generation_prompt`'s system message.",
        files=["src/core/response_formatter.py"],
        target_methods={"src/core/response_formatter.py": ["format_grounded_response", "extract_citations"]},
        milestone="The AI agent generates grounded responses with appropriate source citations.",
        validation="""Confirm that:
- The response directly answers the query using information that could plausibly come from the retrieved documents
- The response includes source citations (either inline or as a "Sources" list), so a customer operations executive (or a compliance reviewer) can trace every claim back to a specific policy document
- `citations` is a non-empty list of document filenames

Check `config/prompts.yaml`'s `no_knowledge_template`: if `state["retrieved_docs"]` were empty, does your implementation fall back to it, or would it currently ask the LLM to answer from nothing?""",
        script="""from pathlib import Path
from src.core.agent_workflow import CustomerOperationsAgent, INDEX_PATH
from src.core.response_formatter import ResponseFormatter
from src.core.agent_state import AgentState
from src.knowledge.knowledge_base import KnowledgeBase
from src.knowledge.retriever import Retriever

# Raised when your code runs but returns something other than what this activity expects.
class CheckFailed(Exception):
    pass

try:
    agent = CustomerOperationsAgent()
except NotImplementedError as e:
    agent = None
    print(f"[WARN] Cannot proceed: Activity 1.2 not complete yet ({e})")

retriever = None
if agent is not None:
    kb = KnowledgeBase()
    try:
        if Path(f"{INDEX_PATH}.index").exists():
            kb.load_index(INDEX_PATH)
        else:
            documents = kb.load_documents("data/knowledge_base")
            kb.build_index(documents)
            kb.save_index(INDEX_PATH)
        retriever = Retriever(kb)
    except NotImplementedError as e:
        print(f"[WARN] Cannot proceed: Activity 2.1 not complete yet ({e})")

if agent is None or retriever is None:
    print("[WARN] Cannot proceed: agent or retriever not available. Complete Activities 1.2 and 2.1 first.")
else:
    formatter = ResponseFormatter(agent.llm, agent.prompt_mgr)
    query = "What documents do I need to open a savings account?"
    try:
        retrieved_docs = retriever.retrieve(query, top_k=3)
    except NotImplementedError as e:
        print(f"[WARN] Task 2.2 not yet implemented: {e}")
        retrieved_docs = []

    state = AgentState(
        query=query, intent="KNOWLEDGE_QUERY", confidence=0.9,
        retrieved_docs=retrieved_docs,
        tool_results=None, response=None, citations=[],
        needs_clarification=False, needs_escalation=False,
        clarification_question=None, escalation_reason=None
    )

    try:
        response = formatter.format_grounded_response(state)
        citations = formatter.extract_citations(state["retrieved_docs"])
        if response is None:
            raise CheckFailed("format_grounded_response() returned None")
        if state["retrieved_docs"] and not citations:
            raise CheckFailed("extract_citations() returned an empty list despite non-empty retrieved_docs")

        print(f"Query: {query}")
        print("=" * 70)
        print("GROUNDED RESPONSE")
        print("=" * 70)
        print(response)
        print("\\nCitations:", citations)
    except NotImplementedError as e:
        print(f"[WARN] Task 2.3 not yet implemented: {e}")
        print("   Implement format_grounded_response() and extract_citations() in src/core/response_formatter.py")
    except CheckFailed as e:
        print(f"[WARN] Task 2.3 check failed: {e}")
        print("   Your code ran without errors, but didn't produce the expected result. Make sure both methods in src/core/response_formatter.py return a value")
""",
    ),
    dict(
        id="3.1", phase=3, title="Integrate Business Tools",
        module="`src/tools/product_tools.py`, `src/tools/branch_tools.py`, `src/tools/eligibility_tools.py`, `src/core/agent_workflow.py`",
        business_context="""Not every customer question can be answered from policy documents. "What credit cards do you offer?" and "Which branch in Bangalore offers forex services?" need structured, up-to-date business data, not free-text retrieval. `agent_config.yaml` already lists three available tools (`get_product_catalog`, `find_branch_info`, `check_eligibility`); this activity implements them.""",
        objective="Implement the three business tool functions, then extend `invoke_tool` so the agent can call the right one for a `TOOL_REQUIRED` query.",
        concept_overview="""**Scope for this activity:** given the 3-hour lab, `invoke_tool` uses a simple keyword check on the query (e.g. "branch", "nearest", "visit" → branch lookup; otherwise → product catalog) rather than a second LLM call to select and fill in tool arguments. `check_eligibility` needs structured inputs (a product name and a customer profile) that don't come from free text, so you'll implement and test it directly rather than wiring it into the live conversational flow: a full slot-filling flow for eligibility is a natural extension beyond this lab, not a requirement of it.""",
        instructions="""Each tool function already loads its JSON file for you: your work is the filtering/matching logic:
1. Implement `get_product_catalog()` in `product_tools.py`: optionally filter the loaded `catalog` by `category`.
2. Implement `find_branch_info()` in `branch_tools.py`: optionally filter the loaded `branches` by `city` and/or `service`.
3. Implement `check_eligibility()` in `eligibility_tools.py`: match `product_type` inside the loaded `rules`, and check `customer_data` against its requirements (e.g. `min_age`).
4. Implement `invoke_tool()` in `agent_workflow.py`: the imports and `query_lower` are set up for you. Branch on keywords in `query_lower` to call `find_branch_info()` or `get_product_catalog()`, and store the result in `state["tool_results"]`.

`check_eligibility` is tested directly here; it isn't wired into `invoke_tool` since it needs structured inputs that don't come from free text.""",
        ai_assist="**AI Assist:** Ask your AI coding assistant to draft the filter conditions, but check each one actually matches the JSON structure in `data/business_data/`: a plausible-looking filter can silently match nothing.",
        files=["src/tools/product_tools.py", "src/tools/branch_tools.py", "src/tools/eligibility_tools.py", "src/core/agent_workflow.py"],
        target_methods={
            "src/tools/product_tools.py": ["get_product_catalog"],
            "src/tools/branch_tools.py": ["find_branch_info"],
            "src/tools/eligibility_tools.py": ["check_eligibility"],
            "src/core/agent_workflow.py": ["invoke_tool"],
        },
        milestone="The AI agent can invoke a business tool and incorporate the results into its response.",
        validation="""Confirm that:
- All three tool functions return real data (not `None` or an exception)
- The product query's `tool_results` contains a `"products"` key
- The branch query's `tool_results` contains a `"branches"` key: routed differently from the product query because of the keyword check

`agent_config.yaml` lists `check_eligibility` as an available tool, but `invoke_tool` doesn't call it: it needs a `product_type` and a `customer_data` profile that don't come from free text, so a scoped keyword heuristic is enough for the other two tools without needing a second LLM call to fill in arguments.""",
        script="""from src.tools.product_tools import get_product_catalog
from src.tools.branch_tools import find_branch_info
from src.tools.eligibility_tools import check_eligibility

try:
    catalog = get_product_catalog()
    print(f"✓ get_product_catalog(): {list(catalog.keys())}")

    branches = find_branch_info(city="Mumbai")
    print(f"✓ find_branch_info(city='Mumbai'): {len(branches)} branch(es) found")

    eligibility = check_eligibility("Personal Loan", {"age": 28})
    print(f"✓ check_eligibility('Personal Loan', {{'age': 28}}): {eligibility}")
except NotImplementedError as e:
    print(f"[WARN] Task 3.1 not yet implemented: {e}")
    print("   Implement get_product_catalog(), find_branch_info(), and check_eligibility()")
    print("   in src/tools/product_tools.py, src/tools/branch_tools.py, and src/tools/eligibility_tools.py")

print()
print("--- invoke_tool routing ---")
from src.core.agent_workflow import CustomerOperationsAgent
from src.core.agent_state import AgentState

# Raised when your code runs but returns something other than what this activity expects.
class CheckFailed(Exception):
    pass

def make_state(query):
    return AgentState(
        query=query, intent="TOOL_REQUIRED", confidence=0.85, retrieved_docs=[],
        tool_results=None, response=None, citations=[],
        needs_clarification=False, needs_escalation=False,
        clarification_question=None, escalation_reason=None
    )

try:
    tool_agent = CustomerOperationsAgent()
    product_state = tool_agent.invoke_tool(make_state("What credit cards do you offer?"))
    product_keys = list((product_state.get("tool_results") or {}).keys())
    print("Product query tool_results keys:", product_keys)
    branch_state = tool_agent.invoke_tool(make_state("Which branch in Bangalore offers forex services?"))
    branch_keys = list((branch_state.get("tool_results") or {}).keys())
    print("Branch query tool_results keys:", branch_keys)
    if "products" not in product_keys:
        raise CheckFailed("invoke_tool() did not route the product query to get_product_catalog() (no 'products' key)")
    if "branches" not in branch_keys:
        raise CheckFailed("invoke_tool() did not route the branch query to find_branch_info() (no 'branches' key)")
except NotImplementedError as e:
    print(f"[WARN] invoke_tool() not yet implemented: {e}")
    print("   Implement invoke_tool() in src/core/agent_workflow.py")
except CheckFailed as e:
    print(f"[WARN] invoke_tool() check failed: {e}")
    print("   invoke_tool() ran, but stored the wrong key: use {'branches': ...} for branch/location queries and {'products': ...} otherwise")
""",
    ),
    dict(
        id="3.2", phase=3, title="Handle Enterprise Conversation Scenarios",
        module="`src/core/agent_workflow.py`",
        business_context="""Real customer conversations aren't always clean knowledge lookups or tool calls. "Can I get a fee waiver?" doesn't say which fee. "Why was my loan application rejected?" touches a compliance-sensitive decision that a bank should not let an LLM answer unsupervised. An enterprise agent needs to recognize both situations and respond appropriately: asking a clarifying question in one case, and handing off to a human in the other, rather than guessing.""",
        objective="Implement the `clarify` and `escalate` nodes using the corresponding prompts already defined in `config/prompts.yaml`.",
        instructions="""Both `clarify()` and `escalate()` already fetch their prompt for you: build the call and store the result:
1. Implement `clarify()`: call `self.llm.generate()` with `state["query"]` formatted into `clarification_prompt`'s `user_template`, and store the result in both `state["clarification_question"]` and `state["response"]`.
2. Implement `escalate()`: call `self.llm.generate()` with `state["query"]` and `state.get("escalation_reason")` formatted into `escalation_prompt`'s `user_template`, and store the result in `state["response"]`.""",
        ai_assist="**AI Assist:** Ask your AI coding assistant why using the same `LLMClient.generate()` pattern here (rather than hardcoding a fixed string) makes these responses easier to tune later: a prompt change in `prompts.yaml` should be enough to adjust tone without touching code.",
        files=["src/core/agent_workflow.py"],
        target_methods={"src/core/agent_workflow.py": ["clarify", "escalate"]},
        milestone="The AI agent responds appropriately to incomplete, ambiguous, and unsupported customer requests.",
        validation="""Confirm that:
- The clarification response asks a specific follow-up question rather than answering the ambiguous query
- The escalation response acknowledges the request will be handed to a human, without attempting to explain the loan rejection itself: even if the LLM technically "knows" a plausible-sounding answer, escalation means recognizing a limit, not working around it""",
        script="""from src.core.agent_workflow import CustomerOperationsAgent
from src.core.agent_state import AgentState

# Raised when your code runs but returns something other than what this activity expects.
class CheckFailed(Exception):
    pass

try:
    conv_agent = CustomerOperationsAgent()

    clarify_state = AgentState(
        query="Can I get a fee waiver?", intent="CLARIFICATION_NEEDED", confidence=0.0,
        retrieved_docs=[], tool_results=None, response=None, citations=[],
        needs_clarification=True, needs_escalation=False,
        clarification_question=None, escalation_reason=None
    )
    clarify_result = conv_agent.clarify(clarify_state)
    if not clarify_result.get("clarification_question"):
        raise CheckFailed("clarify() did not set state['clarification_question']")
    if not clarify_result.get("response"):
        raise CheckFailed("clarify() did not set state['response']")
    print("CLARIFICATION")
    print(f"Query: {clarify_state['query']}")
    print(clarify_result["response"])
    print()

    escalate_state = AgentState(
        query="Why was my loan application rejected?", intent="ESCALATION_REQUIRED", confidence=0.0,
        retrieved_docs=[], tool_results=None, response=None, citations=[],
        needs_clarification=False, needs_escalation=True,
        clarification_question=None, escalation_reason="Sensitive - privacy and compliance issue"
    )
    escalate_result = conv_agent.escalate(escalate_state)
    if not escalate_result.get("response"):
        raise CheckFailed("escalate() did not set state['response']")
    print("ESCALATION")
    print(f"Query: {escalate_state['query']}")
    print(escalate_result["response"])
except NotImplementedError as e:
    print(f"[WARN] Task 3.2 not yet implemented: {e}")
    print("   Implement clarify() and escalate() in src/core/agent_workflow.py")
except CheckFailed as e:
    print(f"[WARN] Task 3.2 check failed: {e}")
    print("   Your code ran without errors, but didn't store the LLM's reply in the state field named above")
""",
    ),
    dict(
        id="3.3", phase=3, title="Validate the Enterprise Solution",
        module="*No new module: end-to-end validation of everything implemented above*",
        business_context="""Before this agent reaches a customer operations executive, it needs to be checked against realistic scenarios the business actually cares about, not just the individual pieces you tested in isolation. `data/validation/test_scenarios.json` contains 18 such scenarios; this activity runs the full agent, end-to-end, against a representative subset covering every difficulty level and intent category.""",
        objective="Run `agent.run(query)` (exercising the complete workflow you've built across all three phases) against a representative set of validation scenarios, and produce a pass/fail scorecard.",
        instructions="""There's no new code to write here: this activity validates everything implemented in Activities 1.2 through 3.2 working together through the full compiled graph.

**Note:** the full 18-scenario suite is available in `data/validation/test_scenarios.json` and can be run the same way (or via `pytest tests/`) outside of class time; this activity uses a representative subset to keep runtime and API cost reasonable during the live session.""",
        files=[],
        milestone="The completed Enterprise AI Customer Operations Agent successfully supports realistic banking customer operations scenarios.",
        validation="""Review the scorecard:
- Most scenarios should show `✓ PASS`; occasional mismatches from LLM variability are expected and not necessarily a bug
- If every scenario shows `NOT IMPLEMENTED`, revisit the earlier activity referenced in the error message
- Investigate any scenario where the **Got Intent** column doesn't reasonably match **Expected Intent**, and note whether it clusters in the `complex` or `edge_case` categories, where an LLM-based agent is typically least consistent""",
        script="""import json
from src.core.agent_workflow import CustomerOperationsAgent

with open("data/validation/test_scenarios.json", encoding="utf-8") as f:
    all_scenarios = {s["id"]: s for s in json.load(f)["test_scenarios"]}

representative_ids = ["TEST-001", "TEST-003", "TEST-007", "TEST-012", "TEST-015", "TEST-016", "TEST-017"]
scenarios = [all_scenarios[sid] for sid in representative_ids]

try:
    final_agent = CustomerOperationsAgent()
except NotImplementedError as e:
    final_agent = None
    print(f"[WARN] Cannot validate: {e}")

if final_agent is not None:
    results = []
    for scenario in scenarios:
        try:
            outcome = final_agent.run(scenario["query"])
            response_text = (outcome.get("response") or "").lower()

            intent_match = outcome.get("intent") == scenario["expected_intent"]

            def term_covered(term, text):
                # Word-level match, not exact-phrase substring: real LLM
                # phrasing reorders and re-inflects words ("Proof of
                # Identity" vs a fixture written as "Identity proof",
                # "Photograph" vs "Photographs") without changing the
                # substance. Require every word of the term to appear
                # (crude singular/plural tolerance via a stripped trailing
                # "s"), not the exact phrase in the exact order.
                return all(w.rstrip("s") in text for w in term.lower().split())

            expected_terms = scenario.get("expected_response_contains", [])
            terms_found = sum(1 for term in expected_terms if term_covered(term, response_text))
            terms_ok = (not expected_terms) or (terms_found >= max(1, len(expected_terms) // 2))

            passed = intent_match and terms_ok
            results.append((scenario["id"], scenario["category"], passed, outcome.get("intent"),
                             scenario["expected_intent"], f"{terms_found}/{len(expected_terms)}" if expected_terms else "n/a"))
        except NotImplementedError as e:
            results.append((scenario["id"], scenario["category"], None, "NOT IMPLEMENTED", scenario["expected_intent"], str(e)))

    print(f"{'ID':<10}{'Category':<12}{'Result':<12}{'Got Intent':<22}{'Expected Intent':<22}{'Keywords'}")
    print("-" * 100)
    for sid, category, passed, got, expected, keywords in results:
        marker = "✓ PASS" if passed else ("✗ FAIL" if passed is False else "[WARN] N/A")
        print(f"{sid:<10}{category:<12}{marker:<12}{str(got):<22}{expected:<22}{keywords}")

    scored = [r for r in results if r[2] is not None]
    if scored:
        passed_count = sum(1 for r in scored if r[2])
        print(f"\\n✓ {passed_count}/{len(scored)} representative scenarios passed.")
""",
    ),
]

ACTIVITIES_BY_ID = {a["id"]: a for a in ACTIVITIES}
PHASE_TITLES = {
    1: "Phase 1 · Build the Enterprise AI Agent Foundation",
    2: "Phase 2 · Integrate Enterprise Knowledge",
    3: "Phase 3 · Enterprise Enablement",
}
PHASE_INTRO = {
    1: dict(
        objective="Understand the enterprise solution architecture and implement the foundational capabilities of "
                  "an AI agent capable of interpreting customer requests, reasoning about user intent, and "
                  "orchestrating the overall workflow.",
        outcome="By the end of this phase, you will have a functional AI agent capable of understanding customer "
                "requests and determining how they should be processed.",
    ),
    2: dict(
        objective="Enable the AI agent to access enterprise knowledge repositories using Retrieval-Augmented "
                  "Generation (RAG) and generate grounded, policy-compliant responses.",
        outcome="By the end of this phase, the AI agent can answer banking questions using enterprise knowledge "
                "rather than relying solely on the language model's own (unverified) knowledge.",
    ),
    3: dict(
        objective="Enhance the AI agent with enterprise behaviours that improve usability, reliability, and "
                  "maintainability within a production-style application.",
        outcome="By the end of this phase, you will have transformed a functional AI prototype into a structured "
                "enterprise AI solution.",
    ),
}

# Short, single-line labels for the sidebar nav: the full descriptive title
# (used in PAGES, the hero banner, and Prev/Next buttons) wraps to 2-3 lines
# in the narrow sidebar and, repeated for all 9 activities, buries the actual
# navigation under a wall of text. The nav only needs enough to recognize
# "where am I"; the full title is one click away on the activity page itself.
NAV_SHORT_TITLES = {
    "1.1": "Explore the Solution",
    "1.2": "Build the Agent Workflow",
    "1.3": "Implement Agent Reasoning",
    "2.1": "Prepare the Knowledge Base",
    "2.2": "Integrate Knowledge Retrieval",
    "2.3": "Generate Grounded Responses",
    "3.1": "Integrate Business Tools",
    "3.2": "Handle Conversation Scenarios",
    "3.3": "Validate the Solution",
}

REFERENCE_MAP = {
    "src/core/agent_workflow.py": "reference_solution/src/core/agent_workflow.py",
    "src/knowledge/knowledge_base.py": "reference_solution/src/knowledge/knowledge_base.py",
    "src/knowledge/retriever.py": "reference_solution/src/knowledge/retriever.py",
    "src/core/response_formatter.py": "reference_solution/src/core/response_formatter.py",
    "src/tools/product_tools.py": "reference_solution/src/tools/product_tools.py",
    "src/tools/branch_tools.py": "reference_solution/src/tools/branch_tools.py",
    "src/tools/eligibility_tools.py": "reference_solution/src/tools/eligibility_tools.py",
}


# ---------------------------------------------------------------------------
# Sidebar: navigation + progress tracker
# ---------------------------------------------------------------------------

PAGES = ["Overview & Setup"] + [f"Activity {a['id']} · {a['title']}" for a in ACTIVITIES] + ["Final Review"]

# Two-level nav: a top-level segmented control for Overview / each Phase /
# Final Review, then (only for a Phase) a short radio scoped to that
# phase's 3 activities. This keeps the always-visible list to at most 5
# items instead of all 11 activities at once, without the duplicate-selector
# trap other tools fall into (two separate widgets both choosing the same
# activity); this radio is the *only* control for "which activity."
TOP_LEVEL_OPTIONS = ["Overview"] + [f"Phase {p}" for p in PHASE_TITLES] + ["Final Review"]


def _nav_label(page: str) -> str:
    if page.startswith("Activity "):
        activity_id = page.replace("Activity ", "").split(" · ")[0]
        return f"{activity_id}  {NAV_SHORT_TITLES.get(activity_id, '')}"
    return page


def _phase_pages(phase_num: int) -> list:
    return [f"Activity {a['id']} · {a['title']}" for a in ACTIVITIES if a["phase"] == phase_num]


def _top_level_for(page: str) -> str:
    if page == PAGES[0] or page == PAGES[-1]:
        return TOP_LEVEL_OPTIONS[0] if page == PAGES[0] else TOP_LEVEL_OPTIONS[-1]
    activity_id = page.replace("Activity ", "").split(" · ")[0]
    return f"Phase {ACTIVITIES_BY_ID[activity_id]['phase']}"


if "nav_top" not in st.session_state:
    st.session_state.nav_top = TOP_LEVEL_OPTIONS[0]
# Widget session_state keys can't be reassigned after that widget has
# already been instantiated in the same run, so Previous/Next buttons
# (below) stage their target page here, applied before the widgets run.
if "pending_nav" in st.session_state:
    target = st.session_state.pop("pending_nav")
    st.session_state.nav_top = _top_level_for(target)
    if target not in (PAGES[0], PAGES[-1]):
        phase_num = ACTIVITIES_BY_ID[target.replace("Activity ", "").split(" · ")[0]]["phase"]
        st.session_state[f"nav_sub_{phase_num}"] = target

with st.sidebar:
    st.header("Guided Workbook")
    top_choice = st.segmented_control(
        "Section", TOP_LEVEL_OPTIONS, label_visibility="collapsed", key="nav_top"
    )
    if top_choice is None:
        # Clicking the active segment again deselects it in Streamlit. A
        # widget's session_state key can't be reassigned after that widget
        # has already run in this script pass, so defer the reset to
        # Overview via the same pending_nav mechanism the Previous/Next
        # buttons use (handled at the top of this block, before any widget
        # runs) and start a fresh run.
        st.session_state.pending_nav = PAGES[0]
        st.rerun()

    if top_choice in (TOP_LEVEL_OPTIONS[0], TOP_LEVEL_OPTIONS[-1]):
        selected_page = PAGES[0] if top_choice == TOP_LEVEL_OPTIONS[0] else PAGES[-1]
    else:
        phase_num = int(top_choice.split()[-1])
        phase_pages = _phase_pages(phase_num)
        sub_key = f"nav_sub_{phase_num}"
        if sub_key not in st.session_state:
            st.session_state[sub_key] = phase_pages[0]
        st.caption(f"↳ Activities in {top_choice}")
        selected_page = st.radio(
            "Activity", phase_pages, format_func=_nav_label, label_visibility="collapsed", key=sub_key
        )

    st.divider()
    st.subheader("Progress")

    passed_count = sum(1 for a in ACTIVITIES if st.session_state.activity_status.get(a["id"]) == "pass")
    total_count = len(ACTIVITIES)
    st.metric("Activities Complete", f"{passed_count} / {total_count}")
    st.progress(passed_count / total_count, text=f"{round(100 * passed_count / total_count)}% complete")

    if passed_count == total_count and not st.session_state.get("celebrated"):
        st.session_state.celebrated = True
        st.balloons()

    st.write("")
    for phase, phase_title in PHASE_TITLES.items():
        phase_activities = [a for a in ACTIVITIES if a["phase"] == phase]
        phase_done = sum(1 for a in phase_activities if st.session_state.activity_status.get(a["id"]) == "pass")
        st.caption(f"{phase_title.split('·')[0].strip()} · {phase_done}/{len(phase_activities)}")
        st.progress(phase_done / len(phase_activities))


# ---------------------------------------------------------------------------
# Reusable page pieces
# ---------------------------------------------------------------------------

def render_file_hint(rel_path: str):
    ref_path = REFERENCE_MAP.get(rel_path)
    if ref_path and (PROJECT_ROOT / ref_path).exists():
        with st.expander(f"Need a hint? View reference solution for {rel_path}"):
            st.code(read_file(ref_path), language="python")


def extract_method_source(file_text: str, method_name: str) -> tuple[str | None, str | None]:
    """Pull just one function/method's exact source (decorators included)
    out of a file's current text via ast, rather than the whole file, so
    the highlight below stays scoped to the few lines a participant is
    actually meant to touch.

    Returns (code, error): `code` is the extracted source, or None if the
    file doesn't parse or the name isn't found. `error` is a human-readable
    reason (the actual SyntaxError, with line/offset, or "not found") when
    `code` is None, so the caller can tell a broken file apart from a
    genuinely missing/renamed method instead of showing the same vague
    message for both."""
    try:
        tree = ast.parse(file_text)
    except SyntaxError as e:
        location = f"line {e.lineno}" + (f", column {e.offset}" if e.offset else "")
        return None, f"syntax error at {location}: {e.msg}"
    lines = file_text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return "\n".join(lines[start_line - 1:node.end_lineno]), None
    return None, "no function with this name found (renamed or removed?)"


def render_code_to_work_on(rel_path: str, method_names: list):
    """Live, read-only view of exactly the method(s) an activity asks the
    participant to implement, extracted fresh from their current src/ file
    on every render, isolated from the surrounding file so the ~10-30 lines
    that matter aren't buried in a full-file dump."""
    label_col, refresh_col = st.columns([5, 1])
    label_col.markdown("**Code you'll work on**: live from your current file, not the answer.")
    # This block only re-reads the file on a Streamlit rerun (any widget
    # interaction), saving in VS Code alone doesn't trigger one, so it can
    # sit stale while you're just looking at the page. Clicking anything
    # reruns the whole script anyway (read_file() below always re-reads
    # from disk); this button exists so there's something to click even
    # when you haven't touched any other widget.
    refresh_col.button("Refresh", key=f"refresh_code_{rel_path}", help="Re-check this file's status against what's currently saved on disk.")
    text = read_file(rel_path)
    for name in method_names:
        segment, error = extract_method_source(text, name)
        if segment is None:
            st.caption(f"`{name}`: can't check TODO status yet — {error} in {rel_path}. Fix this first, then the ✓/○ status below will work again.")
            continue
        # Most stubs signal "not done" with `raise NotImplementedError`, but
        # a couple (e.g. __init__) only leave a `# TODO:` comment behind,
        # check for both, or a half-finished method reads as done.
        done = "raise NotImplementedError" not in segment and "TODO" not in segment
        st.caption(f"{'✓' if done else '○'} `{name}`" + (": looks implemented" if done else ": still has a TODO"))
        st.code(segment, language="python")


STATUS_LABEL = {
    "pass": "All checks passed",
    "warn": "[WARN] Not fully implemented yet",
    "error": "The script raised an error",
}


def status_label_for(activity: dict, status: str) -> str:
    if status == "pass" and activity.get("pass_label"):
        return activity["pass_label"]
    return STATUS_LABEL.get(status, "Done")


def render_activity_runner(activity: dict):
    st.markdown("### Run & Validate")
    # 1.1 only scans the filesystem for TODOs; it has no `from src...`
    # import for reference_solution to stand in for, so it gets no button.
    has_reference_run = "from src" in activity["script"] or "import src" in activity["script"]

    if has_reference_run:
        run_col, ref_col = st.columns(2)
    else:
        run_col = st.container()
    run_clicked = run_col.button(f"Run Activity {activity['id']}", type="primary", key=f"run_{activity['id']}")
    ref_clicked = has_reference_run and ref_col.button(
        "See reference solution run", key=f"ref_{activity['id']}",
        help="Runs this same check against the completed reference_solution/ instead of your src/. "
             "Use it if you're stuck and want to see what passing actually looks like. "
             "Doesn't count toward your progress."
    )

    if ref_clicked:
        with st.status("Running against reference_solution/ ...", expanded=True):
            result = run_snippet(activity["script"], use_reference=True)
            output = (result["stdout"] or "") + (("\n" + result["stderr"]) if result["stderr"] else "")
            st.code(output.strip() or "(no output)", language="text")
        st.session_state[f"reference_output_{activity['id']}"] = result
    elif f"reference_output_{activity['id']}" in st.session_state:
        with st.status("Reference solution output", expanded=False):
            result = st.session_state[f"reference_output_{activity['id']}"]
            output = (result["stdout"] or "") + (("\n" + result["stderr"]) if result["stderr"] else "")
            st.code(output.strip() or "(no output)", language="text")

    if run_clicked:
        with st.status("Running against your current src/ code...", expanded=True) as status_box:
            result = run_snippet(activity["script"])
            status = classify_run(result)
            output = (result["stdout"] or "") + (("\n" + result["stderr"]) if result["stderr"] else "")
            st.code(output.strip() or "(no output)", language="text")
            if result["timed_out"]:
                status_box.update(label="Timed out", state="error", expanded=True)
            else:
                status_box.update(
                    label=status_label_for(activity, status),
                    state="complete" if status == "pass" else ("error" if status == "error" else "complete"),
                    expanded=(status != "pass"),
                )
        st.session_state.activity_status[activity["id"]] = status
        st.session_state.activity_output[activity["id"]] = result
        # Rerun so the sidebar's progress tracker (rendered earlier in script
        # order, before this activity page) picks up the status set just now.
        st.rerun()

    elif activity["id"] in st.session_state.activity_output:
        # Re-show the last run's result on a fresh page load, without re-running it.
        result = st.session_state.activity_output[activity["id"]]
        status = st.session_state.activity_status.get(activity["id"])
        with st.status(status_label_for(activity, status), state="complete" if status == "pass" else "error", expanded=(status != "pass")):
            output = (result["stdout"] or "") + (("\n" + result["stderr"]) if result["stderr"] else "")
            st.code(output.strip() or "(no output)", language="text")
        if status == "pass":
            st.success("Milestone reached: you're ready for the next activity.")

    if activity.get("validation"):
        # Collapsed by default: this is what to check in your own output
        # beyond "did it run," most useful once you actually have output to
        # read it against, not before.
        with st.expander("How to check your result"):
            st.markdown(activity["validation"])


# ---------------------------------------------------------------------------
# Page: Overview & Setup
# ---------------------------------------------------------------------------

if selected_page == "Overview & Setup":
    st.markdown("""
    <div class="hero-banner">
        <p class="hero-title">Enterprise AI Customer Operations Agent</p>
        <p class="hero-subtitle">Retail Banking · Customer Operations · Bootcamp 1, Tier 1 Foundation</p>
    </div>
    """, unsafe_allow_html=True)

    # These facts are fixed for the whole session (not a live metric to
    # track), so a caption (not st.metric) is the honest way to show them:
    # a metric implies "watch this change," which this never does.
    st.caption(
        f"{len(ACTIVITIES)} activities · {len(PHASE_TITLES)} phases · ~3 hrs · 20 policy documents in the knowledge base"
    )

    st.markdown("""
Welcome. You're stepping into the role of an AI Engineer on a retail bank's Enterprise AI programme, extending
an existing Customer Operations app with an agent that reasons about customer enquiries, retrieves banking
knowledge, invokes business tools, and answers with citations.

The project structure, UI, config, and data are already built; your job is the agent logic itself, one guided
activity at a time.
""")

    if st.button("Start Activity 1.1: Explore the Solution", type="primary", use_container_width=True):
        st.session_state.pending_nav = PAGES[1]
        st.rerun()

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["Business Context & Objectives", "What Makes This 'Agentic'", "Solution Architecture"])

    with tab1:
        with st.container(border=True):
            st.markdown("##### What You'll Build")
            st.markdown("""
- A working LangGraph agent workflow that classifies and routes customer requests
- A FAISS-backed knowledge base indexed over 20 banking policy documents
- Grounded response generation with document citations
- Business tool integration (product catalog and branch lookup)
- Clarification and escalation handling for ambiguous or sensitive requests
- A validation scorecard confirming the agent behaves correctly across realistic banking scenarios
""")
            st.caption("Built incrementally across 9 guided activities in 3 phases, each producing a tangible, verifiable output before you move to the next.")

        with st.container(border=True):
            st.markdown("##### The Business Problem")
            st.markdown("""
Customer Operations teams at retail banks handle a wide range of enquiries (account services, card operations,
KYC requirements, loan products, banking procedures) today by consulting multiple disconnected knowledge
repositories, while making sure every response stays accurate, consistent, and policy-aligned.

The bank has initiated an Enterprise AI programme to build a Customer Operations Agent that can reason over
requests, retrieve enterprise knowledge, invoke business capabilities, and generate trustworthy, policy-aware
responses, instead of support executives manually searching multiple systems for every enquiry.
""")

        with st.container(border=True):
            st.markdown("##### Your Role")
            st.markdown("""
You join the AI Engineering team responsible for delivering the first version of the Enterprise AI Customer
Operations Agent. Support executives will use the agent, through this app, to get accurate, explainable,
policy-driven answers to customer questions.
""")

        with st.container(border=True):
            st.markdown("##### Learning Objectives: by the end of this lab you will be able to")
            lo_col1, lo_col2 = st.columns(2)
            with lo_col1:
                st.markdown("""
- Explain what distinguishes an AI agent from a single LLM call, and identify the properties (autonomy, tool use, grounding, auditability) that make an AI system "agentic"
- Design and implement an agent workflow using LangGraph, including conditional routing
- Apply prompt engineering techniques to guide agent classification and reasoning
- Integrate enterprise knowledge using Retrieval-Augmented Generation (RAG)
- Build semantic search with OpenAI embeddings and a FAISS vector database
""")
            with lo_col2:
                st.markdown("""
- Generate grounded responses that cite their supporting documents
- Implement simple business tool invocation (product catalog, branch lookup) within an agent workflow
- Handle ambiguous and sensitive customer requests through clarification and escalation
- Validate an enterprise AI agent's behaviour against realistic business scenarios
- Use an AI coding assistant responsibly to accelerate implementation while validating everything it produces
""")

        with st.container(border=True):
            st.markdown("##### Dataset: already provided under `data/`")
            ds_col1, ds_col2 = st.columns(2)
            with ds_col1:
                st.markdown("""
**Enterprise Knowledge Base** (`knowledge_base/`)
20 banking policy documents in 4 categories: `accounts/`, `cards/`, `loans/`, `operations/`. What your RAG pipeline indexes and retrieves from.

**Business Reference Data** (`business_data/`)
- `product_catalog.json`: accounts, cards, loans
- `branch_directory.json`: locations, services, hours
- `eligibility_rules.json`: criteria per product
""")
            with ds_col2:
                st.markdown("""
**Validation Scenarios** (`validation/test_scenarios.json`)
18 customer queries spanning simple to edge-case difficulty, each with an expected intent. A subset is used in Activity 3.3.

**Configuration** (`config/`)
`agent_config.yaml`, `llm_config.yaml`, `prompts.yaml`: read from throughout; nothing is hardcoded.
""")

    with tab2:
        st.markdown("""
A single LLM call is a straight line: `prompt -> response`. It cannot decide to look something up, take an
action, ask for clarification, or hand off to a human; it just completes the text it was given. An **agent**
is different: it is a loop that *reasons about what a request needs* before it answers.
""")
        st.iframe(AGENTIC_DIAGRAM_SVG, height=480)
        st.markdown("""
That branching decision (not the LLM call itself) is what makes something "agentic." An enterprise AI agent
adds four properties on top of that basic loop, and you will build all four in this lab:

- **Autonomy**: it decides its own path through a request rather than following one fixed script. You will implement this as `route_decision` in Activity 1.3.
- **Tool use**: it can take structured actions, not just generate text. You will implement this as `invoke_tool` in Activity 3.1.
- **Grounding**: it answers from enterprise knowledge, not just what the model already "knows." You will implement this as retrieval-augmented generation in Phase 2.
- **Auditability**: it can explain itself: where an answer came from, or why a request was escalated. You will implement this as citations and `escalation_reason` in Activities 2.3 and 1.3.

Keep this loop in mind as you go: every activity in this lab implements one piece of it. The Solution
Architecture tab shows the specific architecture this agent uses to do it.
""")

    with tab3:
        st.markdown("Each layer of this solution has exactly one job:")
        st.iframe(ARCHITECTURE_DIAGRAM_SVG, height=460)
        st.markdown("""
Every arrow is a one-way dependency: this app never talks to the Knowledge or LLM layers directly, only to the
Agent layer, which decides what to do. Swap the Knowledge and Business Capability layers for a different domain
and the same shape holds.

Zooming into the Agent / Orchestration layer, here is the LangGraph workflow you build across the phases ahead:
""")
        st.iframe(WORKFLOW_DIAGRAM_SVG, height=520)

    import importlib.util
    required_packages = ["langgraph", "faiss", "openai", "streamlit", "yaml", "dotenv"]
    missing_packages = [pkg for pkg in required_packages if importlib.util.find_spec(pkg) is None]

    # OPENAI_API_KEY works with either a real OpenAI key or an OpenRouter
    # key (see .env.example); LLM_BASE_URL picks which one src/llm/ and
    # src/knowledge/embeddings.py actually talk to.
    key = os.getenv("OPENAI_API_KEY")
    key_missing = not key or key in ("your_openai_api_key_here", "your_openai_or_openrouter_api_key_here")

    required_paths = [
        "data/knowledge_base/accounts", "data/knowledge_base/cards",
        "data/knowledge_base/loans", "data/knowledge_base/operations",
        "data/business_data/product_catalog.json", "data/business_data/branch_directory.json",
        "data/business_data/eligibility_rules.json", "data/validation/test_scenarios.json",
        "config/agent_config.yaml", "config/llm_config.yaml", "config/prompts.yaml",
    ]
    missing_paths = [p for p in required_paths if not (PROJECT_ROOT / p).exists()]

    all_ok = not missing_packages and not key_missing and not missing_paths
    expander_label = "Environment ready" if all_ok else "[WARN] Environment Validation: action needed"

    with st.expander(expander_label, expanded=not all_ok):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Packages**")
            if missing_packages:
                st.error(f"Missing: {', '.join(missing_packages)}\n\nRun: `pip install -r requirements.txt`")
            else:
                st.success("All required packages are installed.")

        with col2:
            st.markdown("**API Key**")
            if key_missing:
                st.error("OPENAI_API_KEY is not set.\n\nCopy `.env.example` to `.env` and add your OpenAI or OpenRouter key.")
            else:
                st.success("OPENAI_API_KEY is configured.")

        with col3:
            st.markdown("**Project Assets**")
            if missing_paths:
                st.error(f"Missing: {', '.join(missing_paths)}")
            else:
                st.success(f"All {len(required_paths)} required project assets are present.")


# ---------------------------------------------------------------------------
# Page: Final Review
# ---------------------------------------------------------------------------

elif selected_page == "Final Review":
    st.markdown("""
    <div class="hero-banner">
        <p class="hero-title">Final Review</p>
        <p class="hero-subtitle">Review everything you've built, then run one final live demonstration</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
Review what you've built across all three phases:
- **Agent Workflow**: a compiled LangGraph state machine with conditional routing (Phase 1)
- **Knowledge Retrieval**: a cached FAISS index over 20 banking policy documents, with grounded, cited responses (Phase 2)
- **Business Tools & Conversation Handling**: product/branch lookups, clarification, and escalation (Phase 3)
- **Validation**: a scorecard confirming behaviour against realistic business scenarios
""")

    if st.button("Run Final Demo", type="primary"):
        with st.spinner("Running the complete agent end-to-end..."):
            result = run_snippet("""from src.core.agent_workflow import CustomerOperationsAgent

demo_queries = [
    "What is the interest rate on personal loans?",
    "Which branch in Mumbai offers forex services?",
]

try:
    demo_agent = CustomerOperationsAgent()
    for query in demo_queries:
        result = demo_agent.run(query)
        print(f"Query: {query}")
        print(f"Intent: {result.get('intent')}")
        print(f"Response: {result.get('response')}")
        print(f"Citations: {result.get('citations')}")
        print("-" * 70)
    print("\\n✓ End-to-end agent execution complete.")
except NotImplementedError as e:
    print(f"[WARN] Not all activities are complete yet: {e}")
""")
        output = (result["stdout"] or "") + (("\n" + result["stderr"]) if result["stderr"] else "")
        st.code(output.strip() or "(no output)", language="text")

    st.markdown("---")
    st.markdown("#### Key Takeaways")

    kt_col1, kt_col2, kt_col3 = st.columns(3)
    with kt_col1:
        st.markdown("""**What You Built**
- An enterprise AI agent workflow orchestrated with LangGraph, with intent classification and conditional routing
- A RAG pipeline: chunking, embedding, FAISS indexing, and semantic search over 20 banking policy documents
- Grounded response generation with document citations, driven entirely by configuration-defined prompts
- Business tool integration for product catalog and branch lookups
- Clarification and escalation handling for ambiguous and sensitive requests
- A validation scorecard confirming behaviour against realistic business scenarios""")
    with kt_col2:
        st.markdown("""**Enterprise AI Engineering Principles**
- **Modular architecture**: each capability (workflow, knowledge, tools) lives in its own module, independently testable
- **Configuration-driven behaviour**: prompts, thresholds, and escalation rules live in YAML, not hardcoded in Python
- **Grounding and explainability**: every knowledge-based response traces back to a cited source document
- **Graceful degradation**: the agent fails informatively (not silently) when a capability isn't implemented yet
- **Reusable infrastructure**: a cached vector index built once powers every later activity""")
    with kt_col3:
        st.markdown("""**Skills Demonstrated**
- LangGraph state machine design (nodes, conditional edges, routing functions)
- Prompt-driven LLM classification and generation
- RAG pipeline construction: chunking, embeddings, FAISS indexing, semantic retrieval
- Citation-based grounded response generation
- Business tool design and selection logic
- Enterprise validation against realistic business scenarios""")

    st.markdown("---")
    st.markdown("""
**Next Steps:** The Enterprise AI Customer Operations Agent you built in this lab serves as the foundation for
more advanced enterprise agents capable of interacting with business applications and executing operational
workflows, which you'll explore in **Bootcamp 2**.
""")


# ---------------------------------------------------------------------------
# Page: an individual activity
# ---------------------------------------------------------------------------

else:
    activity_id = selected_page.replace("Activity ", "").split(" · ")[0]
    activity = ACTIVITIES_BY_ID[activity_id]

    # Shown once per phase, right before that phase's first activity: the
    # same place the notebook's own phase-intro cell sits, immediately
    # before Activity X.1's cell. Not repeated on X.2/X.3 since you've
    # already seen it by then.
    if activity["id"].endswith(".1"):
        phase_intro = PHASE_INTRO[activity["phase"]]
        st.markdown(f"#### {PHASE_TITLES[activity['phase']]}")
        st.markdown(f"**Objective:** {phase_intro['objective']}")
        st.caption(phase_intro["outcome"])
        st.divider()

    st.markdown(f"""
    <div class="hero-banner">
        <p class="hero-title">Activity {activity['id']} · {activity['title']}</p>
        <p class="hero-subtitle">{activity['module']}</p>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"**What success looks like:** {activity['milestone']}")

    with st.container(border=True):
        st.markdown("#### Business Context")
        st.markdown(activity["business_context"])

    with st.container(border=True):
        st.markdown("#### Objective")
        st.markdown(activity["objective"])

    if activity.get("concept_overview"):
        with st.container(border=True):
            st.markdown("#### Concept Overview")
            st.markdown(activity["concept_overview"])

    with st.container(border=True):
        st.markdown("#### Implementation Instructions")
        st.markdown(activity["instructions"])
        if activity.get("ai_assist"):
            st.info(activity["ai_assist"])

    if activity.get("reference_only_files"):
        # Collapsed by default: a full config file dumped open on the page
        # is exactly the "wall of code" that makes a lab feel harder than it
        # is before anyone's read a word of the instructions above.
        with st.expander(f"Reference Files: {', '.join(activity['reference_only_files'])}"):
            tabs = st.tabs(activity["reference_only_files"])
            for tab, path in zip(tabs, activity["reference_only_files"]):
                with tab:
                    st.code(read_file(path), language="yaml")

    if activity["files"]:
        st.markdown("#### Files to Edit")
        st.info(
            "Open these in VS Code (or your preferred IDE) to write your implementation. This app runs "
            "whatever is currently saved on disk, it doesn't edit files itself."
        )
        target_methods = activity.get("target_methods", {})
        if len(activity["files"]) == 1:
            path = activity["files"][0]
            st.code(path, language="text")
            if path in target_methods:
                render_code_to_work_on(path, target_methods[path])
            render_file_hint(path)
        else:
            # Tab labels already name each file; an extra list above them
            # would just repeat the same names twice in a row.
            tabs = st.tabs(activity["files"])
            for tab, path in zip(tabs, activity["files"]):
                with tab:
                    if path in target_methods:
                        render_code_to_work_on(path, target_methods[path])
                    render_file_hint(path)

    st.divider()
    render_activity_runner(activity)

    st.divider()
    page_index = PAGES.index(selected_page)
    prev_col, next_col = st.columns(2)
    with prev_col:
        if page_index > 0:
            if st.button(f"< {PAGES[page_index - 1]}", use_container_width=True):
                st.session_state.pending_nav = PAGES[page_index - 1]
                st.rerun()
    with next_col:
        if page_index < len(PAGES) - 1:
            if st.button(f"{PAGES[page_index + 1]} >", use_container_width=True, type="primary"):
                st.session_state.pending_nav = PAGES[page_index + 1]
                st.rerun()
