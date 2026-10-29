
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
import argparse
from salt import get_student_params

try:
    import psutil
except ImportError:
    psutil = None


def run_command(command):
    """Run a system command and return its output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def get_linux_cpu_info():
    info = {}

    try:
        text = Path("/proc/cpuinfo").read_text(errors="ignore")
        blocks = re.split(r"\n\s*\n", text)

        for block in blocks:
            fields = {}
            for line in block.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()

            if fields:
                info = fields
                break
    except OSError:
        pass

    return info


def get_linux_caches():
    caches = {
        "l1_data_bytes": None,
        "l2_bytes": None,
        "l3_shared_bytes": None,
        "cache_line_bytes": None,
    }

    root = Path("/sys/devices/system/cpu/cpu0/cache")

    if not root.exists():
        return caches

    for index in root.glob("index*"):
        try:
            cache_type = (index / "type").read_text().strip()
            level = int((index / "level").read_text().strip())
            size_text = (index / "size").read_text().strip()
            size_match = re.fullmatch(r"(\d+)\s*([KMG]?)", size_text, re.I)

            if not size_match:
                continue

            size = int(size_match.group(1))
            unit = size_match.group(2).upper()
            size *= {"": 1, "K": 1024, "M": 1024**2,
                     "G": 1024**3}[unit]

            if cache_type == "Data" and level == 1:
                caches["l1_data_bytes"] = size
            elif cache_type in ("Unified", "Data") and level == 2:
                caches["l2_bytes"] = size
            elif cache_type in ("Unified", "Data") and level == 3:
                caches["l3_shared_bytes"] = size

            line_file = index / "coherency_line_size"
            if line_file.exists():
                line_size = int(line_file.read_text().strip())
                if line_size > 0:
                    caches["cache_line_bytes"] = line_size

        except (OSError, ValueError):
            continue

    return caches


def get_macos_info():
    keys = [
        "machdep.cpu.brand_string",
        "hw.model",
        "hw.ncpu",
        "hw.physicalcpu",
        "hw.cpufrequency",
        "hw.basefrequency",
        "hw.l1dcachesize",
        "hw.l2cachesize",
        "hw.l3cachesize",
        "hw.cachelinesize",
    ]

    result = {}

    for key in keys:
        value = run_command(["sysctl", "-n", key])
        if value:
            result[key] = value

    return result


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_mhz(value):
    """Convert a frequency in Hz to MHz."""
    try:
        number = float(value)
        return round(number / 1_000_000, 2) if number > 0 else None
    except (TypeError, ValueError):
        return None


def collect_profile():
    system = platform.system()
    linux_info = get_linux_cpu_info() if system == "Linux" else {}
    mac_info = get_macos_info() if system == "Darwin" else {}

    cpu_model = (
        linux_info.get("model name")
        or linux_info.get("Hardware")
        or mac_info.get("machdep.cpu.brand_string")
        or platform.processor()
        or None
    )

    logical_cores = (
        psutil.cpu_count(logical=True) if psutil
        else os.cpu_count()
    )
    physical_cores = (
        psutil.cpu_count(logical=False) if psutil
        else None
    )

    if system == "Darwin":
        physical_cores = (
            to_int(mac_info.get("hw.physicalcpu"))
            or physical_cores
        )
        logical_cores = (
            to_int(mac_info.get("hw.ncpu"))
            or logical_cores
        )

    base_frequency_mhz = None

    if system == "Linux":
        # /proc/cpuinfo's cpu MHz is usually current, not base frequency.
        # Use sysfs cpufreq base frequency when available.
        for path in (
            "/sys/devices/system/cpu/cpu0/cpufreq/base_frequency",
            "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq",
        ):
            try:
                base_frequency_mhz = round(
                    int(Path(path).read_text().strip()) / 1000, 2
                )
                break
            except (OSError, ValueError):
                continue

    elif system == "Darwin":
        base_frequency_mhz = to_mhz(
            mac_info.get("hw.basefrequency")
        )

    if base_frequency_mhz is None and psutil:
        try:
            freq = psutil.cpu_freq()
            if freq:
                # psutil reports current/max, not necessarily base frequency.
                base_frequency_mhz = None
        except Exception:
            pass

    caches = {
        "l1_data_bytes": None,
        "l2_bytes": None,
        "l3_shared_bytes": None,
        "cache_line_bytes": None,
    }

    if system == "Linux":
        caches = get_linux_caches()

    elif system == "Darwin":
        caches = {
            "l1_data_bytes": to_int(
                mac_info.get("hw.l1dcachesize")
            ),
            "l2_bytes": to_int(mac_info.get("hw.l2cachesize")),
            "l3_shared_bytes": to_int(
                mac_info.get("hw.l3cachesize")
            ),
            "cache_line_bytes": to_int(
                mac_info.get("hw.cachelinesize")
            ),
        }

    # Windows and other systems: cache details may not be exposed.
    # Do not guess values.
    microarchitecture = None
    if linux_info.get("cpu family") and linux_info.get("model"):
        microarchitecture = (
            "Not directly reported; "
            f"CPU family {linux_info['cpu family']}, "
            f"model {linux_info['model']}"
        )

    return {
        "host": {
            "os": platform.system(),
            "os_release": platform.release(),
            "kernel_version": platform.version(),
            "machine_architecture": platform.machine(),
        },
        "cpu": {
            "model_name": cpu_model,
            "microarchitecture": microarchitecture,
            "base_frequency_mhz": base_frequency_mhz,
            "physical_cores": physical_cores,
            "logical_threads": logical_cores,
            "smt_or_hyperthreading_detected": (
                logical_cores > physical_cores
                if logical_cores and physical_cores
                else None
            ),
        },
        "cache": caches,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "executable": sys.executable,
            "bits": platform.architecture()[0],
        },
    }



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect host telemetry and student-specific parameters"
    )
    parser.add_argument(
        "--student-id",
        required=True,
        help="Your 8-digit Student ID"
    )
    args = parser.parse_args()

    profile = collect_profile()
    profile["student_params"] = get_student_params(args.student_id)

    output_path = (
        Path(__file__).resolve().parent.parent
        / "results"
        / "host_profile.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(profile, indent=4),
        encoding="utf-8"
    )

    print(json.dumps(profile, indent=4))
    print(f"\nProfile saved to: {output_path}")

