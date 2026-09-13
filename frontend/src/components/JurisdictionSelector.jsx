import React from "react";

const JURISDICTIONS = [
    { value: "delhi", label: "Delhi" },
    { value: "mumbai", label: "Mumbai" },
    { value: "bangalore", label: "Bangalore" },
    { value: "chennai", label: "Chennai" },
    { value: "kolkata", label: "Kolkata" },
];

export default function JurisdictionSelector({ value, onChange, disabled }) {
    return (
        <label className="jurisdiction">
            <span className="jurisdiction-label">Jurisdiction</span>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                disabled={disabled}
            >
                {JURISDICTIONS.map((j) => (
                    <option key={j.value} value={j.value}>
                        {j.label}
                    </option>
                ))}
            </select>
        </label>
    );
}