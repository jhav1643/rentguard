import { useCallback, useRef, useState } from "react";
import { askQuestion } from "../api";

const INITIAL_MESSAGE = {
    role: "assistant",
    text: "Hi! Ask me anything about rental law in your selected jurisdiction.",
    sources: [],
    citation: null,
};

export function useChat() {
    const [messages, setMessages] = useState([INITIAL_MESSAGE]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const abortRef = useRef(null);

    const send = useCallback(
        async (question, jurisdiction) => {
            const trimmed = question.trim();
            if (!trimmed || loading) return;

            setError(null);
            setMessages((m) => [...m, { role: "user", text: trimmed }]);
            setLoading(true);

            const controller = new AbortController();
            abortRef.current = controller;

            try {
                const data = await askQuestion(trimmed, jurisdiction, controller.signal);
                setMessages((m) => [
                    ...m,
                    {
                        role: "assistant",
                        text: data.answer || "(no answer)",
                        sources: data.sources || [],
                        citation: data.citation_check || "unknown",
                    },
                ]);
            } catch (err) {
                if (err.name === "AbortError") return;
                setError(err.message);
                setMessages((m) => [
                    ...m,
                    {
                        role: "assistant",
                        text: `Error: ${err.message}`,
                        sources: [],
                        citation: "fail",
                        isError: true,
                    },
                ]);
            } finally {
                setLoading(false);
                abortRef.current = null;
            }
        },
        [loading]
    );

    const cancel = useCallback(() => {
        if (abortRef.current) abortRef.current.abort();
    }, []);

    const reset = useCallback(() => {
        setMessages([INITIAL_MESSAGE]);
        setError(null);
    }, []);

    return { messages, loading, error, send, cancel, reset };
}