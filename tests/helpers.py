import os
import tempfile
from pathlib import Path

from lifecycle_agent.pipeline import load_policy
from lifecycle_agent.util import parse_dt

ROOT = Path(__file__).resolve().parent.parent
AS_OF = parse_dt("2026-11-08T12:00:00Z")
os.environ.pop("ANTHROPIC_API_KEY", None)


def policy():
    return load_policy(ROOT / "config/policy.json")


def tmpdir():
    return Path(tempfile.mkdtemp(prefix="lma-test-"))


def sample_dataset():
    from lifecycle_agent.ingest import load_dataset
    return load_dataset(ROOT, AS_OF)[0]
