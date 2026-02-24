"""Example graph demonstrating TaskNode-based data mapping and Telegram integration."""

import asyncio
import os
from dotenv import load_dotenv
from orcheo.graph.builder import build_graph


load_dotenv()


graph_config = {
    "nodes": [
        {"name": "START", "type": "START"},
        {
            "name": "print",
            "type": "DataTransformNode",
            "input_data": {"message": "Hello Orcheo!"},
            "transforms": [{"source": "message", "target": "message"}],
        },
        {
            "name": "telegram",
            "type": "MessageTelegram",
            "token": os.getenv("TELEGRAM_TOKEN"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "message": "{{print.result.message}}",
        },
        {"name": "END", "type": "END"},
    ],
    "edges": [("START", "print"), ("print", "telegram"), ("telegram", "END")],
}

if __name__ == "__main__":
    graph = build_graph(graph_config)
    compiled_graph = graph.compile()
    asyncio.run(compiled_graph.ainvoke({}, None))
