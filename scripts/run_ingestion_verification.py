import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def _health_check(name: str, base_url: str, timeout: float) -> dict:
    url = f"{base_url.rstrip('/')}/health"
    try:
        response = requests.get(url, timeout=timeout)
        ok = response.status_code == 200
        return {
            "name": name,
            "url": url,
            "ok": ok,
            "status_code": response.status_code,
            "body": response.text[:500],
            "error": "",
        }
    except Exception as exc:
        return {
            "name": name,
            "url": url,
            "ok": False,
            "status_code": 0,
            "body": "",
            "error": str(exc),
        }


def _run_subprocess(command: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "command": " ".join(command),
    }


def _build_report(
    *,
    generated_at: str,
    health_results: list[dict],
    fail_strategy_result: dict | None,
    load_test_result: dict | None,
    load_report_path: Path,
    overall_ok: bool,
) -> str:
    health_lines = []
    for result in health_results:
        if result["ok"]:
            health_lines.append(
                f"- PASS `{result['name']}` ({result['url']}) status={result['status_code']}"
            )
        else:
            reason = (
                f"status={result['status_code']}"
                if result["status_code"]
                else f"error={result['error']}"
            )
            health_lines.append(f"- FAIL `{result['name']}` ({result['url']}) {reason}")
    health_section = "\n".join(health_lines) if health_lines else "- skipped"

    def _section(name: str, result: dict | None) -> str:
        if result is None:
            return f"## {name}\n- skipped\n"
        status = "PASS" if result["ok"] else "FAIL"
        details = result["stdout"] or result["stderr"] or "(no output)"
        return (
            f"## {name}\n"
            f"- {status} (exit_code={result['returncode']})\n"
            f"- Command: `{result['command']}`\n\n"
            "```text\n"
            f"{details}\n"
            "```\n"
        )

    load_report_line = (
        f"- Generated load report: `{load_report_path}`"
        if load_report_path.exists()
        else f"- Load report not generated: `{load_report_path}`"
    )

    final_status = "PASS" if overall_ok else "FAIL"
    return (
        "# Ingestion Verification Report\n\n"
        f"Generated at (UTC): {generated_at}\n\n"
        "## Overall Status\n"
        f"- {final_status}\n\n"
        "## Health Checks\n"
        f"{health_section}\n\n"
        f"{_section('Fail Strategy Verification', fail_strategy_result)}\n"
        f"{_section('Load Test Execution', load_test_result)}\n"
        "## Artifacts\n"
        f"{load_report_line}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-command verification: health checks + fail strategy + load test."
    )
    parser.add_argument("--ingestion-url", default="http://localhost:8000")
    parser.add_argument("--redactor-url", default="http://localhost:8080")
    parser.add_argument("--nlp-url", default="http://localhost:8081")
    parser.add_argument("--health-timeout", type=float, default=3.0)
    parser.add_argument("--load-requests", type=int, default=500)
    parser.add_argument("--load-concurrency", type=int, default=30)
    parser.add_argument("--load-timeout", type=float, default=5.0)
    parser.add_argument("--skip-fail-strategy", action="store_true")
    parser.add_argument("--skip-load-test", action="store_true")
    parser.add_argument("--strict-health", action="store_true")
    parser.add_argument(
        "--output",
        default="data/reports/ingestion_verification_report.md",
        help="Markdown summary output path.",
    )
    args = parser.parse_args()

    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    output_path = ROOT / args.output
    load_report_path = output_path.parent / "load_test_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    health_results = [
        _health_check("ingestion", args.ingestion_url, timeout=max(args.health_timeout, 0.1)),
        _health_check("redactor", args.redactor_url, timeout=max(args.health_timeout, 0.1)),
        _health_check("nlp", args.nlp_url, timeout=max(args.health_timeout, 0.1)),
    ]
    all_health_ok = all(item["ok"] for item in health_results)

    python_exec = sys.executable
    fail_result = None
    if not args.skip_fail_strategy:
        fail_result = _run_subprocess(
            [python_exec, "scripts/verify_ingestion_fail_strategy.py"],
            cwd=ROOT,
        )

    load_result = None
    if not args.skip_load_test:
        load_result = _run_subprocess(
            [
                python_exec,
                "scripts/load_test_ingestion.py",
                "--base-url",
                args.ingestion_url,
                "--requests",
                str(max(args.load_requests, 1)),
                "--concurrency",
                str(max(args.load_concurrency, 1)),
                "--timeout",
                str(max(args.load_timeout, 0.1)),
                "--report-output",
                str(load_report_path),
            ],
            cwd=ROOT,
        )

    checks = []
    if args.strict_health:
        checks.append(all_health_ok)
    if fail_result is not None:
        checks.append(fail_result["ok"])
    if load_result is not None:
        checks.append(load_result["ok"])
    overall_ok = all(checks) if checks else all_health_ok

    report = _build_report(
        generated_at=generated_at,
        health_results=health_results,
        fail_strategy_result=fail_result,
        load_test_result=load_result,
        load_report_path=load_report_path,
        overall_ok=overall_ok,
    )
    output_path.write_text(report, encoding="utf-8")

    print(f"Verification report written: {output_path}")
    print(f"Overall status: {'PASS' if overall_ok else 'FAIL'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
