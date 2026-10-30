
import time
from multiprocessing import Process, Queue


def buffered_worker(out_queue, start_index, items_per_worker,
                    batch_size=10_000):

    buffer = []

    for i in range(start_index, start_index + items_per_worker):
        buffer.append(i % 7)

        if len(buffer) >= batch_size:
            out_queue.put(sum(buffer))
            buffer.clear()

    # Send remaining items.
    if buffer:
        out_queue.put(sum(buffer))

    # Signal that this worker has finished.
    out_queue.put(None)


def run_buffered(p, total_items=10_000_000, batch_size=10_000):

    q = Queue()

    items_per_worker = total_items // p

    workers = [
        Process(
            target=buffered_worker,
            args=(
                q,
                worker_id * items_per_worker,
                items_per_worker,
                batch_size
            )
        )
        for worker_id in range(p)
    ]

    t0 = time.perf_counter()

    for w in workers:
        w.start()

    total_sum = 0
    active = p

    # Consume batches until all workers finish.
    while active > 0:
        val = q.get()

        if val is None:
            active -= 1
        else:
            total_sum += val

    for w in workers:
        w.join()

    elapsed = time.perf_counter() - t0

    q.close()
    q.join_thread()

    return elapsed, total_sum


if __name__ == "__main__":

    cores = [1, 2, 4, 8]

    runtimes = {}
    checksums = {}

    total_items = 10_000_000

    print("--- EXPERIMENT C: LOCAL BUFFER CHUNKING ---")
    print(f"Total items: {total_items:,}")
    print("Batch size: 10,000")
    print("-" * 65)

    for p in cores:

        elapsed, checksum = run_buffered(
            p,
            total_items=total_items,
            batch_size=10_000
        )

        runtimes[p] = elapsed
        checksums[p] = checksum

        print(
            f"P={p:2d} | "
            f"Time={elapsed:.4f}s | "
            f"Checksum={checksum}"
        )

    # Karp-Flatt analysis.
    t1 = runtimes[1]

    print("\n--- KARP-FLATT ANALYSIS ---")

    for p in [2, 4, 8]:

        tp = runtimes[p]

        speedup = t1 / tp

        e = ((p * tp / t1) - 1.0) / (p - 1.0)

        print(
            f"P={p:2d} | "
            f"Time={tp:.4f}s | "
            f"Speedup={speedup:.2f}x | "
            f"Karp-Flatt e={e:.4f}"
        )

    # Verify results.
    print("\n--- VERIFICATION ---")

    if len(set(checksums.values())) == 1:
        print("PASS: All worker counts produced the same checksum.")
    else:
        print("FAIL: Checksum mismatch.")
