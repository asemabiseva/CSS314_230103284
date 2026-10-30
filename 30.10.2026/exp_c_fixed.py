
import time
from multiprocessing import Pool


def private_worker(iterations):
    # Private local variable. No shared memory or locks.
    local_sum = 0

    for _ in range(iterations):
        local_sum += 1

    return local_sum


def run_privatized(p, total_increments=20_000_000):

    increments_per_worker = total_increments // p

    tasks = [increments_per_worker] * p

    t0 = time.perf_counter()

    with Pool(processes=p) as pool:
        results = pool.map(private_worker, tasks)

    # Combine results once after all workers finish.
    total = sum(results)

    elapsed = time.perf_counter() - t0

    assert total == total_increments, (
        f"Expected {total_increments}, got {total}"
    )

    return elapsed


if __name__ == "__main__":

    cores = [1, 2, 4]
    runtimes = {}

    print("--- EXPERIMENT C: PRIVATIZATION FIX ---")
    print("Total increments: 20,000,000")
    print("-" * 60)

    for p in cores:

        elapsed = run_privatized(p)
        runtimes[p] = elapsed

        print(f"P={p} | Runtime={elapsed:.4f}s")

    # Karp-Flatt analysis.
    t1 = runtimes[1]

    print("\n--- SPEEDUP AND KARPF-FLATT ANALYSIS ---")

    for p in [2, 4]:

        tp = runtimes[p]

        speedup = t1 / tp

        e = ((p * tp / t1) - 1.0) / (p - 1.0)

        print(
            f"P={p} | "
            f"Runtime={tp:.4f}s | "
            f"Speedup={speedup:.2f}x | "
            f"Karp-Flatt e={e:.4f}"
        )

    print("\nPASS: Privatized counter verification successful.")
