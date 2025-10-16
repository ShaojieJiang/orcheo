"""Example of using the Feedly news API to get the latest news and send to Telegram."""

import asyncio
import os
from typing import Any
import httpx
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.telegram import MessageTelegram, escape_markdown


class FeedlyToken(TaskNode):
    """Node for getting the Feedly token."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the code and return results."""
        # Ensure the code contains a return statement
        chrome_options = Options()
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--start-maximized")
        chrome_options.debugger_address = "localhost:9222"

        driver = webdriver.Chrome(options=chrome_options)

        try:
            driver.get("https://feedly.com/i/console")
            WebDriverWait(driver, 5).until(
                ec.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(), 'Your Feedly Token')]")
                )
            )

            # Then try to get the token value
            token = driver.execute_script("""
                const header = document.evaluate("//*[contains(text(), 'Your Feedly Token')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (header) {
                    const nextElement = header.nextElementSibling;
                    return nextElement ? nextElement.textContent : null;
                }
                return null;
            """)  # noqa: E501

            if token:
                return {"feedly_token": token}
            else:
                return {"feedly_token": "Token value not found"}

        except TimeoutException:
            return {"feedly_token": "Page load or token element not found"}
        except Exception as e:
            return {"feedly_token": f"An error occurred: {e}"}
        finally:
            driver.quit()


class GetFeedlyUnread(TaskNode):
    """Node for getting the Feedly unread count."""

    user_id: str
    token: str = "{{FeedlyToken.feedly_token}}"
    count: int = 30
    url: str = "https://cloud.feedly.com/v3/streams/contents?streamId=user/{user_id}/category/global.all&count={count}&unreadOnly=true"

    def decode_title(self, title: str) -> str:
        """Decode HTML entities in title."""
        return (
            title.replace("&quot;", '"')
            .replace("&apos;", "'")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&nbsp;", " ")
            .replace("[", "<")
            .replace("]", ">")
        )

    def format_text(self, news: dict[str, Any]) -> str:
        """Format the text to be sent to Telegram."""
        titles = []
        for item in news["items"]:
            title = escape_markdown(self.decode_title(item["title"]))
            url = escape_markdown(item["alternate"][0]["href"])
            titles.append(f"• [{title}]({url})")
        return "\n".join(titles)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the code and return results."""
        # Ensure the code contains a return statement
        token = f"OAuth {self.token}"
        if not token:
            return {"feedly_unread": "No token found"}

        response = httpx.get(
            self.url.format(user_id=self.user_id, count=self.count),
            headers={"Authorization": token},
        )
        formatted_text = self.format_text(response.json())

        return {
            "feedly_unread": formatted_text,
            "entry_ids": [item["id"] for item in response.json()["items"]],
        }


class MarkFeedlyAsRead(TaskNode):
    """Node for marking the Feedly as read."""

    token: str = "{{FeedlyToken.feedly_token}}"
    url: str = "https://cloud.feedly.com/v3/markers"
    send_status: str = "{{MessageTelegram.status}}"
    entry_ids: list[str] = "{{GetFeedlyUnread.entry_ids}}"

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the code and return results."""
        # Ensure the code contains a return statement
        if self.send_status != "sent":
            return {"feedly_mark_as_read": "No send status found"}

        token = f"OAuth {self.token}"
        if not token:
            return {"feedly_mark_as_read": "No token found"}

        response = httpx.post(
            self.url,
            headers={"Authorization": token},
            json={
                "action": "markAsRead",
                "type": "entries",
                "entryIds": self.entry_ids,
            },
        )
        return {"status": response.status_code}


if __name__ == "__main__":
    graph = StateGraph(State)
    graph.add_node("FeedlyToken", FeedlyToken(name="FeedlyToken"))
    graph.add_node(
        "GetFeedlyUnread",
        GetFeedlyUnread(
            name="GetFeedlyUnread", user_id=os.getenv("FEEDLY_USER_ID"), count=30
        ),
    )
    graph.add_node(
        "MessageTelegram",
        MessageTelegram(
            name="MessageTelegram",
            token=os.getenv("TELEGRAM_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            parse_mode="MarkdownV2",
            message="{{GetFeedlyUnread.feedly_unread}}",
        ),
    )
    graph.add_node(
        "MarkFeedlyAsRead",
        MarkFeedlyAsRead(name="MarkFeedlyAsRead"),
    )

    graph.add_edge(START, "FeedlyToken")
    graph.add_edge("FeedlyToken", "GetFeedlyUnread")
    graph.add_edge("GetFeedlyUnread", "MessageTelegram")
    graph.add_edge("MessageTelegram", END)
    # graph.add_edge("MessageTelegram", "MarkFeedlyAsRead")
    # graph.add_edge("MarkFeedlyAsRead", END)

    compiled_graph = graph.compile()
    result = asyncio.run(
        compiled_graph.ainvoke({"inputs": {}, "results": {}, "messages": []})
    )
    print(result["results"]["MarkFeedlyAsRead"]["status"])
