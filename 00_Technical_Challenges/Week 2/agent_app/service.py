"""Stage 4: run the agent and shape its messages into the AskResponse contract.

`build_agent` is written for you (it just composes your three stubs). `answer_question`
is YOURS — and it is the real lesson of the week: an agent emits a sprawling list of
messages; an API promises one clean, validated object. You close that gap here.
"""

from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable

from .graph import build_agent_graph
from .index import build_retriever
from .schemas import AskRequest, AskResponse, Source, TraceStep
from .tools import build_web_search_tool, make_search_tool, WELLNESS_SEARCH_TOOL_NAME

from langgraph.errors import GraphRecursionError
import json
import re

def build_agent(corpus_path: Path, k: int = 3) -> Runnable:
    """Compose the three stubs into one ready agent. Called ONCE at startup by api.py.

    This is the plumbing that shows how your pieces fit: an index -> a tool over it ->
    a graph that can call the tools. It will raise NotImplementedError until the three
    stubs it calls are filled in.

    The agent gets a second source for free: `build_web_search_tool()` (written for you)
    returns a Tavily tool when `TAVILY_API_KEY` is set, and `None` otherwise. We append it to
    the tool list, so the agent can reach the live web the moment you add a key — and the graph
    needs no change, because `build_agent_graph` takes the whole list.
    """
    retriever = build_retriever(corpus_path, k=k)
    search_tool = make_search_tool(retriever)
    tools = [search_tool]
    web_search = build_web_search_tool()  # None unless TAVILY_API_KEY is set
    if web_search is not None:
        tools.append(web_search)
    return build_agent_graph(tools)


def answer_question(request: AskRequest, agent: Runnable) -> AskResponse:
    """Run the agent for one question and build the AskResponse.

    Args:
        request: the validated AskRequest (question + k).
        agent: the compiled graph from build_agent().

    Returns:
        An AskResponse: the final answer, whether retrieval was used, the cited sources,
        and the trace.

    Walk the message list the agent returns and pull four things out of it:

      result = agent.invoke({"messages": [HumanMessage(content=request.question)]})
      messages = result["messages"]

      1. answer         -> the last message's `.content`.
      2. trace          -> one TraceStep per interesting message: an AI message with
                           `.tool_calls` is a "agent" step whose detail names the tool and
                           args; a ToolMessage is a "tools" step whose detail is its result.
      3. used_retrieval -> True if the wellness search tool appears anywhere in the trace.
                           Match it by name: `tools.WELLNESS_SEARCH_TOOL_NAME`.
      4. sources        -> parse the ToolMessages. Each block the tool emitted starts with
                           `[source chunk_id=<n> score=<x>]` (see tools.SOURCE_LINE), followed
                           by the chunk text. Turn each block into a Source(chunk_id, score,
                           preview=<first ~160 chars>). This is exactly the structured-output
                           seam from the notebook: messy text in, typed objects out.

    If web search is enabled (a `TAVILY_API_KEY` is set), its ToolMessages show up in the trace
    too — but they don't match `SOURCE_LINE`, so a parser that keys off that prefix naturally
    skips them. That's correct: `sources` cite the guide; the web step is visible in `trace`.

    Hint: message role is `getattr(msg, "type", None)` -> "human" | "ai" | "tool". Tool calls
    live on `getattr(msg, "tool_calls", None)`. A ToolMessage carries `.name` and `.content`.
    Keep this function pure data-shaping — no model or retriever calls happen here.
    """

    pattern = r"^\[source chunk_id=(\S+) score=([0-9.]+)\]\n(.*)"
    sources: list[Source] = []
    traces: list[TraceStep] = []
    used_retrieval = False
    result = {}
    last_message = ""

    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=request.question)]},
            config={"recursion_limit": 10})

        last_message = result["messages"][-1].content or ""
        
        for message in result["messages"]:
            match getattr(message, "type", None):
                case "ai":
                    tool_details = ""

                    for tool_calls_attr in getattr(message, "tool_calls", None) or []:
                        tool_details = f"Call Tool Name: {tool_calls_attr["name"]}, Tool args={tool_calls_attr["args"]   }" 
                    
                    tool_details = tool_details or message.response_metadata.get("normalized_finish_reason")
                    
                    traces.append(TraceStep(node="agent",detail=tool_details))

                case "tool":
                    content = getattr(message, "content", None)
                    tool_details = f"Tool Name: {getattr(message, "name", None)}, Result: {content}"

                    traces.append(TraceStep(node="tools", detail=tool_details))
                    
                    if getattr(message, "name", None) == WELLNESS_SEARCH_TOOL_NAME:
                        used_retrieval = True
                        for block in content.strip().split("\n\n"):
                            match = re.match(pattern, block, flags=re.DOTALL)
                            if match:
                                sources.append(
                                    Source(chunk_id=match.group(1), 
                                        score=float(match.group(2)),
                                        preview=f"{match.group(3).strip()[:160]} ..."))
        
        return AskResponse(answer=last_message, 
                        sources=sources, 
                        trace=traces,
                            used_retrieval=used_retrieval)
    except GraphRecursionError:
        return AskResponse(answer=f"Reached max iterations. Best answer so far:\n\n" + last_message,
                       sources=sources, 
                       trace=traces,
                        used_retrieval=used_retrieval)
