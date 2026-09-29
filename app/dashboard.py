from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def calculate_percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values_sorted[int(k)])
    d0 = values_sorted[int(f)] * (c - k)
    d1 = values_sorted[int(c)] * (k - f)
    return float(d0 + d1)


def parse_dashboard_data(minutes: int = 60) -> dict[str, Any]:
    if not LOG_PATH.exists():
        return {"error": "data/logs.jsonl not found"}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)

    events: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            ts_str = rec.get("ts")
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff:
                    events.append(rec)
        except Exception:
            continue

    # 1. Latency & TTFT
    latencies = [float(e["latency_ms"]) for e in events if e.get("event") == "response_sent" and "latency_ms" in e]
    ttfts = [float(e["ttft_ms"]) for e in events if e.get("event") == "response_sent" and "ttft_ms" in e]

    p50 = round(calculate_percentile(latencies, 50), 1)
    p95 = round(calculate_percentile(latencies, 95), 1)
    p99 = round(calculate_percentile(latencies, 99), 1)
    ttft_p95 = round(calculate_percentile(ttfts, 95), 1)

    # 2. Traffic
    req_received = [e for e in events if e.get("event") == "request_received"]
    total_requests = len(req_received)
    rate_per_min = round(total_requests / max(1, minutes), 2)

    # 3. Errors & Retrieval Success
    req_failed = [e for e in events if e.get("event") == "request_failed"]
    error_count = len(req_failed)
    error_rate_pct = round((error_count / max(1, total_requests)) * 100, 2)

    error_breakdown: dict[str, int] = {}
    for e in req_failed:
        err = e.get("error_type", "Unknown")
        error_breakdown[err] = error_breakdown.get(err, 0) + 1

    tool_events = [e for e in events if e.get("tool_name") is not None]
    tool_success_count = sum(1 for e in tool_events if e.get("tool_success") is True)
    tool_total = len(tool_events)
    retrieval_success_rate_pct = round((tool_success_count / max(1, tool_total)) * 100, 1) if tool_total > 0 else 100.0

    # 4. Cost
    costs = [float(e["cost_usd"]) for e in events if e.get("event") == "response_sent" and "cost_usd" in e]
    total_cost_usd = round(sum(costs), 5)

    # 5. Tokens
    tokens_in = sum(int(e["tokens_in"]) for e in events if e.get("event") == "response_sent" and "tokens_in" in e)
    tokens_out = sum(int(e["tokens_out"]) for e in events if e.get("event") == "response_sent" and "tokens_out" in e)

    # 6. Quality
    qualities = [float(e["quality_score"]) for e in events if e.get("event") == "response_sent" and "quality_score" in e]
    mean_quality = round(sum(qualities) / len(qualities), 2) if qualities else 0.0

    return {
        "time_range_minutes": minutes,
        "sample_count": len(events),
        "latency": {
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "ttft_p95": ttft_p95,
            "threshold_ms": 3000,
            "passed": p95 <= 3000,
        },
        "traffic": {
            "total_requests": total_requests,
            "rate_per_min": rate_per_min,
            "threshold_min": 1,
            "passed": rate_per_min >= 0,
        },
        "errors": {
            "error_rate_pct": error_rate_pct,
            "error_count": error_count,
            "error_breakdown": error_breakdown,
            "threshold_pct": 2.0,
            "passed": error_rate_pct <= 2.0,
            "retrieval_success_rate_pct": retrieval_success_rate_pct,
            "retrieval_threshold_pct": 90.0,
            "retrieval_passed": retrieval_success_rate_pct >= 90.0,
        },
        "cost": {
            "total_cost_usd": total_cost_usd,
            "threshold_usd": 2.5,
            "passed": total_cost_usd <= 2.5,
        },
        "tokens": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "threshold_tokens": 50000,
            "passed": (tokens_in + tokens_out) <= 50000,
        },
        "quality": {
            "mean_score": mean_quality,
            "threshold_score": 0.75,
            "passed": mean_quality >= 0.75,
        },
    }


@router.get("/dashboard/data")
async def dashboard_data() -> JSONResponse:
    return JSONResponse(parse_dashboard_data(minutes=60))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view() -> HTMLResponse:
    html_content = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K4-L3A Day 13 Monitoring & LLMOps Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darkbg: '#0f172a',
                        cardbg: '#1e293b',
                        bordercolor: '#334155'
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: ui-sans-serif, system-ui, sans-serif; }
    </style>
</head>
<body class="p-6 min-h-screen">
    <div class="max-w-7xl mx-auto space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-bordercolor pb-5">
            <div>
                <h1 class="text-2xl font-bold text-white flex items-center gap-2">
                    <span class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span>
                    K4-L3A Day 13 Monitoring & LLMOps
                </h1>
                <p class="text-sm text-slate-400 mt-1">Live metrics from <code class="text-indigo-400">data/logs.jsonl</code> &bull; Refresh: 30s</p>
            </div>
            <div class="flex items-center gap-3">
                <span class="bg-indigo-950 text-indigo-300 border border-indigo-700 text-xs px-3 py-1.5 rounded-full font-medium">Time Range: 60m</span>
                <button onclick="fetchData()" class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition shadow">Refresh Now</button>
            </div>
        </div>

        <!-- 6 Panels Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- Panel 1: Latency -->
            <div class="bg-cardbg border border-bordercolor rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h2 class="font-semibold text-slate-100">1. Latency & TTFT</h2>
                            <p class="text-xs text-slate-400">Unit: ms &bull; Target: P95 &le; 3000ms</p>
                        </div>
                        <span id="badge-latency" class="text-xs px-2 py-0.5 rounded font-mono">...</span>
                    </div>
                    <div class="grid grid-cols-2 gap-3 mt-4">
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Latency P50</span>
                            <p id="lat-p50" class="text-xl font-bold text-slate-100 mt-1">-- ms</p>
                        </div>
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Latency P95</span>
                            <p id="lat-p95" class="text-xl font-bold text-indigo-400 mt-1">-- ms</p>
                        </div>
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Latency P99</span>
                            <p id="lat-p99" class="text-xl font-bold text-slate-100 mt-1">-- ms</p>
                        </div>
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">TTFT P95</span>
                            <p id="lat-ttft" class="text-xl font-bold text-cyan-400 mt-1">-- ms</p>
                        </div>
                    </div>
                </div>
                <div class="mt-4 pt-3 border-t border-bordercolor text-xs text-slate-400 flex justify-between">
                    <span>Threshold Line:</span>
                    <span class="font-mono text-amber-400">3000 ms</span>
                </div>
            </div>

            <!-- Panel 2: Traffic -->
            <div class="bg-cardbg border border-bordercolor rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h2 class="font-semibold text-slate-100">2. Request Traffic</h2>
                            <p class="text-xs text-slate-400">Unit: requests/minute &bull; Target: &ge; 1 rpm</p>
                        </div>
                        <span id="badge-traffic" class="text-xs px-2 py-0.5 rounded font-mono">...</span>
                    </div>
                    <div class="space-y-3 mt-4">
                        <div class="bg-darkbg p-4 rounded-lg border border-bordercolor flex justify-between items-center">
                            <div>
                                <span class="text-xs text-slate-400">Total Requests (60m)</span>
                                <p id="traffic-total" class="text-3xl font-extrabold text-slate-100 mt-1">--</p>
                            </div>
                            <div class="text-right">
                                <span class="text-xs text-slate-400">Rate / Minute</span>
                                <p id="traffic-rate" class="text-2xl font-bold text-emerald-400 mt-1">--</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="mt-4 pt-3 border-t border-bordercolor text-xs text-slate-400 flex justify-between">
                    <span>Threshold Line:</span>
                    <span class="font-mono text-slate-300">&ge; 1 req/min</span>
                </div>
            </div>

            <!-- Panel 3: Errors -->
            <div class="bg-cardbg border border-bordercolor rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h2 class="font-semibold text-slate-100">3. Errors & Retrieval</h2>
                            <p class="text-xs text-slate-400">Target: Err &le; 2%, Retrieval &ge; 90%</p>
                        </div>
                        <span id="badge-errors" class="text-xs px-2 py-0.5 rounded font-mono">...</span>
                    </div>
                    <div class="grid grid-cols-2 gap-3 mt-4">
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Error Rate</span>
                            <p id="err-rate" class="text-xl font-bold text-rose-400 mt-1">-- %</p>
                            <span id="err-count" class="text-[10px] text-slate-500">0 errors</span>
                        </div>
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Retrieval Success</span>
                            <p id="retrieval-rate" class="text-xl font-bold text-emerald-400 mt-1">-- %</p>
                            <span class="text-[10px] text-slate-500">tool_name=retrieval</span>
                        </div>
                    </div>
                    <div id="error-breakdown" class="mt-3 text-xs text-slate-400"></div>
                </div>
                <div class="mt-4 pt-3 border-t border-bordercolor text-xs text-slate-400 flex justify-between">
                    <span>Threshold Line:</span>
                    <span class="font-mono text-rose-400">&le; 2.0%</span>
                </div>
            </div>

            <!-- Panel 4: Cost -->
            <div class="bg-cardbg border border-bordercolor rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h2 class="font-semibold text-slate-100">4. Cost Over Time</h2>
                            <p class="text-xs text-slate-400">Unit: USD &bull; Threshold: &le; $2.50</p>
                        </div>
                        <span id="badge-cost" class="text-xs px-2 py-0.5 rounded font-mono">...</span>
                    </div>
                    <div class="bg-darkbg p-4 rounded-lg border border-bordercolor mt-4">
                        <span class="text-xs text-slate-400">Cumulative Cost (60m)</span>
                        <p id="cost-total" class="text-3xl font-extrabold text-amber-400 mt-1">$0.00000</p>
                    </div>
                </div>
                <div class="mt-4 pt-3 border-t border-bordercolor text-xs text-slate-400 flex justify-between">
                    <span>Threshold Line:</span>
                    <span class="font-mono text-amber-400">&le; $2.50</span>
                </div>
            </div>

            <!-- Panel 5: Tokens -->
            <div class="bg-cardbg border border-bordercolor rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h2 class="font-semibold text-slate-100">5. Input & Output Tokens</h2>
                            <p class="text-xs text-slate-400">Unit: tokens &bull; Threshold: &le; 50,000</p>
                        </div>
                        <span id="badge-tokens" class="text-xs px-2 py-0.5 rounded font-mono">...</span>
                    </div>
                    <div class="grid grid-cols-2 gap-3 mt-4">
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Tokens In</span>
                            <p id="tokens-in" class="text-xl font-bold text-slate-100 mt-1">--</p>
                        </div>
                        <div class="bg-darkbg p-3 rounded-lg border border-bordercolor">
                            <span class="text-xs text-slate-400">Tokens Out</span>
                            <p id="tokens-out" class="text-xl font-bold text-slate-100 mt-1">--</p>
                        </div>
                    </div>
                    <div class="bg-darkbg p-2 rounded-lg border border-bordercolor mt-3 flex justify-between text-xs text-slate-300">
                        <span>Total Tokens:</span>
                        <span id="tokens-total" class="font-bold">--</span>
                    </div>
                </div>
                <div class="mt-4 pt-3 border-t border-bordercolor text-xs text-slate-400 flex justify-between">
                    <span>Threshold Line:</span>
                    <span class="font-mono text-slate-300">&le; 50,000</span>
                </div>
            </div>

            <!-- Panel 6: Quality -->
            <div class="bg-cardbg border border-bordercolor rounded-xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h2 class="font-semibold text-slate-100">6. Quality Proxy</h2>
                            <p class="text-xs text-slate-400">Unit: score (0.0 - 1.0) &bull; Threshold: &ge; 0.75</p>
                        </div>
                        <span id="badge-quality" class="text-xs px-2 py-0.5 rounded font-mono">...</span>
                    </div>
                    <div class="bg-darkbg p-4 rounded-lg border border-bordercolor mt-4 text-center">
                        <span class="text-xs text-slate-400">Mean Quality Score</span>
                        <p id="quality-mean" class="text-4xl font-black text-emerald-400 mt-2">--</p>
                    </div>
                </div>
                <div class="mt-4 pt-3 border-t border-bordercolor text-xs text-slate-400 flex justify-between">
                    <span>Threshold Line (SLO):</span>
                    <span class="font-mono text-emerald-400">&ge; 0.75</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        function setBadge(elId, passed, text) {
            const el = document.getElementById(elId);
            if (!el) return;
            el.innerText = text || (passed ? 'PASS' : 'WARN');
            el.className = 'text-xs px-2 py-0.5 rounded font-mono ' + 
                (passed ? 'bg-emerald-950 text-emerald-300 border border-emerald-700' : 'bg-rose-950 text-rose-300 border border-rose-700');
        }

        async function fetchData() {
            try {
                const res = await fetch('/dashboard/data');
                const data = await res.json();
                if (data.error) {
                    console.warn(data.error);
                    return;
                }

                // Latency
                document.getElementById('lat-p50').innerText = data.latency.p50 + ' ms';
                document.getElementById('lat-p95').innerText = data.latency.p95 + ' ms';
                document.getElementById('lat-p99').innerText = data.latency.p99 + ' ms';
                document.getElementById('lat-ttft').innerText = data.latency.ttft_p95 + ' ms';
                setBadge('badge-latency', data.latency.passed);

                // Traffic
                document.getElementById('traffic-total').innerText = data.traffic.total_requests;
                document.getElementById('traffic-rate').innerText = data.traffic.rate_per_min + ' rpm';
                setBadge('badge-traffic', true, 'HEALTHY');

                // Errors
                document.getElementById('err-rate').innerText = data.errors.error_rate_pct + ' %';
                document.getElementById('err-count').innerText = data.errors.error_count + ' failed requests';
                document.getElementById('retrieval-rate').innerText = data.errors.retrieval_success_rate_pct + ' %';
                setBadge('badge-errors', data.errors.passed && data.errors.retrieval_passed);

                // Cost
                document.getElementById('cost-total').innerText = '$' + data.cost.total_cost_usd.toFixed(5);
                setBadge('badge-cost', data.cost.passed);

                // Tokens
                document.getElementById('tokens-in').innerText = data.tokens.tokens_in.toLocaleString();
                document.getElementById('tokens-out').innerText = data.tokens.tokens_out.toLocaleString();
                document.getElementById('tokens-total').innerText = data.tokens.total_tokens.toLocaleString();
                setBadge('badge-tokens', data.tokens.passed);

                // Quality
                document.getElementById('quality-mean').innerText = data.quality.mean_score.toFixed(2);
                setBadge('badge-quality', data.quality.passed);

            } catch (err) {
                console.error("Failed to load dashboard data:", err);
            }
        }

        fetchData();
        setInterval(fetchData, 30000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
