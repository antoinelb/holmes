# Settings

The Settings panel provides options to customize your HOLMES experience, including theme selection, data persistence, and application information.

## Accessing Settings

Click the hamburger menu icon (three horizontal lines) in the top-right corner to open the settings panel.

<!-- ![Settings panel](../assets/images/screenshots/settings-panel.png) -->

## Available Settings

### Theme

Toggle between light and dark color themes:

| Theme | Description |
|-------|-------------|
| **Dark** (default) | Dark background with light text - easier on the eyes in low light |
| **Light** | Light background with dark text - better in bright environments |

Click the theme button or press ++t++ to toggle.

The theme preference is saved automatically if **Allow save** is enabled.

### Reset All

Click **Reset all** to clear all saved settings and data:

- Clears all localStorage data for HOLMES
- Resets configuration to defaults
- Removes imported calibrations from Simulation and Projection pages
- Reloads the page

!!! warning "Data Loss"
    Reset all cannot be undone. Any unsaved calibration parameters or imported files will be lost.

### Allow Save

Toggle data persistence between browser sessions:

| State | Behavior |
|-------|----------|
| **Enabled** | Settings and configurations are saved in browser localStorage |
| **Disabled** | Each session starts fresh with defaults |

When enabled, HOLMES remembers:

- Selected model, catchment, objective, etc.
- Calibration date ranges
- Imported calibrations (Simulation/Projection pages)
- Theme preference

!!! tip "Shared Computers"
    Disable **Allow save** on shared or public computers to prevent your settings from persisting for other users.

### Version

Displays the current HOLMES version number.

This information is useful when:

- Reporting bugs or issues
- Checking for updates
- Verifying installation

## Keyboard Shortcuts

The settings panel includes a visual reminder of available shortcuts:

| Shortcut | Action |
|----------|--------|
| ++t++ | Toggle theme |

## Data Storage

HOLMES stores settings in your browser's localStorage under keys prefixed with `holmes--`:

- `holmes--settings--theme`: Light or dark theme
- `holmes--calibration--*`: Calibration page settings
- `holmes--simulation--*`: Simulation page settings
- `holmes--projection--*`: Projection page settings

This data:

- Stays in your browser (not sent to any server)
- Persists until cleared manually or via **Reset all**
- Is specific to the browser and device you're using

## Privacy

HOLMES does not collect or transmit any user data:

- All computations happen locally or on your server
- Settings are stored only in your browser
- No analytics or tracking

## Closing the Panel

Click anywhere outside the settings panel to close it.
