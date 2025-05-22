"""Example of running an agent node independently."""

import asyncio
import json
import os
from dotenv import load_dotenv
from aic_flow.nodes.ai import Agent


load_dotenv()


model_config = {
    "model": "gpt-4o-mini",
    "api_key": os.getenv("OPENAI_API_KEY"),
}

json_schema = {
    "type": "object",
    "title": "Person",
    "description": "A person",
    "properties": {
        "name": {"type": "string"},
    },
}

agent_node = Agent(
    name="agent",
    model_config=model_config,
    structured_output=json_schema,
    system_prompt="Your name is John Doe.",
    checkpointer="memory",
)
config = {"configurable": {"thread_id": "123"}}
result = asyncio.run(
    agent_node(
        {"messages": [{"role": "user", "content": "What's your name?"}]}, config
    )
)
print(result)
