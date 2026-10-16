import hashlib
from pathlib import Path

import finances.web

STATIC = Path(finances.web.__file__).parent / "static"
LIBRARY = STATIC / "vendor" / "chart.umd.js"
# dist/chart.umd.js from the npm package chart.js 4.4.6 (the same bytes jsDelivr serves).
SHA256 = "3850656abbdc319141e6e8ce8eacde2622fc767c30e20d81704af2bf3159f92d"


def test_the_chart_library_is_the_pinned_file() -> None:
    content = LIBRARY.read_bytes()
    assert hashlib.sha256(content).hexdigest() == SHA256
    assert content.startswith(b"/*!\n * Chart.js v4.4.6\n")


def test_the_vendor_folder_holds_only_the_library() -> None:
    assert sorted(path.name for path in LIBRARY.parent.iterdir()) == ["chart.umd.js"]


def test_our_chart_script_sends_nothing_anywhere() -> None:
    script = (STATIC / "charts.js").read_text(encoding="utf-8")
    for word in (
        "fetch",
        "XMLHttpRequest",
        "http",
        "eval",
        "Function(",
        "innerHTML",
        "localStorage",
    ):
        assert word not in script, word
