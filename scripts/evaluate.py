"""Deterministic evidence-contract evaluation; no semantic quality claim or model cost."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from engine import demo  # noqa: E402


def main():
    cases = json.loads(Path("backend/eval-cases.json").read_text())
    for case in cases:
        result = demo(case["prompt"])
        assert result["outcome"] == case["outcome"]
        assert sorted(source["id"] for source in result["sources"]) == sorted(case["sources"])
        assert result["tool_calls"] == case["tool_calls"]
        assert result["model_calls"] == 0
        print(f"PASS {case['name']}: {case['outcome']}")
    print("3 fixed contracts passed; semantic judgement remains manual; 0 model calls.")


if __name__ == "__main__":
    main()
