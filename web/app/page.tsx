"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [recencyDays, setRecencyDays] = useState<7 | 14 | 30>(14);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = topic.trim();
    if (!trimmed) {
      setError("Please enter a topic.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`/api/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: trimmed, recency_days: recencyDays }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { run_id: string };
      router.push(`/runs/${data.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create run");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-8">
      <div className="rounded-2xl border border-zinc-200 bg-white p-6">
        <h1 className="text-xl font-semibold tracking-tight">
          Generate RSA ideas from the last 7–30 days
        </h1>
        <p className="mt-2 text-sm text-zinc-600">
          We’ll collect discussion from Reddit, X, and YouTube, cluster pain
          points + highlights with evidence, draft RSA sets, run QA, then let
          you dry-run validate and push to Google Ads after explicit approval.
        </p>

        <form onSubmit={onSubmit} className="mt-6 grid gap-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Topic</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. 'AI meeting notes' or 'organic skincare routine'"
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-zinc-900/10"
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Recency window</label>
            <select
              value={recencyDays}
              onChange={(e) => setRecencyDays(Number(e.target.value) as 7 | 14 | 30)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-zinc-900/10"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
          </div>

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-60"
          >
            {submitting ? "Starting…" : "Run analysis"}
          </button>
        </form>
      </div>
    </div>
  );
}
