
import time
from multiprocessing import Pool


def collatz_steps(n):
    steps = 0

    while n > 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1

        steps += 1

    return steps


def run_granularity(workers, total_items=1_000_000, chunk_size=1):
    numbers = range(1, total_items + 1)

    t0 = time.perf_counter()

    with Pool(processes=workers) as pool:
        results = pool.map(
            collatz_steps,
            numbers,
            chunksize=chunk_size
        )

    elapsed = time.perf_counter() - t0

    return elapsed, sum(results)


if __name__ == "__main__":

    workers = 6

    chunk_sizes = [1, 10, 100, 1_000, 10_000]

    print("EXPERIMENT A: THE GRANULARITY TRAP")
    print(f"Workers: {workers}")
    print(f"Total items: 1,000,000")
    print("-" * 55)

    for chunk in chunk_sizes:
        elapsed, checksum = run_granularity(
            workers,
            total_items=1_000_000,
            chunk_size=chunk
        )

        print(
            f"Chunk size: {chunk:>6} | "
            f"Time: {elapsed:.4f} sec | "
            f"Checksum: {checksum}"
        )
