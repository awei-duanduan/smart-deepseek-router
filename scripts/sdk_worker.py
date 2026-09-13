"""One SDK lifecycle per attempt; stdout contains no model response or credentials."""
import argparse
import importlib.metadata
import json
from pathlib import Path

from routerlib import read_json, write_json


def run_request(request, harness_class=None):
    if harness_class is None:
        from deepseek_harness import DeepSeekHarness
        harness_class = DeepSeekHarness
    c = request["contract"]
    prompt = (
        "You are implementing one bounded task for a Codex reviewer. Read applicable AGENTS.md. "
        "Only modify the contract write scope. Do not change Git HEAD/index, commit, stage, "
        "install dependencies, access credentials or unrelated paths, deploy, or perform external mutations. "
        "Do not change trusted verifier files. If blocked by environment, permissions or dependencies, "
        "stop and explain. The host will independently verify your changes.\n"
        "Contract:\n" + json.dumps(c, ensure_ascii=False) + "\n" + request.get("feedback", "")
    )
    # The process is already launched with a minimal allowlisted environment.
    # A fresh sdk-minimal home is per-attempt; credentials must be in environment.
    with harness_class(
        dsh_home=request["home"], cwd=request["workdir"], runtime_cwd=request["workdir"],
        profile="sdk-minimal", provider="deepseek-official", model=request["model"],
        max_tokens=c.get("max_model_output_tokens", 8192), initialize_timeout_seconds=30,
        request_timeout_seconds=c.get("task_timeout_seconds", 600), shutdown_timeout_seconds=3,
    ) as harness:
        result = harness.run(prompt, session_id=c["id"])
    # SDK-owned session logs stay in its run home. Do not copy raw events/responses.
    return dict(finish_reason=result.finish_reason)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--result", required=True)
    args = p.parse_args()
    try:
        result = run_request(read_json(args.request))
    except ImportError:
        result = dict(finish_reason="infrastructure", diagnostic="Missing or incompatible deepseek-harness-sdk; run doctor.py")
    except Exception as exc:
        # Exceptions can contain runtime diagnostics and secrets. Preserve only type.
        result = dict(finish_reason="infrastructure", diagnostic=type(exc).__name__ + ": inspect the local Harness runtime securely; no escalation")
    write_json(args.result, result)


if __name__ == "__main__":
    main()
