"""
Run all synthetic DSR requests through the resolver and measure performance
against ground truth. Emits results/benchmark.json + a console summary.

Metrics reported:
  - Precision / Recall / F1 on the resolution decision
  - Auto-merge rate (straight-through processing, no human in loop)
  - Confidence-band breakdown
  - Avg sources fused per resolved subject (the multi-DB fan-in payoff)
"""
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from idres.loader import build_resolver, load_dsr  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "results"
RESULTS.mkdir(exist_ok=True)


def main():
    t0 = time.time()
    resolver = build_resolver()
    build_ms = (time.time() - t0) * 1000

    dsr = load_dsr()
    t1 = time.time()
    results = [resolver.search(req) for req in dsr]
    search_ms = (time.time() - t1) * 1000

    tp = fp = fn = 0
    bands = {"AUTO_MERGE": 0, "REVIEW": 0, "NO_MATCH": 0}
    correct_auto = 0
    fused = []
    confs = []
    for r in results:
        bands[r.decision] += 1
        confs.append(r.confidence)
        resolved = r.decision in ("AUTO_MERGE", "REVIEW")
        hit = resolved and r.matched_truth == r.request_truth
        if resolved and hit:
            tp += 1
            fused.append(len(r.matched_sources))
        elif resolved and not hit:
            fp += 1
        elif not resolved:
            fn += 1
        if r.decision == "AUTO_MERGE" and hit:
            correct_auto += 1

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    auto_rate = bands["AUTO_MERGE"] / len(dsr)
    auto_precision = correct_auto / bands["AUTO_MERGE"] if bands["AUTO_MERGE"] else 0

    summary = {
        "total_dsr_requests": len(dsr),
        "customer_db_records": len(resolver.pool),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "auto_merge_rate": round(auto_rate, 3),
        "auto_merge_precision": round(auto_precision, 3),
        "avg_sources_fused": round(statistics.mean(fused), 2) if fused else 0,
        "mean_confidence": round(statistics.mean(confs), 3),
        "confidence_bands": bands,
        "index_build_ms": round(build_ms, 1),
        "search_total_ms": round(search_ms, 1),
        "search_ms_per_request": round(search_ms / len(dsr), 2),
    }

    with open(RESULTS / "benchmark.json", "w") as f:
        json.dump({"summary": summary,
                   "sample": [vars(r) for r in results[:10]]}, f, indent=2)

    print("\n=== Identity Resolution Benchmark (synthetic) ===")
    for k, v in summary.items():
        print(f"{k:>26}: {v}")
    print("\nSaved -> results/benchmark.json")


if __name__ == "__main__":
    main()
