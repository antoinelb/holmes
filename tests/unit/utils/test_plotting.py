from typing import Any, cast

from holmes.utils.plotting import (
    colours,
    default_theme,
    font,
    named_colours,
    title_font,
)


class TestDefaultTheme:
    def test_theme_config(self):
        config = cast(dict[str, Any], default_theme())["config"]
        assert config["font"] == font
        assert config["title"]["font"] == title_font
        assert config["mark"]["color"] == colours[0]
        assert config["range"]["category"] == colours

    def test_colours_follow_named_colours(self):
        assert colours == list(named_colours.values())
