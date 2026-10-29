
import json
import statistics
import time
from pathlib import Path

import numpy as np
from numba import njit

from salt import get_student_params


@njit
def multiply_naive(A, B, C):
    """Algorithm A: i-j-k, with strided access to B."""
    M = A.shape[0]

    for i in range(M):
        for j in range(M):
            total = 0.0
            for k in range(M):
                total += A[i, k] * B[k, j]
            C[i, j] = total


@njit
def multiply_interchanged(A, B, C):
    """Algorithm B: i-k-j, with contiguous row access."""
    M = A.shape[0]

    for i in range(M):
        for k in range(M):
            a_ik = A[i, k]

            for j in range(M):
                C[i, j] += a_ik * B[k, j]


def benchmark(kernel, A, B, runs=3):
    M = A.shape[0]
    times_ms = []
    result = np.zeros((M, M), dtype=np.float64)

    # Compile the Numba function before timing.
    result.fill(0.0)
    kernel(A, B, result)

    for _ in range(runs):
        result.fill(0.0)

        start = time.perf_counter()
        kernel(A, B, result)
        elapsed_ms = (time.perf_counter() - start) * 1000

        times_ms.append(elapsed_ms)

    return {
        "median_ms": statistics.median(times_ms),
        "runs_ms": times_ms,
        "checksum": float(result.sum()),
        "result": result,
    }


def main():
    project_root = Path(__file__).resolve().parent.parent
    params_path = project_root / "results" / "salted_params.json"
    output_path = project_root / "results" / "loop_interchange.json"

    if not params_path.exists():
        raise FileNotFoundError(
            f"{params_path} not found. Run src/salt.py first."
        )

    with params_path.open(encoding="utf-8") as file:
        params = json.load(file)

    N = params["N"]
    seed = params["seed"]
    M = N // 2

    print(f"Salted N: {N}")
    print(f"Benchmark block M: {M}")
    print(f"Seed: {seed}")

    # Initialize full N x N matrices deterministically.
    rng = np.random.default_rng(seed)
    A_full = rng.random((N, N), dtype=np.float64)
    B_full = rng.random((N, N), dtype=np.float64)

    # Benchmark the top-left M x M sub-block.
    A = np.ascontiguousarray(A_full[:M, :M])
    B = np.ascontiguousarray(B_full[:M, :M])

    print("\nRunning naïve i-j-k multiplication...")
    naive = benchmark(multiply_naive, A, B)

    print("Running interchanged i-k-j multiplication...")
    interchanged = benchmark(multiply_interchanged, A, B)

    # Verify that the two algorithms produce equivalent results.
    if not np.allclose(
        naive["result"],
        interchanged["result"],
        rtol=1e-10,
        atol=1e-10,
    ):
        raise AssertionError("FAIL: Matrix results do not match.")

    speedup = naive["median_ms"] / interchanged["median_ms"]

    output = {
        "student_id": params["student_id"],
        "N": N,
        "M": M,
        "seed": seed,
        "matrix_dtype": "float64",
        "runs_per_algorithm": 3,
        "algorithms": {
            "naive_i_j_k": {
                "median_ms": naive["median_ms"],
                "runs_ms": naive["runs_ms"],
                "checksum": naive["checksum"],
            },
            "interchanged_i_k_j": {
                "median_ms": interchanged["median_ms"],
                "runs_ms": interchanged["runs_ms"],
                "checksum": interchanged["checksum"],
            },
        },
        "speedup": speedup,
        "verification": "PASS",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=4)

    print("\n--- Results ---")
    print(f"Naïve median:        {naive['median_ms']:.3f} ms")
    print(f"Interchanged median: {interchanged['median_ms']:.3f} ms")
    print(f"Speedup:             {speedup:.3f}x")
    print("Verification:        PASS")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
