import os
import time

from anthropic import APIConnectionError, Anthropic, AuthenticationError
from dotenv import load_dotenv

# 强制加载 .env 文件
load_dotenv()


def _try_model(client: Anthropic, model_name: str) -> bool:
    """Try one model name and print a clear diagnostic."""
    print(f"\n[TEST] Trying model: {model_name}")
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK only."}],
        )
        text = response.content[0].text if response.content else "<empty>"
        print(f"[OK] Model works: {model_name}")
        print(f"[REPLY] {text}")
        return True
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        if "not_found_error" in err or "model:" in err:
            print(f"[FAIL] Model not available or mismatched: {model_name}")
        else:
            print(f"[FAIL] Request failed: {err}")
        return False


def test_claude_connection() -> None:
    api_key = os.getenv("CLAUDE_API_KEY")
    env_model = os.getenv("CLAUDE_MODEL", "").strip()
    print(f"[CHECK] Key status: {'loaded' if api_key else 'missing (.env not loaded?)'}")
    if api_key:
        print(f"[CHECK] Key prefix: {api_key[:12]}...")
    else:
        print("[STOP] CLAUDE_API_KEY not found, cannot continue.")
        return

    client = Anthropic(api_key=api_key)
    start_time = time.time()
    print("\n[START] Running Claude connectivity diagnostics...")

    listed_models = []
    try:
        print("[STEP] Listing models available for this key...")
        models = client.models.list()
        listed_models = [m.id for m in models.data]
        if listed_models:
            print("[OK] Model list fetched:")
            for m in listed_models:
                print(f" - {m}")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Could not list models (some providers disable this API): {exc}")

    candidates = []
    if env_model:
        candidates.append(env_model)
    candidates.extend(
        [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ]
    )
    for m in listed_models:
        if m not in candidates:
            candidates.append(m)

    print("\n[STEP] Probing model availability one by one...")
    success = False
    for model_name in candidates:
        if _try_model(client, model_name):
            success = True
            break

    elapsed = time.time() - start_time
    print(f"\n[DONE] Elapsed: {elapsed:.2f}s")
    if not success:
        print("[RESULT] Key is loaded but no candidate model worked on this endpoint.")
        print("[ACTION] Check provider dashboard for exact model IDs and update CLAUDE_MODEL.")


if __name__ == "__main__":
    try:
        test_claude_connection()
    except AuthenticationError as exc:
        print(f"[AUTH ERROR] Invalid key or insufficient permission: {exc}")
    except APIConnectionError as exc:
        print(f"[NETWORK ERROR] Connection failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"[UNKNOWN ERROR] {exc}")