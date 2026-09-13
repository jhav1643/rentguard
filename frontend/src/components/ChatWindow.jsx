import React, { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";

export default function ChatWindow({ messages, loading }) {
    const endRef = useRef(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

    return (
        <main className="chat-window">
            {messages.map((m, i) => (
                <MessageBubble key={i} message={m} />
            ))}

            {loading && (
                <div className="message assistant">
                    <div className="bubble typing">
                        <span className="dot" />
                        <span className="dot" />
                        <span className="dot" />
                    </div>
                </div>
            )}

            <div ref={endRef} />
        </main>
    );
}