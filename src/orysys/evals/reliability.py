import argparse
import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any

import httpx

from orysys.api.app import create_app
from orysys.config import Settings


async def run_load_smoke(request_count: int = 25, concurrency: int = 5) -> dict[str, Any]:
    if request_count < 1 or concurrency < 1:
        raise ValueError("request_count and concurrency must be positive")
    app = create_app(
        Settings(
            environment="test",
            use_fake_adapters=True,
            auth_enabled=False,
            rate_limit_capacity=request_count + 1,
        )
    )
    transport = httpx.ASGITransport(app=app)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(transport=transport, base_url="http://orysys.test") as client:

        async def request() -> tuple[int, float]:
            async with semaphore:
                started = time.perf_counter()
                response = await client.post("/v1/conversations")
                elapsed_ms = (time.perf_counter() - started) * 1_000
                return response.status_code, elapsed_ms

        results = await asyncio.gather(*(request() for _ in range(request_count)))

    latencies = sorted(latency for _, latency in results)
    failures = sum(status != 201 for status, _ in results)
    return {
        "suite": "local-load-smoke-v1",
        "profile": "deterministic-fake",
        "request_count": request_count,
        "concurrency": concurrency,
        "failures": failures,
        "latency_ms": {
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
            "max": round(max(latencies), 3),
        },
        "provider_calls": 0,
        "estimated_provider_cost_usd": 0.0,
    }


def _percentile(values: list[float], percentile: float) -> float:
    index = max(0, math.ceil(len(values) * percentile) - 1)
    return values[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the credential-free API load smoke")
    parser.add_argument("--requests", type=int, default=25)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("evals/results/local-load-smoke-v1.json")
    )
    args = parser.parse_args()
    report = asyncio.run(run_load_smoke(args.requests, args.concurrency))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{json.dumps(report, indent=2, sort_keys=True)}\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
