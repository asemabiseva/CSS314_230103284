
import time
import math
from multiprocessing import Pool


def heavy_math(n):
    return sum(
        math.sin(i) * math.cos(i)
        for i in range(1, n)
    )


def run_experiment(workers, total_chunks=16, chunk_size=2_000_000):

    t0 = time.perf_counter()

    # Intentional sequential bottleneck.
    time.sleep(0.40)

    with Pool(processes=workers) as pool:
        pool.map(
            heavy_math,
            [chunk_size] * total_chunks
        )

    return time.perf_counter() - t0


if __name__ == "__main__":

    process_counts = [1, 2, 4]
    runtimes = {}

    print("--- EXPERIMENT A: SERIAL BOTTLENECK ---")
    print("Total chunks: 16")
    print("Chunk size: 2,000,000")
    print("Sequential pause: 0.40 seconds")
    print("-" * 60)

    for p in process_counts:

        elapsed = run_experiment(p)
        runtimes[p] = elapsed

        print(f"P={p} | Time={elapsed:.4f}s")

    # Calculate speedup and Karp-Flatt metric.
    t1 = runtimes[1]

    print("\n--- SPEEDUP AND KARPF-FLATT ANALYSIS ---")

    for p in [2, 4]:

        tp = runtimes[p]

        speedup = t1 / tp

        e = ((p * tp / t1) - 1) / (p - 1)

        print(
            f"P={p} | "
            f"Time={tp:.4f}s | "
            f"Speedup={speedup:.3f}x | "
            f"e(p)={e:.4f}"
        )
