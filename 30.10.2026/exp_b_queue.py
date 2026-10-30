
import time
from multiprocessing import Process, Queue


def queue_worker(out_queue, items_per_worker):
    for i in range(items_per_worker):
        # Every result crosses the IPC boundary.
        out_queue.put(i % 7)


def run_queue_benchmark(p, total_items=400_000):
    q = Queue()

    items_per_worker = total_items // p

    workers = [
        Process(
            target=queue_worker,
            args=(q, items_per_worker)
        )
        for _ in range(p)
    ]

    t0 = time.perf_counter()

    # Start all workers.
    for w in workers:
        w.start()

    # Master process consumes all results.
    collected = 0

    while collected < total_items:
        q.get()
        collected += 1

    # Wait for workers to finish.
    for w in workers:
        w.join()

    elapsed = time.perf_counter() - t0

    q.close()
    q.join_thread()

    return elapsed


if __name__ == "__main__":

    cores = [1, 2, 4, 8]

    runtimes = {}

    print("--- EXPERIMENT B: QUEUE CONTENTION ---")

    for p in cores:
        runtimes[p] = run_queue_benchmark(p)
        print(f"P={p} | Time={runtimes[p]:.4f}s")

    # Karp-Flatt analysis
    t1 = runtimes[1]

    print("\n--- Queue Contention Karp-Flatt Analysis ---")

    for p in [2, 4, 8]:
        tp = runtimes[p]

        speedup = t1 / tp

        e = ((p * tp / t1) - 1.0) / (p - 1.0)

        print(
            f"P={p:2d} | "
            f"Time={tp:6.3f}s | "
            f"Speedup={speedup:5.2f}x | "
            f"Karp-Flatt e={e:6.3f}"
        )
