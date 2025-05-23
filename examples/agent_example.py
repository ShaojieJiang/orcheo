# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.7
#   kernelspec:
#     display_name: .venv
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Example of using Agent node

# %%
import os
from dotenv import load_dotenv
from aic_flow.nodes.ai import Agent
from aic_flow.nodes.telegram import MessageTelegram


load_dotenv()


model_settings = {
    "model": "gpt-4o-mini",
    "api_key": os.getenv("OPENAI_API_KEY"),
}

# %% [markdown]
# ## Structured output with vanilla JSON dict

# %%
so_schema = """
json_dict = {
    "type": "object",
    "title": "Person",
    "description": "A person",
    "properties": {
        "name": {"type": "string"},
    },
    "required": ["name"],
}
"""

so_config = {
    "schema_type": "json_dict",
    "schema_str": so_schema,
}

agent_node = Agent(
    name="agent",
    model_settings=model_settings,
    structured_output=so_config,
    system_prompt="Your name is John Doe.",
    checkpointer="memory",
)
config = {"configurable": {"thread_id": "123"}}
result = await agent_node(  # noqa: F704, PLE1142
    {"messages": [{"role": "user", "content": "What's your name?"}]}, config
)

result["structured_response"]

# %% [markdown]
# ## Structured output with OpenAI JSON dict

# %%
so_schema = """
oai_json_schema = {
    "name": "get_person",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
        "required": ["name"],
    },
}
"""

so_config = {
    "schema_type": "json_dict",
    "schema_str": so_schema,
}

agent_node = Agent(
    name="agent",
    model_settings=model_settings,
    structured_output=so_config,
    system_prompt="Your name is John Doe.",
    checkpointer="memory",
)
config = {"configurable": {"thread_id": "123"}}
result = await agent_node(  # noqa: F704, PLE1142
    {"messages": [{"role": "user", "content": "What's your name?"}]}, config
)

result["structured_response"]

# %% [markdown]
# ## Structured output with Pydantic Models

# %%
so_schema = """
class Person(BaseModel):
    \"\"\"A Person.\"\"\"

    name: str
"""

so_config = {
    "schema_type": "json_dict",
    "schema_str": so_schema,
}

agent_node = Agent(
    name="agent",
    model_settings=model_settings,
    structured_output=so_config,
    system_prompt="Your name is John Doe.",
    checkpointer="memory",
)
config = {"configurable": {"thread_id": "123"}}
result = await agent_node(  # noqa: F704, PLE1142
    {"messages": [{"role": "user", "content": "What's your name?"}]}, config
)

result["structured_response"]

# %% [markdown]
# ## Structured output with Typed dict

# %%
so_schema = """
class Person(TypedDict):
    \"\"\"A Person.\"\"\"

    name: str
"""

so_config = {
    "schema_type": "typed_dict",
    "schema_str": so_schema,
}

agent_node = Agent(
    name="agent",
    model_settings=model_settings,
    structured_output=so_config,
    system_prompt="Your name is John Doe.",
    checkpointer="memory",
)
config = {"configurable": {"thread_id": "123"}}
result = await agent_node(  # noqa: F704, PLE1142
    {"messages": [{"role": "user", "content": "What's your name?"}]}, config
)

result["structured_response"]

# %% [markdown]
# ## Use a node as a tool

# %% [markdown]
# Main differences of a graph node and a function tool: A graph node only
# receives `state: dict` as input, and returns a dict, while a function tool
# can have arbitrary inputs.

# %%
telegram_node = MessageTelegram(
    name="MessageTelegram",
    token=os.getenv("TELEGRAM_TOKEN"),
)

agent_node = Agent(
    name="agent",
    model_settings=model_settings,
    tools=[telegram_node],
    system_prompt="Your name is John Doe.",
    checkpointer="memory",
)

config = {"configurable": {"thread_id": "123"}}
result = await agent_node(  # noqa: F704, PLE1142
    {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Say hello to {os.getenv('TELEGRAM_CHAT_ID')} using "
                    "message_telegram tool"
                ),
            }
        ]
    },
    config,
)

result["messages"][-2]
