
import time
import csv
from pathlib import Path

import numpy as np


# Benchmark configuration
N = 16_777_216
STRIDES = [1, 2, 4, 8, 16, 32, 64, 128]
WARMUPS = 5
REPEATS = 5


def benchmark_stride(data, stride):
    # Select elements using the requested memory stride.
    view = data[::stride]
    elements_touched = view.size

    # Warmup iterations
    for _ in range(WARMUPS):
        view.sum(dtype=np.float64)

    # Recorded iterations
    times_ns = []
    checksum = 0.0

    for _ in range(REPEATS):
        start = time.perf_counter_ns()
        checksum = view.sum(dtype=np.float64)
        end = time.perf_counter_ns()

        times_ns.append(end - start)

    median_time_ns = float(np.median(times_ns))
    latency_ns = median_time_ns / elements_touched

    return {
        "stride": stride,
        "elements_touched": elements_touched,
        "median_time_ns": round(median_time_ns, 2),
        "latency_ns_per_element": round(latency_ns, 6),
        "checksum": checksum,
    }


def main():
    # Allocate and initialize a contiguous 128 MiB array.
    data = np.ones(N, dtype=np.float64)

    results_dir = Path(__file__).resolve().parent.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    output_file = results_dir / "stride_results.tsv"
    results = []

    print(f"Array elements: {N:,}")
    print(f"Array size: {data.nbytes / (1024 ** 2):.2f} MiB")
    print(f"Warmups: {WARMUPS}, recorded iterations: {REPEATS}")
    print()

    for stride in STRIDES:
        result = benchmark_stride(data, stride)
        results.append(result)

        print(
            f"Stride {stride:3d} | "
            f"Elements: {result['elements_touched']:>10,} | "
            f"Median: {result['median_time_ns']:>12,.0f} ns | "
            f"Latency: {result['latency_ns_per_element']:.6f} ns/element"
        )

    # Write tab-separated results.
    fieldnames = [
        "stride",
        "elements_touched",
        "median_time_ns",
        "latency_ns_per_element",
        "checksum",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
