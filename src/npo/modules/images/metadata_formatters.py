from fastapi_babel import _


class ExifFlash:
    """Constants for decoding EXIF Flash tag."""

    FIRED_MASK = 1
    MODE_SHIFT = 3
    MODE_MASK = 0b11
    MODE_COMPULSORY = 1
    MODE_SUPPRESSED = 2
    MODE_AUTO = 3
    RED_EYE_SHIFT = 6


class MetadataFormatter:
    @staticmethod
    def format_focal_length(value: float | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = float(value)
            return f"{val:g} mm"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_aperture(value: float | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = float(value)
            return f"f/{val:g}"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_shutter_speed(value: float | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = float(value)
            if 0 < val < 1:
                return f"1/{round(1 / val)}"
            return str(int(val)) if val.is_integer() else str(val)
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_flash(value: float | str | int | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(float(value))
            if val == 0:
                return _("No Flash")

            parts = []
            parts.append(
                _("Flash fired") if val & ExifFlash.FIRED_MASK else _("Flash did not fire")
            )

            mode = (val >> ExifFlash.MODE_SHIFT) & ExifFlash.MODE_MASK
            if mode == ExifFlash.MODE_AUTO:
                parts.append(_("auto"))
            elif mode == ExifFlash.MODE_COMPULSORY:
                parts.append(_("compulsory"))
            elif mode == ExifFlash.MODE_SUPPRESSED:
                parts.append(_("suppressed"))

            if (val >> ExifFlash.RED_EYE_SHIFT) & 1:
                parts.append(_("red-eye reduction"))

            return ", ".join(parts)
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_orientation(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            orientations = {
                1: _("Horizontal (normal)"),
                2: _("Mirror horizontal"),
                3: _("Rotate 180"),
                4: _("Mirror vertical"),
                5: _("Mirror horizontal and rotate 270 CW"),
                6: _("Rotate 90 CW"),
                7: _("Mirror horizontal and rotate 90 CW"),
                8: _("Rotate 270 CW"),
            }
            return orientations.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_pixels(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(float(value))
            return f"{val} px"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_white_balance(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            modes = {
                0: _("Auto"),
                1: _("Manual"),
            }
            return modes.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_exposure_program(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            programs = {
                0: _("Not defined"),
                1: _("Manual"),
                2: _("Normal program"),
                3: _("Aperture priority"),
                4: _("Shutter priority"),
                5: _("Creative program"),
                6: _("Action program"),
                7: _("Portrait mode"),
                8: _("Landscape mode"),
            }
            return programs.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_exposure_mode(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            modes = {
                0: _("Auto"),
                1: _("Manual"),
                2: _("Auto bracket"),
            }
            return modes.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_exposure_compensation(value: float | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = float(value)
            if val == 0:
                return "0 EV"
            return f"{val:+.2g} EV"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_metering_mode(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            modes = {
                0: _("Unknown"),
                1: _("Average"),
                2: _("Center-weighted average"),
                3: _("Spot"),
                4: _("Multi-spot"),
                5: _("Pattern"),
                6: _("Partial"),
                255: _("Other"),
            }
            return modes.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_scene_capture_type(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            types = {
                0: _("Standard"),
                1: _("Landscape"),
                2: _("Portrait"),
                3: _("Night scene"),
            }
            return types.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_scene_type(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            if val == 1:
                return _("Directly photographed")
            return str(val)
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_color_space(value: int | str | None) -> str | None:
        if value is None:
            return None
        try:
            val = int(value)
            spaces = {
                1: _("sRGB"),
                2: _("Adobe RGB"),
                65535: _("Uncalibrated"),
            }
            return spaces.get(val, str(val))
        except (ValueError, TypeError):
            return str(value)
