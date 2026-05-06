from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
plugin_root_text = str(PLUGIN_ROOT)
if plugin_root_text not in sys.path:
    sys.path.insert(0, plugin_root_text)

from astrbot_plugin_volcengine_asr.main import *
