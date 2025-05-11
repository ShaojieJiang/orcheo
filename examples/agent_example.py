"""Example of running an agent node independently."""

import os
from dotenv import load_dotenv
from aic_flow.nodes.ai import Agent


load_dotenv()


model_config = {
    "model": "gpt-4o-mini",
    "api_key": os.getenv("OPENAI_API_KEY"),
}

agent_node = Agent(
    name="agent",
    model_config=model_config,
    system_prompt="You are a helpful assistant.",
    checkpointer="memory",
)
config = {"configurable": {"thread_id": "123"}}
result = agent_node(
    {"messages": [{"role": "user", "content": "Hello, how are you?"}]}, config
)
print(result)
