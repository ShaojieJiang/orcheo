import { useEffect, useRef, useState } from "react";

type ExecutionEvent = {
  at: string;
  message: string;
};

type Props = {
  workflowId: string;
};

export function ExecutionPanel({ workflowId }: Props) {
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [status, setStatus] = useState("disconnected");
  const [backendUrl, setBackendUrl] = useState("ws://localhost:8000/ws/workflows");
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  const connect = () => {
    socketRef.current?.close();
    try {
      const socket = new WebSocket(`${backendUrl}/${workflowId}`);
      socket.onopen = () => setStatus("connected");
      socket.onclose = () => setStatus("disconnected");
      socket.onerror = () => setStatus("error");
      socket.onmessage = (event) => {
        setEvents((current) =>
          current.concat({
            at: new Date().toISOString(),
            message: typeof event.data === "string" ? event.data : JSON.stringify(event.data),
          })
        );
      };
      socketRef.current = socket;
    } catch (error) {
      console.warn("Failed to establish websocket", error);
      setStatus("error");
    }
  };

  return (
    <section className="execution-panel">
      <header>
        <h2>Live Execution Stream</h2>
        <p>
          Connect to the backend WebSocket to monitor workflow runs in real time.
        </p>
      </header>
      <div className="execution-panel__controls">
        <label>
          Backend URL
          <input
            value={backendUrl}
            onChange={(event) => setBackendUrl(event.target.value)}
          />
        </label>
        <button type="button" onClick={connect}>
          Connect
        </button>
        <span className={`execution-panel__status execution-panel__status--${status}`}>
          {status}
        </span>
      </div>
      <div className="execution-panel__events" data-testid="execution-events">
        {events.map((event) => (
          <div key={event.at}>
            <time>{event.at}</time>
            <pre>{event.message}</pre>
          </div>
        ))}
        {events.length === 0 ? (
          <p className="execution-panel__empty">No events received yet.</p>
        ) : null}
      </div>
    </section>
  );
}
