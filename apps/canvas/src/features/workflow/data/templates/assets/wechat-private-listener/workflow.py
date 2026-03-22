from langgraph.graph import END, START, StateGraph
from orcheo_plugin_wechat_listener import WechatListenerPluginNode, WechatReplyNode
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode, AgentReplyExtractorNode


def orcheo_workflow() -> StateGraph:
    """Build a private WeChat listener workflow backed by the plugin."""
    graph = StateGraph(State)

    graph.add_node(
        "wechat_listener",
        WechatListenerPluginNode(
            name="wechat_listener",
            account_id="[[wechat_account_id]]",
            bot_token="[[wechat_bot_token]]",
            base_url="[[wechat_base_url]]",
            bot_identity_key="wechat:primary",
        ),
    )
    graph.add_node(
        "agent_reply",
        AgentNode(
            name="agent_reply",
            ai_model="{{config.configurable.ai_model}}",
            system_prompt="{{config.configurable.system_prompt}}",
            model_kwargs={"api_key": "[[openai_api_key]]"},
            use_graph_chat_history=True,
        ),
    )
    graph.add_node(
        "extract_reply",
        AgentReplyExtractorNode(name="extract_reply"),
    )
    graph.add_node(
        "send_wechat",
        WechatReplyNode(
            name="send_wechat",
            account_id="[[wechat_account_id]]",
            bot_token="[[wechat_bot_token]]",
            base_url="[[wechat_base_url]]",
            message="{{results.extract_reply.agent_reply}}",
            reply_target="{{results.wechat_listener.reply_target}}",
            raw_event="{{results.wechat_listener.raw_event}}",
        ),
    )

    graph.add_edge(START, "wechat_listener")
    graph.add_edge("wechat_listener", "agent_reply")
    graph.add_edge("agent_reply", "extract_reply")
    graph.add_edge("extract_reply", "send_wechat")
    graph.add_edge("send_wechat", END)
    return graph
