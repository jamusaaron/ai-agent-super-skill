#!/usr/bin/env python3
"""Runnable extract of the ReAct agent loop from SKILL.md (section 2.2).

The loop itself is copied faithfully from the skill. To make it runnable with
no API key, a small deterministic ``MockLLM`` stands in for a real model and a
``calculator`` tool is provided. Run directly:

    python3 examples/react_agent.py
"""

import json

REACT_SYSTEM_PROMPT = """
You are a research agent. For every task:

1. THOUGHT: Reason about what you know and what you need
2. ACTION: Choose one tool to call
3. OBSERVATION: Read the tool result
4. Repeat until you have enough information
5. FINAL ANSWER: Synthesize and respond

Available tools: {tool_list}

Format strictly:
Thought: <your reasoning>
Action: <tool_name>
Action Input: <tool_arguments as JSON>
Observation: <tool result -- filled by system>
... (repeat)
Final Answer: <your complete response>
"""


def react_agent(query: str, tools: dict, llm, max_iterations: int = 10) -> str:
    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT.format(
            tool_list="\n".join(f"- {k}: {v['description']}" for k, v in tools.items())
        )},
        {"role": "user", "content": query}
    ]

    for _iteration in range(max_iterations):
        response = llm.complete(messages)

        if "Final Answer:" in response:
            return response.split("Final Answer:")[-1].strip()

        action_line = [l for l in response.split("\n") if l.startswith("Action:")]
        input_line = [l for l in response.split("\n") if l.startswith("Action Input:")]

        if not action_line:
            break

        tool_name = action_line[0].replace("Action:", "").strip()
        tool_input = json.loads(input_line[0].replace("Action Input:", "").strip())

        if tool_name in tools:
            observation = tools[tool_name]["fn"](**tool_input)
        else:
            observation = f"Error: Unknown tool '{tool_name}'"

        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return "Agent reached max iterations without a final answer."


# --- Tooling -----------------------------------------------------------------
def calculator(a: float, b: float, op: str) -> float:
    ops = {
        "add": a + b,
        "sub": a - b,
        "mul": a * b,
        "div": a / b if b else float("inf"),
    }
    return ops.get(op, float("nan"))


TOOLS = {
    "calculator": {
        "description": "Perform arithmetic. Args: a, b, op in {add,sub,mul,div}.",
        "fn": calculator,
    },
}


class MockLLM:
    """Deterministic stand-in for a real LLM, so the loop runs offline.

    It emits a single tool call, then a final answer once it has seen the
    tool's observation -- exactly the observe/think/act cycle the loop expects.
    """

    def __init__(self, a: float, b: float, op: str):
        self.a, self.b, self.op = a, b, op

    def complete(self, messages: list[dict]) -> str:
        seen_observation = any(
            m["role"] == "user" and m["content"].startswith("Observation:")
            for m in messages
        )
        if not seen_observation:
            return (
                "Thought: I should use the calculator tool.\n"
                f"Action: calculator\n"
                f'Action Input: {{"a": {self.a}, "b": {self.b}, "op": "{self.op}"}}'
            )
        result = messages[-1]["content"].replace("Observation:", "").strip()
        return (
            "Thought: I now have the result from the tool.\n"
            f"Final Answer: The result is {result}."
        )


def _demo() -> None:
    query = "What is 12 plus 30?"
    answer = react_agent(query, TOOLS, MockLLM(12, 30, "add"))
    print(f"Query:  {query}")
    print(f"Answer: {answer}")


if __name__ == "__main__":
    _demo()
