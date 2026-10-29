
import hashlib
import json
import re
from pathlib import Path


def get_student_params(student_id: str):
    if not re.fullmatch(r"\d{8}", student_id):
        raise ValueError("Student ID must contain exactly 8 digits.")

    h = int(
        hashlib.sha256(student_id.encode("utf-8")).hexdigest()[:8],
        16
    )

    N = 1024 + ((h % 9) * 64)
    buffer_elements = 16_777_216
    seed = h % 100_007

    return {
        "student_id": student_id,
        "N": N,
        "buffer_elements": buffer_elements,
        "seed": seed
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--student-id", required=True)
    args = parser.parse_args()

    params = get_student_params(args.student_id)

    output_path = (
        Path(__file__).resolve().parent.parent
        / "results"
        / "salted_params.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(params, indent=4),
        encoding="utf-8"
    )

    print(json.dumps(params, indent=4))
    print(f"\nParameters saved to: {output_path}")
