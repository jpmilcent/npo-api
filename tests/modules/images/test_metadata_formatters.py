from unittest.mock import patch

import pytest

from npo.modules.images.metadata_formatters import MetadataFormatter


@pytest.fixture(autouse=True)
def mock_babel_translation():
    """
    Mock la fonction de traduction '_' utilisée dans le module pour retourner
    simplement la chaîne d'entrée. Cela permet de tester les valeurs attendues
    sans se soucier de la locale active ou de l'implémentation de babel.
    """
    with patch("npo.modules.images.metadata_formatters._", side_effect=lambda x: x):
        yield


class TestMetadataFormatter:
    def test_format_focal_length(self):
        assert MetadataFormatter.format_focal_length(None) is None
        assert MetadataFormatter.format_focal_length(50) == "50 mm"
        assert MetadataFormatter.format_focal_length("35.5") == "35.5 mm"
        assert MetadataFormatter.format_focal_length("invalid") == "invalid"

    def test_format_aperture(self):
        assert MetadataFormatter.format_aperture(None) is None
        assert MetadataFormatter.format_aperture(2.8) == "f/2.8"
        assert MetadataFormatter.format_aperture("5.6") == "f/5.6"
        assert MetadataFormatter.format_aperture("invalid") == "invalid"

    def test_format_shutter_speed(self):
        assert MetadataFormatter.format_shutter_speed(None) is None
        assert MetadataFormatter.format_shutter_speed(1) == "1"
        assert MetadataFormatter.format_shutter_speed(0.5) == "1/2"
        assert MetadataFormatter.format_shutter_speed(0.01) == "1/100"
        assert MetadataFormatter.format_shutter_speed(2.5) == "2.5"
        assert MetadataFormatter.format_shutter_speed("invalid") == "invalid"

    def test_format_flash(self):
        assert MetadataFormatter.format_flash(None) is None
        assert MetadataFormatter.format_flash(0) == "No Flash"

        # Cas simple : Flash fired (Bit 0 = 1)
        assert MetadataFormatter.format_flash(1) == "Flash fired"

        # Cas complexe : Flash fired (1) + Auto mode (3 << 3 = 24) -> 25
        # 25 = 11001 (binaire)
        assert MetadataFormatter.format_flash(25) == "Flash fired, auto"

        # Cas complexe : Flash did not fire (0) + Compulsory mode (1 << 3 = 8) -> 8
        # 8 = 1000 (binaire)
        assert MetadataFormatter.format_flash(8) == "Flash did not fire, compulsory"

        # Cas complexe : Flash fired (1) + Red-eye reduction (1 << 6 = 64) -> 65
        assert MetadataFormatter.format_flash(65) == "Flash fired, red-eye reduction"

        assert MetadataFormatter.format_flash("invalid") == "invalid"

    def test_format_orientation(self):
        assert MetadataFormatter.format_orientation(None) is None
        assert MetadataFormatter.format_orientation(1) == "Horizontal (normal)"
        assert MetadataFormatter.format_orientation(6) == "Rotate 90 CW"
        assert MetadataFormatter.format_orientation("3") == "Rotate 180"
        # Valeur inconnue
        assert MetadataFormatter.format_orientation(99) == "99"
        assert MetadataFormatter.format_orientation("invalid") == "invalid"

    def test_format_pixels(self):
        assert MetadataFormatter.format_pixels(None) is None
        assert MetadataFormatter.format_pixels(1000) == "1000 px"
        assert MetadataFormatter.format_pixels("2048.0") == "2048 px"
        assert MetadataFormatter.format_pixels("invalid") == "invalid"

    def test_format_white_balance(self):
        assert MetadataFormatter.format_white_balance(None) is None
        assert MetadataFormatter.format_white_balance(0) == "Auto"
        assert MetadataFormatter.format_white_balance(1) == "Manual"
        assert MetadataFormatter.format_white_balance(99) == "99"
        assert MetadataFormatter.format_white_balance("invalid") == "invalid"

    def test_format_exposure_program(self):
        assert MetadataFormatter.format_exposure_program(None) is None
        assert MetadataFormatter.format_exposure_program(1) == "Manual"
        assert MetadataFormatter.format_exposure_program(2) == "Normal program"
        assert MetadataFormatter.format_exposure_program(99) == "99"
        assert MetadataFormatter.format_exposure_program("invalid") == "invalid"

    def test_format_exposure_mode(self):
        assert MetadataFormatter.format_exposure_mode(None) is None
        assert MetadataFormatter.format_exposure_mode(0) == "Auto"
        assert MetadataFormatter.format_exposure_mode(1) == "Manual"
        assert MetadataFormatter.format_exposure_mode(2) == "Auto bracket"
        assert MetadataFormatter.format_exposure_mode(99) == "99"
        assert MetadataFormatter.format_exposure_mode("invalid") == "invalid"

    def test_format_exposure_compensation(self):
        assert MetadataFormatter.format_exposure_compensation(None) is None
        assert MetadataFormatter.format_exposure_compensation(0) == "0 EV"
        assert MetadataFormatter.format_exposure_compensation(1) == "+1 EV"
        assert MetadataFormatter.format_exposure_compensation(-0.33) == "-0.33 EV"
        assert MetadataFormatter.format_exposure_compensation("invalid") == "invalid"

    def test_format_metering_mode(self):
        assert MetadataFormatter.format_metering_mode(None) is None
        assert MetadataFormatter.format_metering_mode(2) == "Center-weighted average"
        assert MetadataFormatter.format_metering_mode(5) == "Pattern"
        assert MetadataFormatter.format_metering_mode(255) == "Other"
        assert MetadataFormatter.format_metering_mode(99) == "99"
        assert MetadataFormatter.format_metering_mode("invalid") == "invalid"

    def test_format_scene_capture_type(self):
        assert MetadataFormatter.format_scene_capture_type(None) is None
        assert MetadataFormatter.format_scene_capture_type(0) == "Standard"
        assert MetadataFormatter.format_scene_capture_type(3) == "Night scene"
        assert MetadataFormatter.format_scene_capture_type(99) == "99"
        assert MetadataFormatter.format_scene_capture_type("invalid") == "invalid"

    def test_format_scene_type(self):
        assert MetadataFormatter.format_scene_type(None) is None
        assert MetadataFormatter.format_scene_type(1) == "Directly photographed"
        assert MetadataFormatter.format_scene_type(2) == "2"
        assert MetadataFormatter.format_scene_type("invalid") == "invalid"

    def test_format_color_space(self):
        assert MetadataFormatter.format_color_space(None) is None
        assert MetadataFormatter.format_color_space(1) == "sRGB"
        assert MetadataFormatter.format_color_space(2) == "Adobe RGB"
        assert MetadataFormatter.format_color_space(65535) == "Uncalibrated"
        assert MetadataFormatter.format_color_space(99) == "99"
        assert MetadataFormatter.format_color_space("invalid") == "invalid"
