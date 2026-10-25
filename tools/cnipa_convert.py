#!/usr/bin/env python
"""免安装入口：``python tools/cnipa_convert.py <docx> [--validate]``。

真正的实现在 ``oh_my_patent/cnipa_convert.py``；这里只把仓库根塞进 sys.path 后转发。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oh_my_patent.cnipa_convert import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
