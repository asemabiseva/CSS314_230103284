
import time
from multiprocessing import Process, Value, Lock


def contended_worker(shared_counter, lock, iterations):

    for _ in range(iterations):
        with lock:
            # Every increment requires exclusive lock access.
            shared_counter.value += 1


def run_contended(p, total_increments=2_000_000):

    increments_per_worker = total_increments // p

    counter = Value('i', 0)
    lock = Lock()

    procs = [
        Process(
            target=contended_worker,
            args=(counter, lock, increments_per_worker)
        )
        for _ in range(p)
    ]

    t0 = time.perf_counter()

    for proc in procs:
        proc.start()

    for proc in procs:
        proc.join()

    elapsed = time.perf_counter() - t0

    # Verify the final counter.
    assert counter.value == total_increments, (
        f"Expected {total_increments}, got {counter.value}"
    )

    return elapsed


if __name__ == "__main__":

    cores = [1, 2, 4]
    runtimes = {}

    print("--- EXPERIMENT B: LOCK CONTENTION ---")
    print("Total increments: 2,000,000")
    print("-" * 60)

    for p in cores:
        runtimes[p] = run_contended(p)
        print(f"P={p} | Runtime={runtimes[p]:.3f}s")

    # Karp-Flatt analysis.
    t1 = runtimes[1]

    print("\n--- KARPF-FLATT ANALYSIS ---")

    for p in [2, 4]:

        tp = runtimes[p]

        speedup = t1 / tp

        e = ((p * tp / t1) - 1.0) / (p - 1.0)

        print(
            f"P={p} | "
            f"Runtime={tp:.3f}s | "
            f"Speedup={speedup:.2f}x | "
            f"Karp-Flatt e={e:.3f}"
        )

    print("\nPASS: Shared counter verification successful.")
