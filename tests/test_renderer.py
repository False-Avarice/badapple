import numpy as np

from main import build_text_frame


def test_build_text_frame_uses_bad_apple_stream_and_masks_spaces():
    mask = np.zeros((3, 12), dtype=np.uint8)
    mask[1, 2:7] = 1

    rendered = build_text_frame(mask, offset=0)

    assert len(rendered) == 3
    assert rendered[0].startswith("bad apple")
    assert rendered[1][0:2] == "ba"
    assert rendered[1][2:7] == "     "
    assert rendered[1][7:10] == "leb"
    assert rendered[2].startswith("bad apple")
