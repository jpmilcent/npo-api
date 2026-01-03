def _format_focal_length(value: float | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = float(value)
        return f"{val:g} mm"
    except (ValueError, TypeError):
        return str(value)


def _format_aperture(value: float | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = float(value)
        return f"f/{val:g}"
    except (ValueError, TypeError):
        return str(value)


def _format_shutter_speed(value: float | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = float(value)
        if 0 < val < 1:
            return f"1/{round(1 / val)}"
        return str(int(val)) if val.is_integer() else str(val)
    except (ValueError, TypeError):
        return value


def _format_flash(value: float | str | int | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(float(value))
        if val == 0:
            return "No Flash"

        parts = []
        parts.append("Flash fired" if val & 1 else "Flash did not fire")

        mode = (val >> 3) & 0b11
        if mode == 3:
            parts.append("auto")
        elif mode == 1:
            parts.append("compulsory")
        elif mode == 2:
            parts.append("suppressed")

        if (val >> 6) & 1:
            parts.append("red-eye reduction")

        return ", ".join(parts)
    except (ValueError, TypeError):
        return str(value)


def _format_orientation(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        orientations = {
            1: "Horizontal (normal)",
            2: "Mirror horizontal",
            3: "Rotate 180",
            4: "Mirror vertical",
            5: "Mirror horizontal and rotate 270 CW",
            6: "Rotate 90 CW",
            7: "Mirror horizontal and rotate 90 CW",
            8: "Rotate 270 CW",
        }
        return orientations.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)


def _format_pixels(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(float(value))
        return f"{val} px"
    except (ValueError, TypeError):
        return str(value)


def _format_white_balance(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        modes = {
            0: "Auto",
            1: "Manual",
        }
        return modes.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)


def _format_exposure_program(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        programs = {
            0: "Not defined",
            1: "Manual",
            2: "Normal program",
            3: "Aperture priority",
            4: "Shutter priority",
            5: "Creative program",
            6: "Action program",
            7: "Portrait mode",
            8: "Landscape mode",
        }
        return programs.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)


def _format_exposure_mode(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        modes = {
            0: "Auto",
            1: "Manual",
            2: "Auto bracket",
        }
        return modes.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)


def _format_exposure_compensation(value: float | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = float(value)
        if val == 0:
            return "0 EV"
        return f"{val:+.2g} EV"
    except (ValueError, TypeError):
        return str(value)


def _format_metering_mode(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        modes = {
            0: "Unknown",
            1: "Average",
            2: "Center-weighted average",
            3: "Spot",
            4: "Multi-spot",
            5: "Pattern",
            6: "Partial",
            255: "Other",
        }
        return modes.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)


def _format_scene_capture_type(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        types = {
            0: "Standard",
            1: "Landscape",
            2: "Portrait",
            3: "Night scene",
        }
        return types.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)


def _format_scene_type(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        if val == 1:
            return "Directly photographed"
        return str(val)
    except (ValueError, TypeError):
        return str(value)


def _format_color_space(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        val = int(value)
        spaces = {
            1: "sRGB",
            2: "Adobe RGB",
            65535: "Uncalibrated",
        }
        return spaces.get(val, str(val))
    except (ValueError, TypeError):
        return str(value)
