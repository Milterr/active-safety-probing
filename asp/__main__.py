import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from asp.benchmark import DATA, load_scenarios
from asp.evaluate import evaluate, summarize, verify_fixtures
from asp.monitor import ARMS, APIError, Monitor, SYSTEM_MESSAGE


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(scenarios, fixtures, gold, monitor, output):
    output.mkdir(parents=True, exist_ok=False)
    rows = {arm: [] for arm in ARMS}
    error = None
    reported_model = None
    with (output / "decisions.jsonl").open("x", encoding="utf-8") as log:
        try:
            for index, scenario in enumerate(scenarios):
                for arm in (ARMS if index % 2 == 0 else ARMS[::-1]):
                    decision = monitor.decide(scenario, arm)
                    if reported_model is not None and decision.reported_model != reported_model:
                        raise APIError("The API reported a different model during the run")
                    reported_model = decision.reported_model
                    reference = gold[scenario.id]
                    row = {
                        "scenario_id": scenario.id,
                        "arm": arm,
                        "decision": decision.value,
                        "format_valid": decision.format_valid,
                        **reference,
                        **evaluate(scenario, fixtures[scenario.id], decision.value),
                    }
                    log.write(json.dumps(row, ensure_ascii=False) + "\n")
                    log.flush()
                    rows[arm].append(row)
        except APIError as problem:
            error = str(problem)

    summary = {
        "status": "incomplete" if error else "complete",
        "requested_model": monitor.model,
        "reported_model": reported_model,
        "api_host": monitor.provider,
        "generation_options": monitor.generation_options,
        "scenarios_per_arm": len(scenarios),
        "system_prompt_sha256": hashlib.sha256(SYSTEM_MESSAGE.encode("utf-8")).hexdigest(),
        "dataset_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(DATA.glob("*.json"))
        },
        "arms": {arm: summarize(records) for arm, records in rows.items()},
    }
    if error:
        summary["error"] = error
    write_json(output / "summary.json", summary)
    if error:
        raise APIError(error)


def main():
    parser = argparse.ArgumentParser(description="Run the Active Safety Probing A/B baseline")
    parser.add_argument("--model", default=os.environ.get("ASP_MODEL"))
    parser.add_argument("--output", type=Path, help="New output directory, or a JSON file with --validate-only")
    parser.add_argument("--validate-only", action="store_true", help="Check fixture outcomes without an API call")
    args = parser.parse_args()

    try:
        monitor = None if args.validate_only else Monitor(args.model)
        scenarios = load_scenarios()
        fixtures, gold, validation = verify_fixtures(scenarios)
        if args.validate_only:
            if args.output:
                write_json(args.output, validation)
            print(json.dumps(validation, ensure_ascii=False))
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output = args.output or Path("runs") / stamp
            run(scenarios, fixtures, gold, monitor, output)
            print(output / "summary.json")
    except (APIError, OSError, ValueError, RuntimeError) as problem:
        print(f"Error: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
