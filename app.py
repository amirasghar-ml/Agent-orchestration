
import os
import ast
import operator
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

try:
    from langchain_community.tools import DuckDuckGoSearchRun
except ImportError:
    DuckDuckGoSearchRun = None

try:
    from langchain.agents import create_agent as create_specialist_agent
except ImportError:
    try:
        from langgraph.prebuilt import create_react_agent as create_specialist_agent
    except ImportError:
        create_specialist_agent = None

load_dotenv()

# --------------------------------------------------
# 1. LLM CONFIGURATION: OLLAMA CLOUD
# --------------------------------------------------

llm = ChatOpenAI(
    model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
    api_key=os.getenv("OLLAMA_API_KEY"),
    base_url=os.getenv(
        "OLLAMA_BASE_URL", "https://ollama.com/v1"
    ),
    temperature=0,
)

# --------------------------------------------------
# 2. AGENT 1 TOOL: RESEARCH
# --------------------------------------------------

web_search = DuckDuckGoSearchRun() if DuckDuckGoSearchRun is not None else None


@tool
def research_tool(query: str) -> str:
    """Search the web for information relevant to a research query."""
    if web_search is None:
        return (
            "Web search is unavailable because the langchain-community search package "
            "is not installed in this environment."
        )

    try:
        return web_search.invoke(query)
    except Exception as exc:
        return (
            "Web search is currently unavailable due to a network or DNS issue. "
            f"Please try a different query or use a direct answer mode. Error: {exc}"
        )


# --------------------------------------------------
# 3. AGENT 2 TOOL: DATA ANALYSIS
# --------------------------------------------------

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression: str):
    """Evaluate basic arithmetic without executing arbitrary Python."""
    if len(expression) > 200:
        raise ValueError("Expression is too long.")

    tree = ast.parse(expression, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant):
            if type(node.value) in (int, float):
                return node.value
            raise ValueError("Only numbers are allowed.")

        if isinstance(node, ast.BinOp):
            operation = ALLOWED_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Operator not allowed.")
            return operation(
                evaluate(node.left), evaluate(node.right)
            )

        if isinstance(node, ast.UnaryOp):
            operation = ALLOWED_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Operator not allowed.")
            return operation(evaluate(node.operand))

        raise ValueError("Unsupported expression.")

    return evaluate(tree)


@tool
def data_tool(expression: str) -> str:
    """Calculate a basic arithmetic expression, such as (100 + 50) / 2."""
    try:
        return str(safe_calculate(expression))
    except Exception as exc:
        return f"Calculation error: {exc}"


# --------------------------------------------------
# 4. AGENT 3 TOOL: CODING
# --------------------------------------------------

@tool
def inspect_python_code(code: str) -> str:
    """Check Python code for syntax errors without executing it."""
    try:
        ast.parse(code)
        return "Python syntax is valid."
    except SyntaxError as exc:
        return (
            f"Syntax error on line {exc.lineno}: {exc.msg}"
        )


# --------------------------------------------------
# 5. AGENT 4 TOOL: DOCUMENTS
# --------------------------------------------------

@tool
def document_stats(text: str) -> str:
    """Return basic statistics about the supplied document text."""
    words = text.split()
    lines = text.splitlines()

    return (
        f"Word count: {len(words)}\n"
        f"Line count: {len(lines)}\n"
        f"Character count: {len(text)}"
    )


# --------------------------------------------------
# 6. CREATE FOUR SPECIALIST AGENTS
# --------------------------------------------------

def make_specialist_agent(agent_name: str, tool_list, instruction: str):
    """Create a specialist agent compatible with current and older LangChain versions."""
    if create_specialist_agent is None:
        raise RuntimeError(
            "No supported LangChain agent factory was found. "
            "Please install a compatible version of the LangChain packages."
        )

    try:
        return create_specialist_agent(
            model=llm,
            tools=tool_list,
            prompt=instruction,
        )
    except TypeError:
        return create_specialist_agent(
            model=llm,
            tools=tool_list,
            system_prompt=instruction,
        )


research_agent = make_specialist_agent(
    "research",
    [research_tool],
    (
        "You are a Research Agent. Research the user's question "
        "using your search tool. Summarize findings clearly and "
        "distinguish sourced facts from uncertainty. If the search tool "
        "fails due to a network issue, say the search is unavailable and "
        "state the limitation clearly."
    ),
)

data_agent = make_specialist_agent(
    "data",
    [data_tool],
    (
        "You are a Data Analysis Agent. Analyze numerical "
        "questions carefully. Use your calculation tool when "
        "appropriate and explain the result."
    ),
)

coding_agent = make_specialist_agent(
    "coding",
    [inspect_python_code],
    (
        "You are a Coding Agent. Help with Python programming, "
        "debugging, and code design. Use your syntax inspection "
        "tool when code is supplied. Never claim code was run "
        "when it was only inspected."
    ),
)

document_agent = make_specialist_agent(
    "documents",
    [document_stats],
    (
        "You are a Document Agent. Help summarize, analyze, "
        "and extract information from text provided by the user. "
        "Use the document statistics tool when useful. Base "
        "your answer on the supplied document."
    ),
)

AGENTS = {
    "research": research_agent,
    "data": data_agent,
    "coding": coding_agent,
    "documents": document_agent,
}

# --------------------------------------------------
# 7. MASTER AGENT: DECIDES WHICH AGENTS TO CALL
# --------------------------------------------------

class RoutingDecision(BaseModel):
    agents: list[
        Literal["research", "data", "coding", "documents"]
    ] = Field(
        description=(
            "The specialist agents needed to answer the user. "
            "Choose one or more agents. Use an empty list only "
            "when no specialist is needed."
        )
    )
    reason: str = Field(
        description="Brief explanation of the routing decision."
    )


router = llm.with_structured_output(RoutingDecision)

master_prompt = """
You are the Master Agent supervising four specialist agents.

Available agents:
- research: web research and finding current information
- data: arithmetic and numerical analysis
- coding: Python programming and syntax inspection
- documents: document analysis and text summarization

Rules:
1. Read the user's request carefully.
2. Select the minimum necessary specialist agents.
3. Select multiple agents if the task requires multiple skills.
4. Do not select an agent without a relevant reason.
5. For simple conversational questions, select no specialist.
6. Never claim a tool was used unless it was actually called.
"""

# --------------------------------------------------
# 8. RUN THE MASTER AND SPECIALIST AGENTS
# --------------------------------------------------

def normalize_routing_decision(decision) -> RoutingDecision:
    """Convert router output into a valid RoutingDecision object."""
    if decision is None:
        return RoutingDecision(
            agents=[],
            reason=(
                "No routing decision returned by the model; "
                "defaulting to a direct answer."
            ),
        )

    if isinstance(decision, RoutingDecision):
        return decision

    if isinstance(decision, dict):
        raw_agents = decision.get("agents", [])
        if isinstance(raw_agents, str):
            raw_agents = [raw_agents]

        agents = []
        for name in raw_agents or []:
            if name in AGENTS:
                agents.append(name)

        reason = str(decision.get("reason") or "Routing decision missing explanation.")
        return RoutingDecision(agents=agents, reason=reason)

    if hasattr(decision, "agents") or hasattr(decision, "reason"):
        raw_agents = getattr(decision, "agents", [])
        if isinstance(raw_agents, str):
            raw_agents = [raw_agents]

        agents = []
        for name in raw_agents or []:
            if name in AGENTS:
                agents.append(name)

        reason = getattr(decision, "reason", None)
        return RoutingDecision(
            agents=agents,
            reason=str(reason or "Routing decision missing explanation."),
        )

    return RoutingDecision(
        agents=[],
        reason=f"Unexpected routing response: {decision!r}",
    )


def infer_agents_from_query(user_query: str) -> RoutingDecision:
    """Fallback routing logic used when structured output is empty or unusable."""
    text = user_query.lower()
    detected = []

    research_keywords = [
        "search", "research", "latest", "news", "recent", "current",
        "web", "internet", "find information", "what is happening",
        "developments", "update", "newest"
    ]
    data_keywords = [
        "calculate", "sum", "average", "percent", "percentage",
        "math", "total", "estimate", "multiply", "divide", "plus",
        "minus", "times", "+", "-", "*", "/"
    ]
    coding_keywords = [
        "python", "code", "syntax", "bug", "error", "exception",
        "traceback", "debug", "function", "class", "program",
        "fix", "lint"
    ]
    document_keywords = [
        "document", "summarize", "text", "essay", "report",
        "article", "paragraph", "paste", "analyze this", "read this"
    ]

    if any(keyword in text for keyword in research_keywords):
        detected.append("research")
    if any(keyword in text for keyword in data_keywords):
        detected.append("data")
    if any(keyword in text for keyword in coding_keywords):
        detected.append("coding")
    if any(keyword in text for keyword in document_keywords):
        detected.append("documents")

    if not detected:
        return RoutingDecision(
            agents=[],
            reason="No specialist agents matched the query; defaulting to a direct answer.",
        )

    return RoutingDecision(
        agents=detected,
        reason="Detected relevant specialist skills from the user query because the model returned no structured routing output.",
    )


def run_agent(agent, task: str) -> str:
    """Execute a specialist agent and return its final response."""
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        return str(result["messages"][-1].content)
    except Exception as exc:
        return f"Agent execution failed: {exc}"


def run_master_with_steps(user_query: str, on_step=None):
    steps = []

    def log_step(message: str):
        print(message)
        steps.append(message)
        if on_step is not None:
            on_step(message)

    log_step("\n[MASTER] Analyzing request...")

    try:
        raw_decision = router.invoke([
            ("system", master_prompt),
            ("human", user_query),
        ])
    except Exception as exc:
        log_step(
            "[MASTER] Structured routing unavailable "
            f"({type(exc).__name__}); using query-based fallback."
        )
        decision = infer_agents_from_query(user_query)
    else:
        decision = normalize_routing_decision(raw_decision)

    if not decision.agents:
        decision = infer_agents_from_query(user_query)

    log_step(f"[MASTER] Routing reason: {decision.reason}")
    log_step(f"[MASTER] Selected agents: {decision.agents}")

    if not decision.agents:
        response = llm.invoke([
            ("system", "Answer the user helpfully and accurately."),
            ("human", user_query),
        ])
        return str(response.content), steps

    results = []

    # Run only the agents selected by the Master Agent.
    for name in decision.agents:
        log_step(f"\n[{name.upper()}] Working...")

        result = run_agent(AGENTS[name], user_query)

        results.append(
            f"Agent: {name}\nResult:\n{result}"
        )

    # Master Agent synthesizes the specialist results.
    log_step("\n[MASTER] Preparing final answer...")

    synthesis_prompt = f"""
You are the Master Agent.

Original user request:
{user_query}

Specialist results:
{"".join(chr(10) + result + chr(10) for result in results)}

Combine the results into one accurate, useful response.
Resolve inconsistencies where possible. Do not invent facts,
tool outputs, or conclusions unsupported by the results.
"""

    final_response = llm.invoke([
        ("system", "You are a careful AI supervisor."),
        ("human", synthesis_prompt),
    ])

    return str(final_response.content), steps


def run_master(user_query: str) -> str:
    answer, _ = run_master_with_steps(user_query)
    return answer


# --------------------------------------------------
# 9. INTERACTIVE CLI
# --------------------------------------------------

if __name__ == "__main__":
    print("Multi-Agent System started.")
    print("Type 'exit' to stop.")

    while True:
        query = input("\nYou: ").strip()

        if query.lower() in {"exit", "quit"}:
            break

        if not query:
            continue

        try:
            answer = run_master(query)
            print("\nFinal Answer:\n", answer)
        except Exception as exc:
            print(f"\nError: {exc}")
