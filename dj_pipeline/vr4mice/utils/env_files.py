import os


def load_env_file(path, override=False):
    """Load KEY=VALUE lines from path into os.environ."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Env file not found: {path}")
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if override or key not in os.environ:
                os.environ[key] = value


def require_dj_env():
    missing = [
        key
        for key in ("DJ_HOST", "DJ_USER", "DJ_PWD")
        if not os.environ.get(key)
    ]
    if missing:
        raise EnvironmentError(
            "Missing database credentials: "
            + ", ".join(missing)
            + " (set in .env for local cron or .env-aws for --aws)."
        )
