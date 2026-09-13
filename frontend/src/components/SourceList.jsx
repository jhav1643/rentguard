import React, { useState } from "react";

export default function SourceList({ sources }) {
    const [open, setOpen] = useState(false);

    return (
        <div className="sources">
            <button className="sources-toggle" onClick={() => setOpen((v) => !v)}>
                {open ? "Hide" : "Show"} {sources.length} source
                {sources.length === 1 ? "" : "s"}
            </button>

            {open && (
                <ul className="sources-list">
                    {sources.map((s, i) => (
                        <li key={i} className="source-item">
                            <div className="source-title">
                                {s.title || s.source || `Source ${i + 1}`}
                            </div>
                            {s.page != null && (
                                <div className="source-meta">page {s.page}</div>
                            )}
                            {s.score != null && (
                                <div className="source-meta">
                                    score {Number(s.score).toFixed(3)}
                                </div>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}