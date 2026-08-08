from typing import LiteralString, cast

import altair as alt

#########
# types #
#########

title_font = '"Playfair Display", serif'
font = "Lato, sans-serif"

named_colours = {
    "black": "#052946",
    "red": "#ce153d",
    "blue": "#18bbbb",
    "yellow": "#fdc414",
    "purple": "#6850af",
    "green": "#196a5e",
    "brown": "#7a5315",
}

colours = list(named_colours.values())

##########
# public #
##########


@alt.theme.register("default", enable=True)
def default_theme() -> alt.theme.ThemeConfig:
    return {
        "config": {
            "font": font,
            "view": {
                "stroke": None,
            },
            "axis": {
                "labelFontSize": 12,
                "titleFontSize": 14,
                "titleFontWeight": "normal",
            },
            "axisX": {
                "grid": False,
            },
            "axisY": {
                "grid": True,
            },
            "title": {
                "font": title_font,
                "fontSize": 18,
                "fontWeight": "normal",
                "anchor": "middle",
            },
            "mark": {
                "color": cast(LiteralString, colours[0]),
            },
            "point": {
                "filled": True,
            },
            "range": {
                "category": colours,
            },
            "legend": {
                "labelFont": font,
                "titleFont": font,
            },
            "header": {
                "labelFont": font,
                "titleFont": font,
            },
            "text": {
                "font": font,
            },
        }
    }
