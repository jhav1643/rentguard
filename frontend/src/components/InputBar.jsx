import React, { useState } from "react";

export default function InputBar({ onSend, onCancel, loading }) {
    const [value, setValue] = useState("");

    function submit() {
        const trimmed = value.trim();
        if (!trimmed || loading) return;
        onSend(trimmed);
        setValue("");
    }

    function onKeyDown(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
        }
    }

    return (
        <footer className="input-bar">
            <textarea
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Ask about rent control, eviction, deposits…  (Enter to send, Shift+Enter for newline)"
                rows={2}
                disabled={loading}
            />
            {loading ? (
                <button className="cancel-button" onClick={onCancel}>
                    Cancel
                </button>
            ) : (
                <button
                    className="send-button"
                    onClick={submit}
                    disabled={!value.trim()}
                >
                    Send
                </button>
            )}
        </footer>
    );
}