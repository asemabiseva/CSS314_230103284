# Results B — Parallel Overhead Experiments

## Empirical measurements

| Configuration | A: Micro (k=1) | B: Queue Choke | C: Buffered Batch |
|---|---:|---:|---:|
| T1 (s) | N/A* | 5.4154 | 1.5364 |
| T2 (s) | N/A* | 8.7829 | 2.0636 |
| T4 (s) | N/A* | 9.6174 | 1.2756 |
| T8 (s) | N/A* | 9.3423 | 1.8259 |
| S8 | N/A* | 0.58x | 0.84x |
| e(2) | N/A* | 2.2440 | 1.6863 |
| e(8) | N/A* | 1.8290 | 1.2153 |
| Verdict | Master dispatch / scheduling overhead | Shared-queue contention; negative scaling | Batching reduces queue messages, but scaling remains inefficient |

\* Experiment A was measured with a fixed worker count of 6 while varying `chunksize`; it was not run with P = 1, 2, 4, and 8. Therefore, A's T1/T2/T4/T8, S8, and Karp–Flatt values cannot be calculated from the available measurements.

## Experiment A — Granularity Trap

Configuration: 6 workers, 1,000,000 items.

| Chunk size (k) | Time (s) | Checksum |
|---:|---:|---:|
| 1 | 122.2866 | 131434424 |
| 10 | 12.1429 | 131434424 |
| 100 | 6.0367 | 131434424 |
| 1,000 | 4.8882 | 131434424 |
| 10,000 | 4.8434 | 131434424 |

Increasing the chunk size from 1 to 10,000 reduced runtime from 122.2866 s to 4.8434 s (about 25.25x faster). All checksums match, confirming that the computed result remained the same.

## Experiment B — Queue Choke-Point

Configuration: 400,000 items, individual queue messages.

| Processes (P) | Time (s) | Speedup | Karp–Flatt e(p) |
|---:|---:|---:|---:|
| 1 | 5.4154 | 1.00x | — |
| 2 | 8.7829 | 0.62x | 2.2440 |
| 4 | 9.6174 | 0.56x | 2.0350 |
| 8 | 9.3423 | 0.58x | 1.8290 |

Adding processes made execution slower than the one-process baseline. The measured speedup stayed below 1 for P = 2, 4, and 8, consistent with substantial communication and synchronization overhead in the shared queue.

## Experiment C — Local Buffer Chunking

Configuration: 10,000,000 items, batch size 10,000.

| Processes (P) | Time (s) | Speedup | Karp–Flatt e(p) |
|---:|---:|---:|---:|
| 1 | 1.5364 | 1.00x | — |
| 2 | 2.0636 | 0.74x | 1.6863 |
| 4 | 1.2756 | 1.20x | 0.7736 |
| 8 | 1.8259 | 0.84x | 1.2153 |

All process counts produced the same checksum: **29,999,994**. P = 4 was the fastest configuration, with a speedup of approximately 1.20x. P = 2 and P = 8 were slower than the one-process baseline.

## Analysis and conclusion

- **Experiment A:** Very small chunks caused substantial dispatch and scheduling overhead. Larger chunks amortized that overhead and improved runtime substantially.
- **Experiment B:** Sending every result through one shared queue produced negative scaling. The queue became a communication/synchronization bottleneck.
- **Experiment C:** Local aggregation reduced the number of queue messages and improved the measured runtime compared with B's baseline, but the experiment did **not** achieve the target near-linear speedup or Karp–Flatt e(p) below 0.05. The best measured process count was P = 4; performance degraded at P = 8.

**Comparison limitation:** Experiments B and C used different total item counts (400,000 versus 10,000,000), so their absolute runtimes are not a controlled apples-to-apples comparison. A fair direct comparison requires rerunning both with the same item count, equivalent per-item work, and the same process counts.

Karp–Flatt values above 1 are empirical indicators of severe overhead/negative scaling in these measurements; they should not be interpreted as an ordinary serial fraction between 0 and 1.
