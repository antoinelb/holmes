import plotly.graph_objects as go

#########
# types #
#########


# Dark theme colors - vibrant colors for dark backgrounds
colours = [
    "#fd7f6f",
    "#7eb0d5",
    "#b2e061",
    "#bd7ebe",
    "#ffb55a",
    "#ffee65",
    "#beb9db",
    "#fdcce5",
    "#8bd3c7",
]

# Light theme colors - soft, muted palette for light backgrounds
light_colours = [
    "#d97373",  # soft coral red
    "#5a9bc7",  # muted blue
    "#8fba4d",  # soft green
    "#a866aa",  # muted purple
    "#e89a3c",  # soft orange
    "#d4b83e",  # muted yellow
    "#9b94c4",  # soft lavender
    "#e5a8c8",  # soft pink
    "#6cb3a3",  # muted teal
]


template = {
    "layout": go.Layout(
        {
            "title": {
                "xanchor": "center",
                "x": 0.5,
            },
            "font": {
                "color": "rgb(230,230,230)",
            },
            "xaxis": {
                "gridcolor": "#2A3459",
                "linecolor": "rgb(230,230,230)",
                "automargin": True,
            },
            "yaxis": {
                "gridcolor": "#2A3459",
                "linecolor": "rgb(230,230,230)",
                "automargin": True,
            },
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "colorway": colours,
            "legend_traceorder": "normal",
        }
    )
}

light_template = {
    "layout": go.Layout(
        {
            "title": {
                "xanchor": "center",
                "x": 0.5,
            },
            "font": {
                "color": "rgb(50,50,50)",
            },
            "xaxis": {
                "gridcolor": "#e5e5e5",
                "linecolor": "rgb(80,80,80)",
                "automargin": True,
            },
            "yaxis": {
                "gridcolor": "#e5e5e5",
                "linecolor": "rgb(80,80,80)",
                "automargin": True,
            },
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "colorway": light_colours,
            "legend_traceorder": "normal",
        }
    )
}

##########
# public #
##########


def convert_colour(
    colour: str, *, opacity: float = 1
) -> str:  # pragma: no cover
    """
    Convert a hex color to an rgba color string with specified opacity.

    Parameters
    ----------
    colour : str
        Hex color string (e.g., "#fd7f6f")
    opacity : float, default 1
        Opacity value between 0 and 1

    Returns
    -------
    str
        RGBA color string (e.g., "rgba(253,127,111,1)")
    """
    colour = colour.lstrip("#")
    return (
        "rgba("
        + ",".join(str(int(colour[i : i + 2], 16)) for i in (0, 2, 4))
        + f",{opacity})"
    )


def compute_domain(
    i: int, n: int, pad: float, *, reverse: bool = False
) -> tuple[float, float]:
    if reverse:
        i = n - i - 1
    total_gap = pad * (n - 1)
    width = (1 - total_gap) / n
    start = i * (width + pad)
    end = start + width
    return start, end
