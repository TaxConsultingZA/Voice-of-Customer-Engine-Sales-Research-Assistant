import argparse
import random
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import httpx

_SOURCES = ["email", "whatsapp", "zendesk", "web_form", "api"]


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if q <= 0:
        return min(values)
    if q >= 100:
        return max(values)
    sorted_values = sorted(values)
    idx = (len(sorted_values) - 1) * (q / 100.0)
    low = int(idx)
    high = min(low + 1, len(sorted_values) - 1)
    frac = idx - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


def _sample_payload(source: str, seq: int) -> dict:
    arr = random.choice([1200, 15000, 85000, 150000, 250000])
    if source == "email":
        return {
            "text": f"Email login issue #{seq}: cannot log in and payment keeps failing.",
            "customer_id": f"email-user-{seq}",
            "timestamp": "2026-05-15T00:00:00Z",
            "customer_arr": arr,
        }
    if source == "whatsapp":
        return {
            "message_text": f"WhatsApp issue #{seq}: app is slow and login broken.",
            "wa_id": f"2782000{seq:05d}",
            "timestamp": "2026-05-15T00:00:00Z",
            "customer_arr": arr,
        }
    if source == "zendesk":
        return {
            "description": f"Zendesk ticket #{seq}: charged twice and cannot export report.",
            "requester_id": f"zd-{seq}",
            "created_at": "2026-05-15T00:00:00Z",
            "customer_arr": arr,
        }
    if source == "web_form":
        return {
            "feedback": f"Web form #{seq}: dashboard not loading and setup failed.",
            "email": f"user{seq}@example.com",
            "submitted_at": "2026-05-15T00:00:00Z",
            "customer_arr": arr,
        }
    return {
        "content": f"API event #{seq}: webhook sync failed and timeout errors.",
        "account_id": f"acct-{seq}",
        "event_time": "2026-05-15T00:00:00Z",
        "customer_arr": arr,
    }


def run_load_test(base_url: str, total_requests: int, concurrency: int, timeout: float) -> dict:
    endpoint = f"{base_url.rstrip('/')}/api/events"
    lock = threading.Lock()
    latencies: list[float] = []
    status_counts: dict[int, int] = {}
    failures = 0
    start_all = time.perf_counter()

    def send_one(i: int) -> None:
        nonlocal failures
        source = random.choice(_SOURCES)
        body = {"source": source, "payload": _sample_payload(source, i)}
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(endpoint, json=body)
            elapsed = (time.perf_counter() - started) * 1000.0
            with lock:
                latencies.append(elapsed)
                status_counts[resp.status_code] = status_counts.get(resp.status_code, 0) + 1
                if resp.status_code >= 500:
                    failures += 1
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000.0
            with lock:
                latencies.append(elapsed)
                status_counts[0] = status_counts.get(0, 0) + 1
                failures += 1

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(send_one, i) for i in range(total_requests)]
        for f in as_completed(futures):
            f.result()

    elapsed_s = max(time.perf_counter() - start_all, 1e-9)
    success = status_counts.get(201, 0)
    return {
        "total_requests": total_requests,
        "elapsed_seconds": elapsed_s,
        "rps": total_requests / elapsed_s,
        "success_201": success,
        "failure_count": failures,
        "status_counts": dict(sorted(status_counts.items(), key=lambda x: x[0])),
        "latency_ms_mean": statistics.mean(latencies) if latencies else 0.0,
        "latency_ms_p95": _percentile(latencies, 95),
        "latency_ms_p99": _percentile(latencies, 99),
        "latency_ms_max": max(latencies) if latencies else 0.0,
    }


def build_markdown_report(result: dict, base_url: str, concurrency: int, timeout: float) -> str:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    success_rate = (
        (result["success_201"] / result["total_requests"]) * 100.0
        if result["total_requests"]
        else 0.0
    )
    return (
        "# Ingestion Load Test Report\n\n"
        f"Generated at (UTC): {generated_at}\n\n"
        "## Test Configuration\n"
        f"- Base URL: {base_url}\n"
        f"- Total requests: {result['total_requests']}\n"
        f"- Concurrency: {concurrency}\n"
        f"- Timeout (s): {timeout}\n\n"
        "## Outcome\n"
        f"- Success 201: {result['success_201']}\n"
        f"- Failure count: {result['failure_count']}\n"
        f"- Success rate: {success_rate:.2f}%\n"
        f"- Status counts: {result['status_counts']}\n\n"
        "## Performance\n"
        f"- Elapsed seconds: {result['elapsed_seconds']:.2f}\n"
        f"- Throughput (RPS): {result['rps']:.2f}\n"
        f"- Latency mean (ms): {result['latency_ms_mean']:.2f}\n"
        f"- Latency p95 (ms): {result['latency_ms_p95']:.2f}\n"
        f"- Latency p99 (ms): {result['latency_ms_p99']:.2f}\n"
        f"- Latency max (ms): {result['latency_ms_max']:.2f}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run synthetic load test against ingestion API.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Ingestion base URL.")
    parser.add_argument("--requests", type=int, default=1000, help="Total requests.")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent workers.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds.")
    parser.add_argument(
        "--report-output",
        default=None,
        help="Optional markdown report output path (e.g., data/reports/load_test_report.md).",
    )
    args = parser.parse_args()

    result = run_load_test(
        base_url=args.base_url,
        total_requests=max(args.requests, 1),
        concurrency=max(args.concurrency, 1),
        timeout=max(args.timeout, 0.1),
    )

    print("=== Ingestion Load Test Summary ===")
    print(f"Base URL         : {args.base_url}")
    print(f"Total requests   : {result['total_requests']}")
    print(f"Elapsed seconds  : {result['elapsed_seconds']:.2f}")
    print(f"Throughput (RPS) : {result['rps']:.2f}")
    print(f"201 success      : {result['success_201']}")
    print(f"Failure count    : {result['failure_count']}")
    print(f"Status counts    : {result['status_counts']}")
    print(f"Latency mean ms  : {result['latency_ms_mean']:.2f}")
    print(f"Latency p95 ms   : {result['latency_ms_p95']:.2f}")
    print(f"Latency p99 ms   : {result['latency_ms_p99']:.2f}")
    print(f"Latency max ms   : {result['latency_ms_max']:.2f}")

    if args.report_output:
        report_md = build_markdown_report(
            result=result,
            base_url=args.base_url,
            concurrency=max(args.concurrency, 1),
            timeout=max(args.timeout, 0.1),
        )
        report_path = Path(args.report_output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_md, encoding="utf-8")
        print(f"Markdown report written: {report_path}")


if __name__ == "__main__":
    main()
