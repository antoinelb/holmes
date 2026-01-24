# User Guide

This guide provides comprehensive documentation for using the HOLMES web interface. Whether you're a student learning about hydrological modeling or an instructor teaching operational hydrology, this guide will help you make the most of HOLMES.

## Overview

HOLMES provides three main workflows, each accessible from the navigation menu:

| Workflow | Purpose | Prerequisites |
|----------|---------|---------------|
| [Calibration](calibration.md) | Find optimal model parameters by fitting to observed data | Catchment data |
| [Simulation](simulation.md) | Run the model with calibrated parameters on any time period | Calibrated parameters |
| [Projection](projection.md) | Explore future streamflow under climate change scenarios | Calibrated parameters + Climate data |

## Interface Structure

The HOLMES interface consists of:

<!-- ![Interface overview](../assets/images/screenshots/interface-navigation.png) -->

1. **Navigation Menu** (top left corner) - Switch between Calibration, Simulation, and Projection
2. **Settings Menu** (top right corner) - Theme toggle, data persistence, version info
3. **Configuration Panel** (top) - Model and run settings
4. **Results Panel** (bottom) - Charts and metrics

## Typical Workflow

A typical HOLMES session follows this pattern:

1. **Calibrate** a model against observed streamflow data
2. **Export** the calibrated parameters to a JSON file
3. **Simulate** streamflow for validation periods or other catchments
4. **Project** future conditions using climate model data

## Quick Links

### By Task

- [Run my first calibration](calibration.md#running-a-manual-calibration)
- [Use automatic optimization](calibration.md#running-an-automatic-calibration)
- [Compare multiple models](simulation.md#multimodel-simulation)
- [Explore climate projections](projection.md)
- [Export my results](calibration.md#exporting-results)
- [Change the theme](settings.md#theme)

### By Feature

- [Understanding parameter sliders](calibration.md#manual-calibration-settings)
- [Interpreting performance metrics](simulation.md#understanding-results)
- [Zoom and pan on charts](interface-overview.md#chart-interactions)
- [Save my settings between sessions](settings.md#allow-save)

## User Guide Sections

<div class="grid cards" markdown>

-   :material-tune: **[Interface Overview](interface-overview.md)**

    ---

    Learn the common UI elements: navigation, charts, forms, and keyboard shortcuts

-   :material-chart-line: **[Calibration](calibration.md)**

    ---

    Manual and automatic model calibration against observed data

-   :material-play-circle: **[Simulation](simulation.md)**

    ---

    Forward model runs with calibrated parameters

-   :material-weather-cloudy: **[Projection](projection.md)**

    ---

    Climate change impact assessment

-   :material-cog: **[Settings](settings.md)**

    ---

    Theme, data persistence, and other preferences

</div>
