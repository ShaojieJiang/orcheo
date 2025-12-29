"""WeCom AI bot responder workflow.

Configure WeCom to send AI bot callbacks to:
`/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`

Configurable inputs (workflow_config.json):
- reply_message (fixed response content)
- reply_msg_type (text, markdown, template_card)
- use_passive_reply (bool, default True)
- receive_id (optional receive_id for encryption validation)

Orcheo vault secrets required:
- wecom_aibot_token: AI bot callback token
- wecom_aibot_encoding_aes_key: AI bot encoding AES key
"""

from langgraph.graph import END, StateGraph
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.wecom import (
    WeComAIBotEventsParserNode,
    WeComAIBotPassiveReplyNode,
    WeComAIBotResponseNode,
)


async def build_graph() -> StateGraph:
    """Build the WeCom AI bot responder workflow."""
    graph = StateGraph(State)

    graph.add_node(
        "wecom_ai_bot_events_parser",
        WeComAIBotEventsParserNode(
            name="wecom_ai_bot_events_parser",
            receive_id="{{config.configurable.receive_id}}",
        ),
    )

    graph.add_node(
        "passive_reply",
        WeComAIBotPassiveReplyNode(
            name="passive_reply",
            msg_type="{{config.configurable.reply_msg_type}}",
            content="{{config.configurable.reply_message}}",
            receive_id="{{config.configurable.receive_id}}",
        ),
    )

    graph.add_node(
        "active_reply",
        WeComAIBotResponseNode(
            name="active_reply",
            msg_type="{{config.configurable.reply_msg_type}}",
            content="{{config.configurable.reply_message}}",
        ),
    )

    graph.set_entry_point("wecom_ai_bot_events_parser")

    immediate_response_router = IfElse(
        name="immediate_response_router",
        conditions=[
            Condition(
                left="{{wecom_ai_bot_events_parser.immediate_response}}",
                operator="is_truthy",
            ),
            Condition(
                left="{{wecom_ai_bot_events_parser.should_process}}",
                operator="is_falsy",
            ),
        ],
        condition_logic="or",
    )

    reply_mode_router = IfElse(
        name="reply_mode_router",
        conditions=[
            Condition(
                left="{{config.configurable.use_passive_reply}}",
                operator="is_truthy",
            )
        ],
    )

    graph.add_conditional_edges(
        "wecom_ai_bot_events_parser",
        immediate_response_router,
        {
            "true": END,
            "false": "route_reply_mode",
        },
    )

    graph.add_node("route_reply_mode", lambda _: {})
    graph.add_conditional_edges(
        "route_reply_mode",
        reply_mode_router,
        {
            "true": "passive_reply",
            "false": "active_reply",
        },
    )

    graph.add_edge("passive_reply", END)
    graph.add_edge("active_reply", END)

    return graph
