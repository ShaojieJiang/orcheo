"""Example graph demonstrating Python code and Telegram integration."""

import asyncio
import os
from dotenv import load_dotenv
from aic_flow.graph import build_graph


load_dotenv()


graph_config = {
    "nodes": [
        {"name": "START", "type": "START"},
        {
            "name": "print",
            "type": "PythonCode",
            "code": """
return {"message": "Hello AIC!"}
""",
        },
        {
            "name": "telegram",
            "type": "TelegramMessage",
            "token": os.getenv("TELEGRAM_TOKEN"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "message": "{{print.message}}",
        },
        {"name": "END", "type": "END"},
    ],
    "edges": [("START", "print"), ("print", "telegram"), ("telegram", "END")],
}

if __name__ == "__main__":
    graph = build_graph(graph_config)
    compiled_graph = graph.compile()
    asyncio.run(compiled_graph.ainvoke({}))
