# RESULTS — Parallel Synchronization Experiments

## Hardware and execution profile

| Property | Configuration |
|---|---|
| Operating system / shell | Windows, PowerShell |
| Physical CPU cores | 6 |
| Logical processors | 12 |
| Parallelism tested | 1, 2, and 4 worker processes |
| Runtime measurement | `time.perf_counter()` |
| Implementation | Python `multiprocessing` |

*Hardware profile reflects the system configuration previously reported for this coursework. Record the exact CPU model and Python version separately if your instructor requires them.*

## Empirical runtimes

All values below are the actual measurements from the terminal output.

| Experiment mode | T1 (s) | T2 (s) | T4 (s) | e(2) | e(4) | Architectural diagnosis |
|---|---:|---:|---:|---:|---:|---|
| A: Serial Tail | 11.2119 | 7.7934 | 5.1304 | 0.3902 | 0.2768 | Sequential delay plus other measured overhead; e is not constant and is higher than the expected ~0.10–0.14 |
| B: Lock Contention | 5.4980 | 25.8440 | 33.0220 | 8.4010 | 7.6750 | Severe negative scaling; shared-lock contention dominates |
| C: Privatized State | 1.2970 | 1.2438 | 0.5411 | 0.9179 | 0.2229 | Privatization removes per-increment locking, but measured scaling is not near-linear and e remains above the <0.05 target |

## Speedup calculations

Speedup is calculated as:

\[
S(p) = \frac{T(1)}{T(p)}
\]

| Experiment | S(2) | S(4) |
|---|---:|---:|
| A: Serial Tail | 1.4386x | 2.1850x |
| B: Lock Contention | 0.2127x | 0.1665x |
| C: Privatized State | 1.0427x | 2.3962x |

Karp–Flatt is calculated using:

\[
e(p) = \frac{p/S(p)-1}{p-1}
\]

## Interpretation

### A: Serial Tail

The runtime improves as worker count increases, but the measured Karp–Flatt values (0.3902 and 0.2768) are substantially above the assignment's expected range of approximately 0.10–0.14. The fixed 0.40-second pause is not the only source of measured overhead; process-pool startup, scheduling, and workload characteristics also contribute. The results do not support describing the measured serial fraction as constant.

### B: Lock Contention

Adding workers makes the program substantially slower: T2 is 25.8440 s versus T1 at 5.4980 s, and T4 is 33.0220 s. Both speedups are below 1. The very high Karp–Flatt estimates (8.4010 and 7.6750) indicate severe overhead and negative scaling. These measurements are consistent with contention around the shared lock and counter.

### C: Privatized State

Each worker increments a private local variable and returns one partial result, avoiding a shared lock on every increment. T4 improves to 0.5411 s, but T2 (1.2438 s) is only slightly faster than T1 (1.2970 s). The Karp–Flatt values (0.9179 and 0.2229) do not meet the expected <0.05 target. The measurements show a benefit at four processes, but do not demonstrate near-linear scalability.

## Verification

All three experiments completed their stated counter/checksum verification:
- Experiment B: shared counter verification passed.
- Experiment C: privatized counter verification passed.

## Overall conclusion

The experiments illustrate three different performance behaviors: a sequential delay limits scaling in A; a shared lock causes severe negative scaling in B; and local accumulation reduces synchronization frequency in C. However, the measured Karp–Flatt values show that neither A nor C reached the assignment's target ranges on this run. Report the empirical values as measured rather than substituting the expected values.


