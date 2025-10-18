import { FormEvent, useState } from "react";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type Props = {
  workflowId: string;
};

export function ChatPanel({ workflowId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const generateId = () =>
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setMessages((current) =>
      current.concat({ id: generateId(), role: "user", content: trimmed })
    );
    setInput("");
    setIsStreaming(true);
    await new Promise((resolve) => setTimeout(resolve, 150));
    setMessages((current) =>
      current.concat({
        id: generateId(),
        role: "assistant",
        content: `Workflow ${workflowId} received: ${trimmed}`,
      })
    );
    setIsStreaming(false);
  };

  return (
    <section className="chat-panel">
      <header>
        <h2>Chat-based Testing</h2>
        <p>Simulate ChatKit-style interactions for workflow validation.</p>
      </header>
      <div className="chat-panel__messages" data-testid="chat-messages">
        {messages.map((message) => (
          <div key={message.id} className={`chat-panel__bubble chat-panel__bubble--${message.role}`}>
            <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
            <p>{message.content}</p>
          </div>
        ))}
        {messages.length === 0 ? (
          <p className="chat-panel__empty">Start a conversation to preview responses.</p>
        ) : null}
      </div>
      <form onSubmit={sendMessage} className="chat-panel__form">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask the workflow to run a scenario..."
        />
        <button type="submit" disabled={isStreaming}>
          {isStreaming ? "Streaming..." : "Send"}
        </button>
      </form>
    </section>
  );
}
