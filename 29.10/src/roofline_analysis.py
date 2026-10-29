
import json
import os

# Values from your Milestone 0 report
N_SALTED = 1152
SEED = 16454
PHYSICAL_CORES = 6
LOGICAL_THREADS = 12

# Cache data was unavailable in the host report.
L1_KB = None
L2_KB = None
L3_MB = None
CACHE_LINE_BYTES = None

# Fill these from a reliable CPU specification or benchmark.
MEMORY_BANDWIDTH_GB_S = 21.3
PEAK_COMPUTE_GFLOPS = 384.0

# Five-point stencil per interior cell:
# 4 additions + 1 multiplication.
FLOPS_PER_CELL = 5

# Ideal reuse: one 8-byte read and one 8-byte write.
BYTES_PER_CELL_IDEAL_REUSE = 16

# No reuse model: four 8-byte reads and one 8-byte write.
BYTES_PER_CELL_NO_REUSE = 40


def main():
    os.makedirs("results", exist_ok=True)

    ai_ideal = FLOPS_PER_CELL / BYTES_PER_CELL_IDEAL_REUSE
    ai_no_reuse = FLOPS_PER_CELL / BYTES_PER_CELL_NO_REUSE

    hardware_values = [
        L1_KB, L2_KB, L3_MB,
        MEMORY_BANDWIDTH_GB_S, PEAK_COMPUTE_GFLOPS
    ]
    hardware_complete = all(v is not None for v in hardware_values)

    ridge_point = None
    ideal_classification = "Undetermined: missing hardware values"
    no_reuse_classification = "Undetermined: missing hardware values"

    if hardware_complete:
        ridge_point = (
            PEAK_COMPUTE_GFLOPS / MEMORY_BANDWIDTH_GB_S
        )

        ideal_classification = (
            "Memory-bandwidth bound"
            if ai_ideal < ridge_point
            else "Potentially compute bound"
        )

        no_reuse_classification = (
            "Memory-bandwidth bound"
            if ai_no_reuse < ridge_point
            else "Potentially compute bound"
        )

    summary = {
        "kernel": "Five-point 2D stencil",
        "matrix_dimension": N_SALTED,
        "seed": SEED,
        "cpu": {
            "physical_cores": PHYSICAL_CORES,
            "logical_threads": LOGICAL_THREADS
        },
        "floating_point_operations_per_interior_cell": FLOPS_PER_CELL,
        "arithmetic_intensity_flop_per_byte": {
            "ideal_cache_reuse": ai_ideal,
            "no_cache_reuse": ai_no_reuse
        },
        "estimated_bytes_per_interior_cell": {
            "ideal_cache_reuse": BYTES_PER_CELL_IDEAL_REUSE,
            "no_cache_reuse": BYTES_PER_CELL_NO_REUSE
        },
        "cache": {
            "L1_data_KB": L1_KB,
            "L2_KB": L2_KB,
            "L3_MB": L3_MB,
            "cache_line_bytes": CACHE_LINE_BYTES
        },
        "peak_memory_bandwidth_GB_s": MEMORY_BANDWIDTH_GB_S,
        "peak_compute_GFLOPS": PEAK_COMPUTE_GFLOPS,
        "roofline": {
            "ridge_point_flop_per_byte": ridge_point,
            "ideal_reuse_classification": ideal_classification,
            "no_reuse_classification": no_reuse_classification
        },
        "notes": [
            "Arithmetic intensity values are theoretical estimates.",
            "Actual DRAM traffic depends on cache reuse and temporary arrays.",
            "Roofline classification requires verified peak bandwidth and compute throughput."
        ]
    }

    path = "results/roofline_summary.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print(json.dumps(summary, indent=4))
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
