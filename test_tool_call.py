#!/usr/bin/env python
# Test ToolCall from langchain-core
from langchain_core.messages import ToolCall

# Create a ToolCall instance
tool_call = ToolCall(name="test_tool", args={"arg1": "value1"}, id="test_id")

# Print basic information
print("Tool Call ID:", tool_call.id)
print("Tool Call Name:", tool_call.name)
print("Tool Call Args:", tool_call.args)
