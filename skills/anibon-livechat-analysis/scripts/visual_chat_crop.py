"""ROI calculation and ffmpeg filter generation for live chat overlays."""

ROI_PRESETS = {
    "bottom-right": {
        "w_ratio": 0.25,
        "h_ratio": 0.42,
        "x_ratio": 0.75,
        "y_ratio": 0.54,
    },
    "left": {
        "w_ratio": 0.28,
        "h_ratio": 0.60,
        "x_ratio": 0.01,
        "y_ratio": 0.22,
    },
}


def get_chat_roi(layout: str, width: int, height: int) -> dict[str, int]:
    if layout not in ROI_PRESETS:
        raise ValueError(f"Unknown layout: {layout}. Valid: {list(ROI_PRESETS.keys())}")
    cfg = ROI_PRESETS[layout]
    return {
        "w": int(width * cfg["w_ratio"]),
        "h": int(height * cfg["h_ratio"]),
        "x": int(width * cfg["x_ratio"]),
        "y": int(height * cfg["y_ratio"]),
    }


def build_crop_filter(roi: dict[str, int]) -> str:
    return f"crop={roi['w']}:{roi['h']}:{roi['x']}:{roi['y']}"
