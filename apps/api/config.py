from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent.parent
load_dotenv(REPO_ROOT / ".env")

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
