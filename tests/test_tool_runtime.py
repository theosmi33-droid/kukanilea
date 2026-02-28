from __future__ import annotations

import os
import sys

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.tool_loader import load_all_tools
from app.agents.runtime import AgentRuntime
from app.tools.registry import registry
from app.evaluation.evaluator import Evaluator

def test_tool_runtime():
    print("Testing KUKANILEA Tool Runtime...")
    
    # 1. Load tools
    load_all_tools()
    tools = registry.list()
    print(f"Registered tools: {tools}")
    assert "filesystem_list" in tools
    
    # 2. Setup runtime
    runtime = AgentRuntime()
    evaluator = Evaluator()
    
    # 3. Execute with evaluation
    def run_agent():
        return runtime.run("search", "Dateien zeigen")
        
    eval_result = evaluator.evaluate(run_agent)
    
    result = eval_result["result"]
    duration = eval_result["duration_seconds"]
    
    print(f"Agent result: {result}")
    print(f"Execution took: {duration:.4f}s")
    
    assert isinstance(result, list)
    assert "app" in result or "requirements.txt" in result
    
    print("Tool Runtime Test: PASS")

if __name__ == "__main__":
    test_tool_runtime()
