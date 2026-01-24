# Getting Started

Welcome to HOLMES (HydrOLogical Modeling Educational Software), a web-based tool designed to teach operational hydrology. This section will guide you through installing HOLMES and getting your first model calibration running.

## What is HOLMES?

HOLMES is educational software developed at Université Laval, Québec, Canada. It provides an interactive web interface for:

- **Calibrating** hydrological models (GR4J, Bucket) against observed streamflow data
- **Simulating** streamflow using calibrated model parameters
- **Projecting** future streamflow under climate change scenarios

## What You'll Learn

This Getting Started guide covers:

| Section | Description |
|---------|-------------|
| [Installation](installation.md) | Installing HOLMES via pip or from source |
| [Quickstart](quickstart.md) | Your first calibration in 5 steps |
| [Configuration](configuration.md) | Customizing server settings |

## Prerequisites

Before installing HOLMES, ensure you have:

- **Python 3.11 or newer** installed on your system
- A modern web browser (Chrome, Firefox, Safari, or Edge)

## Quick Install

Install HOLMES with:

```bash
pip install holmes-hydro
```

Then start the server:

```bash
holmes
```

The web interface opens automatically in your default browser. If needed, you can also access it manually at [http://127.0.0.1:8000](http://127.0.0.1:8000).

For detailed installation instructions, see the [Installation](installation.md) page.

## Next Steps

- Follow the [Quickstart](quickstart.md) tutorial to run your first calibration
- Read the [User Guide](../user-guide/index.md) for comprehensive interface documentation
- Explore the [Concepts](../concepts/index.md) section to understand the hydrological models
