# -*- coding: utf-8 -*-
"""每晚归档总入口：先跑每日知识点整理，再归档其余暂存 txt。"""

from __future__ import annotations

import sys

from run_archive import main as archive_main
from run_digest import log_line, main as digest_main


def main() -> int:
    log_line("=== run_nightly 开始 ===")

    digest_code = digest_main()
    if digest_code != 0:
        log_line(f"每日知识点整理 exit={digest_code}，继续归档其余暂存")

    archive_code = archive_main()

    if digest_code != 0 and archive_code != 0:
        code = 3
    elif digest_code != 0:
        code = digest_code
    elif archive_code != 0:
        code = archive_code
    else:
        code = 0

    log_line(f"=== run_nightly 结束 exit={code} ===")
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
