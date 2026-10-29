
import os
import time
import csv
import multiprocessing as mp
from multiprocessing import shared_memory

import numpy as np

try:
    import psutil
    PHYSICAL_CORES = psutil.cpu_count(logical=False) or os.cpu_count() or 1
except ImportError:
    PHYSICAL_CORES = os.cpu_count() or 1


# Replace with the N_salted value specified in your assignment.
N_SALTED = 1152
SEED = 16454

_input = None
_output = None
_input_shm = None
_output_shm = None


def init_worker(input_name, output_name, shape):
    """Attach each worker to the shared input and output matrices."""
    global _input, _output, _input_shm, _output_shm

    _input_shm = shared_memory.SharedMemory(name=input_name)
    _output_shm = shared_memory.SharedMemory(name=output_name)

    _input = np.ndarray(
        shape, dtype=np.float64, buffer=_input_shm.buf
    )
    _output = np.ndarray(
        shape, dtype=np.float64, buffer=_output_shm.buf
    )


def stencil_chunk(bounds):
    """Compute a five-point stencil for a chunk of matrix rows."""
    start, end = bounds
    n = _input.shape[0]

    # Leave the outer matrix boundary unchanged.
    row_start = max(start, 1)
    row_end = min(end, n - 1)

    if row_start >= row_end:
        return

    _output[row_start:row_end, 1:-1] = (
        _input[row_start - 1:row_end - 1, 1:-1]
        + _input[row_start + 1:row_end + 1, 1:-1]
        + _input[row_start:row_end, :-2]
        + _input[row_start:row_end, 2:]
    ) * 0.25


def make_chunks(n, workers):
    """Divide the matrix into approximately equal row ranges."""
    boundaries = np.linspace(
        0, n, workers + 1, dtype=int
    )
    return [
        (int(boundaries[i]), int(boundaries[i + 1]))
        for i in range(workers)
    ]


def run_benchmark(matrix, workers, reference=None):
    n = matrix.shape[0]

    input_shm = shared_memory.SharedMemory(
        create=True, size=matrix.nbytes
    )
    output_shm = shared_memory.SharedMemory(
        create=True, size=matrix.nbytes
    )

    shared_input = np.ndarray(
        matrix.shape, dtype=np.float64, buffer=input_shm.buf
    )
    shared_output = np.ndarray(
        matrix.shape, dtype=np.float64, buffer=output_shm.buf
    )

    shared_input[:] = matrix
    shared_output[:] = matrix

    chunks = make_chunks(n, workers)

    try:
        start = time.perf_counter()

        with mp.Pool(
            processes=workers,
            initializer=init_worker,
            initargs=(
                input_shm.name,
                output_shm.name,
                matrix.shape
            )
        ) as pool:
            pool.map(stencil_chunk, chunks)

        elapsed = time.perf_counter() - start

        correct = True
        if reference is not None:
            correct = np.allclose(shared_output, reference)

        return elapsed, correct

    finally:
        input_shm.close()
        input_shm.unlink()
        output_shm.close()
        output_shm.unlink()


def make_worker_counts(max_cores):
    """Use powers of two and include the maximum physical core count."""
    counts = [1]
    p = 2

    while p <= max_cores:
        counts.append(p)
        p *= 2

    if max_cores not in counts:
        counts.append(max_cores)

    return sorted(set(counts))


def make_stencil_reference(matrix):
    """Calculate the correct result for a five-point stencil."""
    reference = matrix.copy()
    reference[1:-1, 1:-1] = (
        matrix[:-2, 1:-1]
        + matrix[2:, 1:-1]
        + matrix[1:-1, :-2]
        + matrix[1:-1, 2:]
    ) * 0.25
    return reference


def run_weak_scaling(base_n, worker_counts):
    print("\nWEAK SCALING STUDY")
    print("=" * 80)
    print(
        f"{'P':>4} | {'Matrix N':>10} | {'Work':>14} | "
        f"{'Time (s)':>10} | {'Scaled speedup':>15} | {'Correct':>8}"
    )
    print("-" * 80)

    results = []
    base_work = base_n * base_n
    base_time = None

    rng = np.random.default_rng(SEED)

    for p in worker_counts:
        # Increase matrix dimension proportionally to sqrt(P).
        n_p = int(np.ceil(base_n * np.sqrt(p)))
        matrix = rng.random((n_p, n_p), dtype=np.float64)
        reference = make_stencil_reference(matrix)

        # Existing function from Task 3.1.
        runs = []
        correct = True

        for _ in range(3):
            elapsed, run_correct = run_benchmark(
                matrix, p, reference
            )
            runs.append(elapsed)
            correct = correct and run_correct

        elapsed = float(np.median(runs))
        work = n_p * n_p

        if p == 1:
            base_time = elapsed

        # Formula specified in Task 3.2.
        scaled_speedup = (
            p * base_work * base_time / (work * elapsed)
        )

        print(
            f"{p:4d} | {n_p:10d} | {work:14,d} | "
            f"{elapsed:10.4f} | {scaled_speedup:15.3f} | "
            f"{str(correct):>8}"
        )

        results.append({
            "workers": p,
            "matrix_dimension": n_p,
            "work": work,
            "time_seconds": elapsed,
            "scaled_speedup": scaled_speedup,
            "correct": correct
        })

    os.makedirs("results", exist_ok=True)

    with open(
        "results/weak_scaling.csv", "w", newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "workers",
                "matrix_dimension",
                "work",
                "time_seconds",
                "scaled_speedup",
                "correct"
            ]
        )
        writer.writeheader()
        writer.writerows(results)

    print("\nResults saved to results/weak_scaling.csv")
    return results


def main():
    mp.freeze_support()

    n = N_SALTED
    rng = np.random.default_rng(SEED)

    matrix = rng.random((n, n), dtype=np.float64)

    # Compute the serial reference result.
    reference = matrix.copy()

    reference[1:-1, 1:-1] = (
        matrix[:-2, 1:-1]
        + matrix[2:, 1:-1]
        + matrix[1:-1, :-2]
        + matrix[1:-1, 2:]
    ) * 0.25

    worker_counts = make_worker_counts(PHYSICAL_CORES)
    timings = {}

    print(f"Matrix: {n} x {n}")
    print(f"Physical cores available: {PHYSICAL_CORES}")
    print(f"Worker counts: {worker_counts}")
    print("-" * 75)
    print(
        f"{'P':>4} | {'Time (s)':>12} | {'Speedup':>10} | "
        f"{'Efficiency':>12} | {'Correct':>8}"
    )
    print("-" * 75)

    for p in worker_counts:
        # Repeat each measurement and use the median.
        runs = []
        correct = True

        for _ in range(3):
            elapsed, run_correct = run_benchmark(
                matrix, p, reference
            )
            runs.append(elapsed)
            correct = correct and run_correct

        timings[p] = float(np.median(runs))

        print(
            f"{p:4d} | {timings[p]:12.4f} | "
            f"{timings[1] / timings[p]:10.3f} | "
            f"{timings[1] / timings[p] / p * 100:11.2f}% | "
            f"{str(correct):>8}"
        )

    # Estimate the effective serial fraction from each parallel run.
    serial_fractions = []

    print("\nAMDAHL'S LAW ANALYSIS")
    print("-" * 55)

    for p in worker_counts:
        if p == 1:
            continue

        speedup = timings[1] / timings[p]
        s = (1 / speedup - 1 / p) / (1 - 1 / p)
        serial_fractions.append(s)

        print(
            f"P={p:3d} | Speedup={speedup:.4f} | "
            f"Estimated s={s:.6f}"
        )

    # Average the estimates from the measured worker counts.
    s_estimate = float(np.mean(serial_fractions))

    print(f"\nEstimated serial fraction s = {s_estimate:.6f}")

    if s_estimate > 0:
        print(f"Theoretical maximum speedup = {1 / s_estimate:.3f}x")
    else:
        print(
            "No positive finite speedup ceiling can be estimated "
            "from this average. Check the timings and overhead."
        )

    # Save empirical measurements.
    os.makedirs("results", exist_ok=True)

    with open(
        "results/scaling_study.csv", "w", newline=""
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "workers", "time_seconds", "speedup",
            "efficiency_percent", "serial_fraction"
        ])

        for p in worker_counts:
            speedup = timings[1] / timings[p]
            efficiency = speedup / p * 100

            s = (
                (1 / speedup - 1 / p) / (1 - 1 / p)
                if p > 1 else 0
            )

            writer.writerow([
                p,
                f"{timings[p]:.6f}",
                f"{speedup:.6f}",
                f"{efficiency:.4f}",
                f"{s:.6f}"
            ])

    print("\nResults saved to results/scaling_study.csv")
        # Task 3.2: Weak scaling
    run_weak_scaling(N_SALTED, worker_counts)


if __name__ == "__main__":
    main()
