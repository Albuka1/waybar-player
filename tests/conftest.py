import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "share"
if str(SHARE) not in sys.path:
    sys.path.insert(0, str(SHARE))
