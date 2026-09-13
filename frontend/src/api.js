const BASE = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
    const res = await fetch(`${BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });

    if (!res.ok) {
        let detail = "";
        try {
            const body = await res.json();
            detail = body.error || body.detail || "";
        } catch {
            // ignore
        }
        throw new Error(`API ${res.status}${detail ? `: ${detail}` : ""}`);
    }

    return res.json();
}

export async function askQuestion(question, jurisdiction, signal) {
    return request("/chat", {
        method: "POST",
        body: JSON.stringify({ question, jurisdiction }),
        signal,
    });
}

export async function health() {
    return request("/health");
}