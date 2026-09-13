import React, { useState } from "react";
import ChatWindow from "./components/ChatWindow";
import InputBar from "./components/InputBar";
import JurisdictionSelector from "./components/JurisdictionSelector";
import { useChat } from "./hooks/useChat";

const APP_NAME = import.meta.env.VITE_APP_NAME || "RentGuard";

export default function App() {
    const [jurisdiction, setJurisdiction] = useState("delhi");
    const { messages, loading, error, send, cancel, reset } = useChat();

    return (
        <div className="app">
            <header className="app-header">
                <div className="app-header-left">
                    <h1>{APP_NAME}</h1>
                    <span className="app-subtitle">Rental-law RAG assistant</span>
                </div>
                <div className="app-header-right">
                    <JurisdictionSelector
                        value={jurisdiction}
                        onChange={setJurisdiction}
                        disabled={loading}
                    />
                    <button
                        className="ghost-button"
                        onClick={reset}
                        disabled={loading || messages.length <= 1}
                    >
                        New chat
                    </button>
                </div>
            </header>

            {error && <div className="error-banner">{error}</div>}

            <ChatWindow messages={messages} loading={loading} />

            <InputBar
                onSend={(q) => send(q, jurisdiction)}
                onCancel={cancel}
                loading={loading}
            />
        </div>
    );
}