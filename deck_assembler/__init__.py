"""Mixed-deck assembler.

Combines per-slide artifacts from two pipelines into one editable PPTX:

    image slides  → editable_pptx  → image-deck.pptx
    chart  slides → svg_to_pptx    → chart-deck.pptx
                                      |
                          merge in slide order
                                      v
                                 final.pptx

Slide order is determined by the leading NN- prefix on each artifact filename.
"""

from .merge import assemble_mixed_deck

__all__ = ["assemble_mixed_deck"]
