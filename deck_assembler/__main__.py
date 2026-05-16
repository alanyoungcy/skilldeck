"""CLI: deck_assembler <slide-deck-dir>

Looks for `NN-slide-*.png` (image slides) and `NN-slide-*.svg` (chart slides)
in <slide-deck-dir>, runs the appropriate exporter for each kind, and merges
into a single editable PPTX.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from deck_assembler.merge import assemble_mixed_deck


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Assemble mixed image + chart deck → editable PPTX.")
    parser.add_argument("deck_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    deck_dir = args.deck_dir.resolve()
    out = args.output.resolve() if args.output else deck_dir / f"{deck_dir.name}.pptx"

    assemble_mixed_deck(deck_dir, out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
