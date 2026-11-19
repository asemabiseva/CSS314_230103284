
import os
import sys
import json
import time
import hashlib
import platform
import threading
import subprocess
import re
import numpy as np
from numba import njit

try:
    import resource
except ImportError:
    resource = None


# Change this only if your GitHub username is different
GIT_USERNAME = "asemabiseva"

NUM_THREADS = 4
ITERATIONS_PER_THREAD = 60_000_000
STRIDES = [1, 4, 8, 16]


# ---------------------------------------------------------
# Detect cache line size
# ---------------------------------------------------------

def detect_cache_line_size():
    linux_path = (
        "/sys/devices/system/cpu/cpu0/cache/index0/"
        "coherency_line_size"
    )

    if os.path.exists(linux_path):
        try:
            with open(linux_path, "r") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            pass

    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.cachelinesize"],
                encoding="utf-8"
            )
            return int(out.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    return 64


# ---------------------------------------------------------
# Task 1: Hardware topology and identity
# ---------------------------------------------------------

def get_cpu_model():
    model = platform.processor()

    if not model and os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        model = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass

    return model or platform.machine()


def init_system_context(git_user):
    assert git_user != "REPLACE_WITH_YOUR_GIT_USERNAME"
    assert len(git_user.strip()) > 0

    logical_cores = os.cpu_count() or 1

    if logical_cores < NUM_THREADS:
        raise RuntimeError("At least 4 logical CPU cores are required.")

    line_size = detect_cache_line_size()
    cpu_model = get_cpu_model()

    cpu_sig = f"{platform.machine()}::{cpu_model}::{logical_cores}"
    seed_text = f"{git_user}::{cpu_sig}"

    instance_seed = int(
        hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16
    )

    affinity_supported = hasattr(os, "sched_setaffinity")
    available_cpus = list(range(logical_cores))

    if hasattr(os, "sched_getaffinity"):
        try:
            available_cpus = sorted(os.sched_getaffinity(0))
        except OSError:
            pass

    if len(available_cpus) < NUM_THREADS:
        raise RuntimeError("Not enough available CPUs for four threads.")

    return {
        "github_username": git_user,
        "cpu_model": cpu_model,
        "platform": platform.platform(),
        "logical_cores": logical_cores,
        "cache_line_size": line_size,
        "instance_seed": instance_seed,
        "affinity_supported": affinity_supported,
        "cpu_affinity": available_cpus[:NUM_THREADS]
    }


# ---------------------------------------------------------
# Create a 64-byte-aligned NumPy array
# ---------------------------------------------------------

def aligned_array(length):
    extra = np.empty(length + 64, dtype=np.uint64)
    address = extra.ctypes.data
    offset = ((64 - address % 64) % 64) // 8

    result = extra[offset:offset + length]
    assert result.ctypes.data % 64 == 0

    return result


# ---------------------------------------------------------
# Task 2: GIL-free shared counter kernel
# ---------------------------------------------------------

@njit(nogil=True)
def worker_strided_accumulate(buffer, slot, iters, thread_seed):
    increment = np.uint64(thread_seed % 97 + 1)

    for i in range(iters):
        current = buffer[slot]
        buffer[slot] = current + increment


# ---------------------------------------------------------
# Task 4: Register-privatized kernel
# ---------------------------------------------------------

@njit(nogil=True)
def worker_private_accumulate(buffer, slot, iters, thread_seed):
    increment = np.uint64(thread_seed % 97 + 1)
    local_value = np.uint64(0)

    for i in range(iters):
        local_value += increment

    # One write to shared memory after the loop
    buffer[slot] = local_value


# ---------------------------------------------------------
# Context switch measurements
# ---------------------------------------------------------

def get_context_switches():
    if resource is None:
        return {"voluntary": None, "involuntary": None}

    usage = resource.getrusage(resource.RUSAGE_SELF)

    return {
        "voluntary": usage.ru_nvcsw,
        "involuntary": usage.ru_nivcsw
    }


# ---------------------------------------------------------
# Task 3: Run one benchmark
# ---------------------------------------------------------

def run_one_benchmark(stride, context, private=False):
    length = (NUM_THREADS - 1) * stride + 1
    buffer = aligned_array(length)
    buffer[:] = 0

    barrier = threading.Barrier(NUM_THREADS)
    errors = []

    def thread_function(thread_id):
        try:
            if context["affinity_supported"]:
                cpu = context["cpu_affinity"][thread_id]
                try:
                    os.sched_setaffinity(0, {cpu})
                except (OSError, AttributeError):
                    pass

            seed = (context["instance_seed"] + thread_id + 1) % (2**63 - 1)
            slot = thread_id * stride

            barrier.wait()

            if private:
                worker_private_accumulate(
                    buffer, slot, ITERATIONS_PER_THREAD, seed
                )
            else:
                worker_strided_accumulate(
                    buffer, slot, ITERATIONS_PER_THREAD, seed
                )

        except Exception as error:
            errors.append(str(error))

    threads = [
        threading.Thread(target=thread_function, args=(i,))
        for i in range(NUM_THREADS)
    ]

    switches_before = get_context_switches()
    start = time.perf_counter_ns()

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    elapsed_ns = time.perf_counter_ns() - start
    switches_after = get_context_switches()

    if errors:
        raise RuntimeError(str(errors))

    expected = []

    for thread_id in range(NUM_THREADS):
        seed = (context["instance_seed"] + thread_id + 1) % (2**63 - 1)
        increment = seed % 97 + 1
        expected.append(ITERATIONS_PER_THREAD * increment)

    actual = [
        int(buffer[i * stride]) for i in range(NUM_THREADS)
    ]

    if actual != expected:
        raise AssertionError("Counter values do not match expected values.")

    total_updates = NUM_THREADS * ITERATIONS_PER_THREAD

    return {
        "stride": stride,
        "elapsed_ns": elapsed_ns,
        "ns_per_update": elapsed_ns / total_updates,
        "context_switches": {
            "voluntary": (
                switches_after["voluntary"] - switches_before["voluntary"]
                if switches_before["voluntary"] is not None else None
            ),
            "involuntary": (
                switches_after["involuntary"] - switches_before["involuntary"]
                if switches_before["involuntary"] is not None else None
            )
        },
        "values": actual,
        "verification_passed": True
    }


# ---------------------------------------------------------
# Task 5: LLVM inspection and parity
# ---------------------------------------------------------

def audit_llvm_and_parity(results):
    signature = worker_strided_accumulate.signatures[0]
    llvm_ir = worker_strided_accumulate.inspect_llvm(signature)

    store_i64_count = len(re.findall(r"\bstore i64\b", llvm_ir))
    load_i64_count = len(re.findall(r"\bload i64\b", llvm_ir))

    # All layouts and the private version must produce the same values
    reference = results["stride_8"]["values"]

    for name, result in results.items():
        if result["values"] != reference:
            raise AssertionError(f"Parity failed for {name}")

    if store_i64_count == 0 or load_i64_count == 0:
        raise AssertionError("Expected native i64 loads and stores not found.")

    return {
        "llvm_load_i64_count": load_i64_count,
        "llvm_store_i64_count": store_i64_count,
        "llvm_native_memory_operations_found": True,
        "parity_passed": True
    }


# ---------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------

def main():
    print("Detecting system information...")
    context = init_system_context(GIT_USERNAME)

    print(json.dumps(context, indent=2))

    # Compile kernels before measuring execution time
    warmup = aligned_array(32)
    warmup[:] = 0

    worker_strided_accumulate(warmup, 0, 10, 123)
    worker_private_accumulate(warmup, 1, 10, 123)

    results = {}

    print("\nRunning stride benchmarks...")

    for stride in STRIDES:
        print(f"Testing stride {stride}...")
        results[f"stride_{stride}"] = run_one_benchmark(
            stride, context
        )

    print("\nRunning register-privatized benchmark...")
    results["private"] = run_one_benchmark(
        1, context, private=True
    )

    audit = audit_llvm_and_parity(results)

    stride_1 = results["stride_1"]["elapsed_ns"]
    stride_8 = results["stride_8"]["elapsed_ns"]

    manifest = {
        "system": context,
        "threads": NUM_THREADS,
        "iterations_per_thread": ITERATIONS_PER_THREAD,
        "results": results,
        "slowdown_stride_1_vs_stride_8": stride_1 / stride_8,
        "audit": audit,
        "verification_passed": True
    }

    with open("cache_lab_manifest.json", "w") as f:
        json.dump(manifest, f, indent=4)

    print("\nBenchmark results:")

    for name, result in results.items():
        print(
            f"{name}: {result['elapsed_ns']} ns, "
            f"{result['ns_per_update']:.3f} ns/update"
        )

    print(
        "\nStride 1 / Stride 8 slowdown:",
        f"{stride_1 / stride_8:.3f}x"
    )

    print("\nLLVM audit:")
    print(json.dumps(audit, indent=2))

    print("\nVerification passed.")
    print("Created cache_lab_manifest.json")


if __name__ == "__main__":
    main()
