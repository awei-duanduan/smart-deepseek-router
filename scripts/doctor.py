"""Read-only diagnostics; --online refreshes model capabilities without exposing key values."""
import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from credentials import runtime_dir
from provider_proxy import discover_models, load_capabilities, save_capabilities


def check(online=False):
    result = dict(python=sys.version.split()[0], platform=platform.system(), git=bool(shutil.which("git")), platform_shell=bool(shutil.which("pwsh" if os.name == "nt" else "bash")), sdk_installed=False,
                  api_key_in_environment=bool(os.environ.get("DEEPSEEK_API_KEY")), live_api_tested=False)
    try:
        result["sdk_version"] = importlib.metadata.version("deepseek-harness-sdk")
        from deepseek_harness import DeepSeekHarnessConfig
        fields = DeepSeekHarnessConfig.__dataclass_fields__
        required = {"dsh_home", "profile", "model", "cwd", "runtime_cwd", "max_tokens", "request_timeout_seconds", "initialize_timeout_seconds", "shutdown_timeout_seconds"}
        result["sdk_installed"] = True
        result["sdk_api_compatible"] = required <= set(fields)
        result["runtime_version"] = importlib.metadata.version("deepseek-harness-runtime-bin")
    except (ImportError, importlib.metadata.PackageNotFoundError, AttributeError):
        result["sdk_api_compatible"] = False
    cached = load_capabilities(runtime_dir(), base_url=os.environ.get("DEEPSEEK_BASE_URL"))
    result["model_capabilities"] = cached
    if online and result["api_key_in_environment"]:
        try:
            models = discover_models(os.environ["DEEPSEEK_API_KEY"], base_url=os.environ.get("DEEPSEEK_BASE_URL"))
            result["model_capabilities"] = save_capabilities(runtime_dir(), models, base_url=os.environ.get("DEEPSEEK_BASE_URL"))
            result["live_api_tested"] = True
        except Exception as exc:
            result["model_discovery_error"] = type(exc).__name__
    selected = (result.get("model_capabilities") or {}).get("selected", {})
    result["ready_for_live_attempt"] = bool(sys.version_info >= (3, 10) and result["git"] and result["platform_shell"] and result["sdk_api_compatible"] and result.get("runtime_version") and result["api_key_in_environment"] and selected.get("flash"))
    result["note"] = "Readiness checks runtime compatibility, key presence, and a recent model capability cache. --online refreshes the cache. It does not prove billing capacity or OS isolation."
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    print(json.dumps(check(parser.parse_args().online), indent=2))
