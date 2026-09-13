import React from "react";

import CitationBadge from "./CitationBadge";
import SourceList from "./SourceList";

export default function MessageBubble({ message }) {
    const { role, text, sources, citation, isError } = message;
    const isUser = role === "user";

    return (
        <div className={`message ${isUser ? "user" : "assistant"}`}>
            <div className={`bubble ${isError ? "bubble-error" : ""}`}>
                <p className="bubble-text">{text}</p>

                {!isUser && citation && <CitationBadge status={citation} />}
                {!isUser && sources?.length > 0 && <SourceList sources={sources} />}
            </div>
        </div>
    );
}