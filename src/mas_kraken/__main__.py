"""Environment-driven terminal entry point for M1."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from mas_kraken.errors import ConfigurationError
from mas_kraken.log import configure_logging
from mas_kraken.model_adapters import make_openai_model
from mas_kraken.repl import run_repl

load_dotenv(dotenv_path=Path.cwd() / ".env", override=True)

def main() -> int:
    """Load local settings, validate configuration, and run the chat REPL."""

    required = ("MASFS_BASE_URL", "MASFS_API_KEY", "MASFS_MODEL")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        timeout_s = float(os.environ.get("MASFS_REQUEST_TIMEOUT", "30"))
    except ValueError:
        print("MASFS_REQUEST_TIMEOUT must be a positive number.", file=sys.stderr)
        return 2

    try:
        configure_logging(os.environ.get("MASFS_LOG_LEVEL", "INFO"))
        model = make_openai_model(
            base_url=os.environ["MASFS_BASE_URL"],
            api_key=os.environ["MASFS_API_KEY"],
            model=os.environ["MASFS_MODEL"],
            timeout_s=timeout_s,
        )
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except ValueError:
        # Do not expose a third-party exception that might include credentials.
        print("Invalid provider or logging configuration.", file=sys.stderr)
        return 2

    return run_repl(model)


if __name__ == "__main__":
    raise SystemExit(main())
