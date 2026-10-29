
import multiprocessing as mp
import ctypes
import time
import csv
import os

ITERATIONS = 5_000_000
PROCESS_COUNTS = [1, 2, 4, 8]
INTEGERS_PER_CACHE_LINE = 8


# Task 2.1: Unpadded counters
def worker_unpadded(shared_arr, worker_id, iterations):
    for _ in range(iterations):
        shared_arr[worker_id] += 1


# Task 2.2.1: Padded counters
def worker_padded(shared_arr, worker_id, iterations):
    index = worker_id * INTEGERS_PER_CACHE_LINE

    for _ in range(iterations):
        shared_arr[index] += 1


# Task 2.2.2: Thread-local privatization
def worker_privatized(shared_arr, worker_id, iterations):
    local_count = 0

    # Increment a private local variable.
    for _ in range(iterations):
        local_count += 1

    # Write the final result once, using a shared lock.
    with shared_arr.get_lock():
        shared_arr[worker_id] = local_count


def run_benchmark(strategy, process_count):
    if strategy == "unpadded":
        shared_arr = mp.Array(
            ctypes.c_int64, process_count, lock=False
        )
        worker = worker_unpadded

    elif strategy == "padded":
        shared_arr = mp.Array(
            ctypes.c_int64,
            process_count * INTEGERS_PER_CACHE_LINE,
            lock=False
        )
        worker = worker_padded

    elif strategy == "privatized":
        shared_arr = mp.Array(
            ctypes.c_int64, process_count, lock=True
        )
        worker = worker_privatized

    else:
        raise ValueError("Unknown strategy")

    processes = []
    start = time.perf_counter()

    for worker_id in range(process_count):
        process = mp.Process(
            target=worker,
            args=(shared_arr, worker_id, ITERATIONS)
        )
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

    elapsed = time.perf_counter() - start

    # Check correctness.
    if strategy == "padded":
        results = [
            shared_arr[p * INTEGERS_PER_CACHE_LINE]
            for p in range(process_count)
        ]
    else:
        results = [shared_arr[p] for p in range(process_count)]

    passed = (
        all(value == ITERATIONS for value in results)
        and all(p.exitcode == 0 for p in processes)
    )

    print(
        f"{strategy:12s} | P={process_count:2d} | "
        f"Time={elapsed:.4f} s | PASS={passed}"
    )

    return elapsed


if __name__ == "__main__":
    mp.freeze_support()

    timings = {
        strategy: {}
        for strategy in ["unpadded", "padded", "privatized"]
    }

    for strategy in timings:
        print(f"\n{strategy.upper()} COUNTERS")
        print("-" * 55)

        for p in PROCESS_COUNTS:
            timings[strategy][p] = run_benchmark(strategy, p)

    print("\nFINAL PERFORMANCE COMPARISON")
    print("-" * 75)
    print(
        f"{'P':>3} | {'Unpadded (s)':>14} | "
        f"{'Padded (s)':>12} | {'Privatized (s)':>15}"
    )
    print("-" * 75)

    for p in PROCESS_COUNTS:
        print(
            f"{p:3d} | "
            f"{timings['unpadded'][p]:14.4f} | "
            f"{timings['padded'][p]:12.4f} | "
            f"{timings['privatized'][p]:15.4f}"
        )

    print("\nSPEEDUP RELATIVE TO ONE PROCESS")
    print("-" * 65)

    for strategy in timings:
        baseline = timings[strategy][1]
        print(f"\n{strategy.upper()}")

        for p in PROCESS_COUNTS:
            speedup = baseline / timings[strategy][p]
            print(f"P={p:2d}: {speedup:.3f}x")


    
    # Task 2.3: Karp-Flatt metric
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(
        output_dir, "false_sharing_karp_flatt.tsv"
    )

    with open(output_file, "w", newline="") as file:
        writer = csv.writer(file, delimiter="\t")

        writer.writerow([
            "strategy",
            "P",
            "T1_seconds",
            "TP_seconds",
            "speedup",
            "karp_flatt_e"
        ])

        for strategy in ["unpadded", "padded"]:
            T1 = timings[strategy][1]

            for p in [2, 4, 8]:
                TP = timings[strategy][p]
                speedup = T1 / TP

                e = (p * TP / T1 - 1) / (p - 1)

                writer.writerow([
                    strategy,
                    p,
                    f"{T1:.6f}",
                    f"{TP:.6f}",
                    f"{speedup:.6f}",
                    f"{e:.6f}"
                ])

    print(f"\nKarp-Flatt results saved to: {output_file}")

