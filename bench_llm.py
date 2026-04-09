#!/usr/bin/env python3
"""
Benchmark local Ollama chat models for speed and basic response quality.

Why this exists:
- Tiny models vary a lot by hardware and quantization.
- The fastest model on paper is not always fastest on your Pi.
- This script gives a simple apples-to-apples comparison.
"""

import argparse
import statistics
import time
from typing import Any

import ollama


PROMPTS = [
    # Short factual prompt: measures quick response latency.
    "In one sentence, explain what DNS does.",
    # Structured prompt: tests instruction following.
    "Return exactly 3 bullet points about why backups matter.",
    # Reasoning-lite prompt with constrained output length.
    "Give two quick ideas to reduce Python app startup time on Raspberry Pi.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local Ollama models for speed and consistency."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "qwen2.5:0.5b",
            "smollm2:360m",
            "smollm2:135m",
            "llama3.2:1b",
        ],
        help="Model names to benchmark.",
    )
    parser.add_argument(
        "--ctx",
        type=int,
        default=1024,
        help="Context window used for all model runs.",
    )
    parser.add_argument(
        "--predict",
        type=int,
        default=64,
        help="Maximum generated tokens per prompt.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature for all runs.",
    )
    parser.add_argument(
        "--keep-alive",
        default="30m",
        help="How long Ollama should keep model in memory.",
    )
    return parser.parse_args()


def estimate_score(text: str) -> int:
    """
    A tiny heuristic score (0-3):
    - not empty
    - has enough content length
    - follows structured bullet request for prompt 2 when applicable
    This is intentionally simple, just to avoid picking nonsense-fast outputs.
    """
    if not text.strip():
        return 0
    score = 1
    if len(text.split()) >= 8:
        score += 1
    bullet_markers = ("- ", "* ", "• ")
    if any(marker in text for marker in bullet_markers):
        score += 1
    return min(score, 3)


def run_prompt(model: str, prompt: str, options: dict[str, Any], keep_alive: str) -> tuple[float, str]:
    messages = [
        {
            "role": "system",
            "content": "You are concise and follow format exactly.",
        },
        {"role": "user", "content": prompt},
    ]
    start = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=messages,
        options=options,
        keep_alive=keep_alive,
    )
    elapsed = time.perf_counter() - start
    text = response["message"]["content"]
    return elapsed, text


def benchmark_model(model: str, options: dict[str, Any], keep_alive: str) -> dict[str, Any]:
    # Warm load so first request does not dominate results.
    try:
        ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            options=options,
            keep_alive=keep_alive,
        )
    except Exception as err:
        return {"model": model, "error": str(err)}

    timings = []
    scores = []
    samples = []
    for prompt in PROMPTS:
        elapsed, output = run_prompt(model, prompt, options, keep_alive)
        timings.append(elapsed)
        scores.append(estimate_score(output))
        samples.append(output.replace("\n", " ")[:100])

    avg_latency = statistics.mean(timings)
    p95_latency = max(timings)
    quality_score = statistics.mean(scores)
    speed_score = 1.0 / max(avg_latency, 1e-6)
    combined = (speed_score * 0.7) + (quality_score * 0.3)
    return {
        "model": model,
        "avg_latency_s": avg_latency,
        "p95_latency_s": p95_latency,
        "quality_score": quality_score,
        "combined_score": combined,
        "samples": samples,
    }


def main() -> int:
    args = parse_args()
    options = {
        "num_ctx": args.ctx,
        "num_predict": args.predict,
        "temperature": args.temperature,
    }

    # Quick connectivity check for clearer error.
    try:
        ollama.ps()
    except Exception as err:
        print("Could not connect to Ollama. Start it with: `ollama serve`")
        print(f"Details: {err}")
        return 1

    results: list[dict[str, Any]] = []
    for model in args.models:
        print(f"\n--- Benchmarking {model} ---")
        result = benchmark_model(model, options, args.keep_alive)
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(
                f"avg={result['avg_latency_s']:.2f}s "
                f"p95={result['p95_latency_s']:.2f}s "
                f"quality={result['quality_score']:.2f} "
                f"combined={result['combined_score']:.3f}"
            )
            for idx, sample in enumerate(result["samples"], start=1):
                print(f"  sample{idx}: {sample}")
        results.append(result)

    valid = [r for r in results if "error" not in r]
    if not valid:
        print("\nNo successful model runs.")
        return 2

    ranked = sorted(valid, key=lambda r: r["combined_score"], reverse=True)
    print("\n=== Ranking (higher is better) ===")
    for i, row in enumerate(ranked, start=1):
        print(
            f"{i}. {row['model']} | combined={row['combined_score']:.3f} "
            f"| avg={row['avg_latency_s']:.2f}s | quality={row['quality_score']:.2f}"
        )

    winner = ranked[0]["model"]
    print(f"\nRecommended default model: {winner}")
    print(f"Run with: ZUBO_MODEL={winner} ./start.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
