"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type RunStatus =
  | "queued"
  | "collecting"
  | "analyzing"
  | "drafting"
  | "awaiting_approval"
  | "pushing"
  | "complete"
  | "failed";

type RunSummary = {
  run: {
    id: string;
    created_at: string;
    topic: string;
    recency_days: number;
    status: RunStatus;
    config_json: Record<string, unknown>;
    error_json: Record<string, unknown>;
  };
  document_counts: Record<string, number>;
};

type EvidenceItem = {
  document_id: string;
  quote: string;
  url: string;
  meta?: Record<string, unknown>;
};

type Cluster = {
  id: string;
  run_id: string;
  type: "pain_point" | "highlight";
  label: string;
  summary: string;
  intensity_score: number;
  evidence: EvidenceItem[];
};

type Results = {
  run: { id: string; status: RunStatus; topic: string; recency_days: number };
  clusters: Cluster[];
  ad_assets:
    | null
    | {
        id: string;
        run_id: string;
        rsa_sets: any[];
        qa_report: any;
        final_selection: any;
      };
};

function Badge({ status }: { status: RunStatus }) {
  const color =
    status === "failed"
      ? "bg-red-100 text-red-800 border-red-200"
      : status === "complete"
        ? "bg-emerald-100 text-emerald-800 border-emerald-200"
        : status === "awaiting_approval"
          ? "bg-amber-100 text-amber-800 border-amber-200"
          : "bg-zinc-100 text-zinc-800 border-zinc-200";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${color}`}>
      {status}
    </span>
  );
}

function CharCounter({ value, max }: { value: string; max: number }) {
  const len = value.length;
  const bad = len > max;
  return (
    <div className={`text-[11px] ${bad ? "text-red-700" : "text-zinc-500"}`}>
      {len}/{max}
    </div>
  );
}

export default function RunPage({ params }: { params: { id: string } }) {
  const runId = params.id;
  const backendUrl = useMemo(
    () => process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
    [],
  );

  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [status, setStatus] = useState<RunStatus>("queued");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [selectedSetIdx, setSelectedSetIdx] = useState(0);
  const [headlines, setHeadlines] = useState<string[]>([]);
  const [descriptions, setDescriptions] = useState<string[]>([]);

  const [approvalChecked, setApprovalChecked] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [adGroupId, setAdGroupId] = useState("");
  const [finalUrl, setFinalUrl] = useState("");
  const [dryRunState, setDryRunState] = useState<any>(null);
  const [pushing, setPushing] = useState(false);

  async function fetchSummary() {
    const res = await fetch(`${backendUrl}/api/runs/${runId}`, { cache: "no-store" });
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as RunSummary;
    setSummary(data);
    setStatus(data.run.status);
    return data;
  }

  async function fetchResults() {
    const res = await fetch(`${backendUrl}/api/runs/${runId}/results`, { cache: "no-store" });
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as Results;
    setResults(data);
    return data;
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const s = await fetchSummary();
        if (cancelled) return;
        if (s.run.status === "awaiting_approval" || s.run.status === "complete") {
          const r = await fetchResults();
          if (cancelled) return;
          if (r.ad_assets?.rsa_sets?.length) {
            const set0 = r.ad_assets.rsa_sets[0];
            setSelectedSetIdx(0);
            setHeadlines((set0.headlines || []).slice(0, 35));
            setDescriptions((set0.descriptions || []).slice(0, 12));
          }
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load run");
      } finally {
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [backendUrl, runId]);

  useEffect(() => {
    const es = new EventSource(`${backendUrl}/api/runs/${runId}/stream`);
    es.addEventListener("status", async (evt) => {
      try {
        const data = JSON.parse((evt as MessageEvent).data) as { status: RunStatus };
        setStatus(data.status);
        if (data.status === "awaiting_approval" || data.status === "complete" || data.status === "failed") {
          await fetchSummary();
          if (data.status !== "failed") {
            const r = await fetchResults();
            if (r.ad_assets?.rsa_sets?.length) {
              const set0 = r.ad_assets.rsa_sets[0];
              setSelectedSetIdx(0);
              setHeadlines((set0.headlines || []).slice(0, 35));
              setDescriptions((set0.descriptions || []).slice(0, 12));
            }
          }
          es.close();
        }
      } catch {
        // ignore parse errors
      }
    });
    return () => es.close();
  }, [backendUrl, runId]);

  useEffect(() => {
    // When user changes set selection, load that set for editing.
    if (!results?.ad_assets?.rsa_sets?.length) return;
    const s = results.ad_assets.rsa_sets[selectedSetIdx];
    if (!s) return;
    setHeadlines((s.headlines || []).slice(0, 35));
    setDescriptions((s.descriptions || []).slice(0, 12));
  }, [results, selectedSetIdx]);

  function updateList(
    kind: "headline" | "description",
    idx: number,
    val: string,
  ) {
    if (kind === "headline") {
      setHeadlines((prev) => prev.map((x, i) => (i === idx ? val : x)));
    } else {
      setDescriptions((prev) => prev.map((x, i) => (i === idx ? val : x)));
    }
  }

  async function dryRun() {
    setDryRunState(null);
    const payload = {
      customer_id: customerId.trim(),
      campaign_id: campaignId.trim(),
      ad_group_id: adGroupId.trim(),
      final_url: finalUrl.trim(),
      assets: {
        rsa_sets: [
          {
            theme: results?.ad_assets?.rsa_sets?.[selectedSetIdx]?.theme || "Selected",
            headlines,
            descriptions,
          },
        ],
      },
    };
    const res = await fetch(`${backendUrl}/api/runs/${runId}/dry-run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    setDryRunState({ http_ok: res.ok, ...data });
  }

  async function pushLive() {
    if (!dryRunState?.ok) return;
    if (!approvalChecked) return;
    if (!confirm("Push this RSA live to Google Ads?")) return;
    setPushing(true);
    try {
      const payload = {
        customer_id: customerId.trim(),
        campaign_id: campaignId.trim(),
        ad_group_id: adGroupId.trim(),
        final_url: finalUrl.trim(),
        assets: {
          rsa_sets: [
            {
              theme: results?.ad_assets?.rsa_sets?.[selectedSetIdx]?.theme || "Selected",
              headlines,
              descriptions,
            },
          ],
        },
      };
      const res = await fetch(`${backendUrl}/api/runs/${runId}/push`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setDryRunState((prev: any) => ({ ...prev, push_result: data, push_http_ok: res.ok }));
      await fetchSummary();
    } finally {
      setPushing(false);
    }
  }

  const clusters = results?.clusters || [];
  const painPoints = clusters.filter((c) => c.type === "pain_point");
  const highlights = clusters.filter((c) => c.type === "highlight");

  const collectorErrors = (summary?.run?.error_json as any)?.collectors || {};

  return (
    <div className="grid gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-zinc-500">Run</div>
          <div className="mt-1 text-lg font-semibold tracking-tight">
            {summary?.run.topic || runId}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <Badge status={status} />
            {summary ? (
              <div className="text-xs text-zinc-500">
                last {summary.run.recency_days} days
              </div>
            ) : null}
          </div>
        </div>
        <Link href="/" className="text-sm text-zinc-700 underline">
          New run
        </Link>
      </div>

      {err ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
          Loading…
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <div className="text-sm font-semibold">Collection summary</div>
          <div className="mt-3 grid gap-2 text-sm">
            {Object.entries(summary?.document_counts || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <div className="text-zinc-600">{k}</div>
                <div className="font-medium">{v}</div>
              </div>
            ))}
          </div>
          {Object.keys(collectorErrors).length ? (
            <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-xs">
              <div className="font-semibold text-zinc-700">Collector notes</div>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap text-zinc-700">
                {JSON.stringify(collectorErrors, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <div className="text-sm font-semibold">Status</div>
          <div className="mt-3 text-sm text-zinc-600">
            {status === "awaiting_approval"
              ? "Results ready. Review evidence and RSA drafts, then dry-run validate."
              : status === "failed"
                ? "Run failed. Check collector/pipeline errors."
                : "Processing… (partial results are OK if some APIs fail)"}
          </div>
          {summary?.run?.error_json && Object.keys(summary.run.error_json).length ? (
            <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-xs">
              <div className="font-semibold text-zinc-700">Errors</div>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap text-zinc-700">
                {JSON.stringify(summary.run.error_json, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <div className="text-sm font-semibold">Pain points</div>
          <div className="mt-4 grid gap-4">
            {painPoints.map((c) => (
              <div key={c.id} className="rounded-xl border border-zinc-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="font-semibold">{c.label}</div>
                  <div className="text-xs text-zinc-500">
                    intensity {c.intensity_score.toFixed(1)}
                  </div>
                </div>
                <div className="mt-2 text-sm text-zinc-700 whitespace-pre-wrap">
                  {c.summary}
                </div>
                <div className="mt-3 grid gap-2">
                  {c.evidence?.slice(0, 6).map((e, idx) => (
                    <a
                      key={idx}
                      href={e.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700 hover:bg-zinc-100"
                    >
                      <div className="font-medium text-zinc-900">Evidence</div>
                      <div className="mt-1">{e.quote}</div>
                      <div className="mt-2 text-[11px] text-zinc-500">
                        {e.url}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            ))}
            {!painPoints.length ? (
              <div className="text-sm text-zinc-500">Not ready yet.</div>
            ) : null}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6">
          <div className="text-sm font-semibold">Highlights</div>
          <div className="mt-4 grid gap-4">
            {highlights.map((c) => (
              <div key={c.id} className="rounded-xl border border-zinc-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="font-semibold">{c.label}</div>
                  <div className="text-xs text-zinc-500">
                    intensity {c.intensity_score.toFixed(1)}
                  </div>
                </div>
                <div className="mt-2 text-sm text-zinc-700 whitespace-pre-wrap">
                  {c.summary}
                </div>
                <div className="mt-3 grid gap-2">
                  {c.evidence?.slice(0, 6).map((e, idx) => (
                    <a
                      key={idx}
                      href={e.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700 hover:bg-zinc-100"
                    >
                      <div className="font-medium text-zinc-900">Evidence</div>
                      <div className="mt-1">{e.quote}</div>
                      <div className="mt-2 text-[11px] text-zinc-500">
                        {e.url}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            ))}
            {!highlights.length ? (
              <div className="text-sm text-zinc-500">Not ready yet.</div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-6">
        <div className="flex items-center justify-between gap-4">
          <div className="text-sm font-semibold">RSA drafts</div>
          <div className="text-xs text-zinc-500">
            Headlines ≤ 30 chars · Descriptions ≤ 90 chars
          </div>
        </div>

        {results?.ad_assets?.rsa_sets?.length ? (
          <>
            <div className="mt-4 flex flex-wrap gap-2">
              {results.ad_assets.rsa_sets.map((s: any, i: number) => (
                <button
                  key={i}
                  onClick={() => setSelectedSetIdx(i)}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    i === selectedSetIdx
                      ? "border-zinc-900 bg-zinc-900 text-white"
                      : "border-zinc-200 bg-white text-zinc-700"
                  }`}
                >
                  {s.theme || `Set ${i + 1}`}
                </button>
              ))}
            </div>

            <div className="mt-5 grid gap-6 md:grid-cols-2">
              <div>
                <div className="text-xs font-semibold text-zinc-700">Headlines</div>
                <div className="mt-3 grid gap-2">
                  {headlines.map((h, idx) => (
                    <div key={idx} className="grid gap-1">
                      <input
                        value={h}
                        onChange={(e) => updateList("headline", idx, e.target.value)}
                        className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/10"
                      />
                      <CharCounter value={h} max={30} />
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs font-semibold text-zinc-700">Descriptions</div>
                <div className="mt-3 grid gap-2">
                  {descriptions.map((d, idx) => (
                    <div key={idx} className="grid gap-1">
                      <textarea
                        value={d}
                        onChange={(e) => updateList("description", idx, e.target.value)}
                        rows={2}
                        className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/10"
                      />
                      <CharCounter value={d} max={90} />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
              <div className="text-xs font-semibold text-zinc-700">QA report</div>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs text-zinc-700">
                {JSON.stringify(results.ad_assets.qa_report, null, 2)}
              </pre>
            </div>
          </>
        ) : (
          <div className="mt-3 text-sm text-zinc-500">Not ready yet.</div>
        )}
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-6">
        <div className="text-sm font-semibold">Approve &amp; Push</div>
        <p className="mt-2 text-sm text-zinc-600">
          Dry-run validate first. “Push Live” stays disabled until dry run OK and you explicitly approve.
        </p>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Google Ads customer_id</label>
            <input className="rounded-xl border border-zinc-200 px-3 py-2 text-sm" value={customerId} onChange={(e) => setCustomerId(e.target.value)} placeholder="1234567890" />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">campaign_id</label>
            <input className="rounded-xl border border-zinc-200 px-3 py-2 text-sm" value={campaignId} onChange={(e) => setCampaignId(e.target.value)} placeholder="111111111" />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">ad_group_id</label>
            <input className="rounded-xl border border-zinc-200 px-3 py-2 text-sm" value={adGroupId} onChange={(e) => setAdGroupId(e.target.value)} placeholder="222222222" />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">final_url</label>
            <input className="rounded-xl border border-zinc-200 px-3 py-2 text-sm" value={finalUrl} onChange={(e) => setFinalUrl(e.target.value)} placeholder="https://example.com" />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={dryRun}
            disabled={status !== "awaiting_approval"}
            className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Dry Run Validate
          </button>
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input type="checkbox" checked={approvalChecked} onChange={(e) => setApprovalChecked(e.target.checked)} />
            I approve these assets for push
          </label>
          <button
            onClick={pushLive}
            disabled={!dryRunState?.ok || !approvalChecked || pushing}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {pushing ? "Pushing…" : "Push Live"}
          </button>
        </div>

        {dryRunState ? (
          <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
            <div className="text-xs font-semibold text-zinc-700">Dry run result</div>
            <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs text-zinc-700">
              {JSON.stringify(dryRunState, null, 2)}
            </pre>
          </div>
        ) : null}

        <div className="mt-4 text-xs text-zinc-500">
          Tip: use the backend debug endpoint for raw docs:{" "}
          <a className="underline" href={`${backendUrl}/api/runs/${runId}/documents`} target="_blank" rel="noreferrer">
            /api/runs/{runId}/documents
          </a>
        </div>
      </div>
    </div>
  );
}

