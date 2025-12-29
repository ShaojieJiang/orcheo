"""WeCom bot responder workflow for direct messages.

This workflow handles messages from both:
1. Internal WeCom users (企业微信成员) - direct app messages
2. External WeChat users (微信用户) - via Customer Service (微信客服)

Configure WeCom to send callback requests to:
`/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`
so signatures can be verified.

Configurable inputs (workflow_config.json):
- corp_id (WeCom corp ID)
- agent_id (WeCom app agent ID, for internal users)
- reply_message (fixed response content)

Orcheo vault secrets required:
- wecom_corp_secret: WeCom app secret for access token (internal users)
- wecom_mp_secret: WeCom Customer Service app secret (external users)
- wecom_token: Callback token for signature validation
- wecom_encoding_aes_key: AES key for callback decryption
"""

from langgraph.graph import END, StateGraph
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.wecom import (
    WeComAccessTokenNode,
    WeComCustomerServiceSendNode,
    WeComCustomerServiceSyncNode,
    WeComEventsParserNode,
    WeComSendMessageNode,
)


async def build_graph() -> StateGraph:
    """Build the WeCom bot responder workflow."""
    graph = StateGraph(State)

    # Parse the incoming callback event (handles both internal and CS events)
    graph.add_node(
        "wecom_events_parser",
        WeComEventsParserNode(
            name="wecom_events_parser",
            corp_id="{{config.configurable.corp_id}}",
        ),
    )

    # --- Internal WeCom user path ---
    graph.add_node(
        "get_access_token",
        WeComAccessTokenNode(
            name="get_access_token",
            corp_id="{{config.configurable.corp_id}}",
        ),
    )

    graph.add_node(
        "send_message",
        WeComSendMessageNode(
            name="send_message",
            agent_id="{{config.configurable.agent_id}}",
            message="{{config.configurable.reply_message}}",
        ),
    )

    # --- External WeChat user path (Customer Service) ---
    graph.add_node(
        "wecom_cs_sync",
        WeComCustomerServiceSyncNode(
            name="wecom_cs_sync",
            corp_id="{{config.configurable.corp_id}}",
        ),
    )

    graph.add_node(
        "wecom_cs_send",
        WeComCustomerServiceSendNode(
            name="wecom_cs_send",
            corp_id="{{config.configurable.corp_id}}",
            message="{{config.configurable.reply_message}}",
        ),
    )

    # Entry point
    graph.set_entry_point("wecom_events_parser")

    # First router: check if we should stop or continue processing
    # Stop if: immediate_response exists OR should_process is false
    immediate_response_router = IfElse(
        name="immediate_response_router",
        conditions=[
            Condition(
                left="{{wecom_events_parser.immediate_response}}",
                operator="is_truthy",
            ),
            Condition(
                left="{{wecom_events_parser.should_process}}",
                operator="is_falsy",
            ),
        ],
        condition_logic="or",
    )

    # Second router: route to internal or CS path based on is_customer_service
    message_type_router = IfElse(
        name="message_type_router",
        conditions=[
            Condition(
                left="{{wecom_events_parser.is_customer_service}}",
                operator="is_truthy",
            ),
        ],
    )

    # Route from parser: stop, or continue to type-based routing
    graph.add_conditional_edges(
        "wecom_events_parser",
        immediate_response_router,
        {
            "true": END,  # Immediate response or nothing to process
            "false": "route_by_type",  # Continue to message type routing
        },
    )

    # Virtual routing node to split internal vs CS paths
    graph.add_node("route_by_type", lambda _: {})
    graph.add_conditional_edges(
        "route_by_type",
        message_type_router,
        {
            "true": "wecom_cs_sync",  # External WeChat user: sync CS messages
            "false": "get_access_token",  # Internal WeCom user: get token
        },
    )

    # --- Internal user path ---
    graph.add_edge("get_access_token", "send_message")
    graph.add_edge("send_message", END)

    # --- External user (CS) path ---
    # After syncing, check if we have a message to respond to
    cs_sync_router = IfElse(
        name="cs_sync_router",
        conditions=[
            Condition(
                left="{{wecom_cs_sync.should_process}}",
                operator="is_falsy",
            ),
        ],
    )
    graph.add_conditional_edges(
        "wecom_cs_sync",
        cs_sync_router,
        {
            "true": END,  # No message from external user
            "false": "wecom_cs_send",  # Send reply
        },
    )
    graph.add_edge("wecom_cs_send", END)

    return graph
