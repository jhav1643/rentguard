import React from "react";

export default function CitationBadge({ status }) {
    const normalized = (status || "unknown").toLowerCase();
    const label =
        normalized === "pass"
            ? "Citations verified"
            : normalized === "fail"
                ? "Citations unverified"
                : "Citation status unknown";

    return <span className={`citation citation-${normalized}`}>{label}</span>;
}