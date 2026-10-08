from __future__ import annotations

import json

from .transform.medqa_final_review import build_reviewed_cases


def curate_selected_cases() -> dict[str, object]:
    return build_reviewed_cases()


def main() -> int:
    print(json.dumps(curate_selected_cases(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
