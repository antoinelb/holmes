# Configuration

HOLMES can be customized using environment variables. These control server behavior such as the host address, port, and development features.

## Configuration File

Create a `.env` file in your working directory to set configuration options:

```env
DEBUG=True
RELOAD=True
HOST=127.0.0.1
PORT=8000
```

## Available Options

### DEBUG

Enables debug mode with more verbose logging.

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `False` |
| Values | `True`, `False` |

```env
DEBUG=True
```

When enabled:

- More detailed error messages
- Verbose logging output
- Useful for troubleshooting issues

### RELOAD

Enables auto-reload on code changes. Primarily useful for development.

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `False` |
| Values | `True`, `False` |

```env
RELOAD=True
```

When enabled:

- Server automatically restarts when source files change
- Useful when developing or customizing HOLMES

!!! warning "Development Only"
    Do not enable `RELOAD` in production environments as it impacts performance.

### HOST

The network interface to bind the server to.

| Property | Value |
|----------|-------|
| Type | String (IP address) |
| Default | `127.0.0.1` |

```env
HOST=127.0.0.1
```

Common values:

- `127.0.0.1` - Only accessible from local machine (recommended for personal use)
- `0.0.0.0` - Accessible from any network interface (use for sharing on a network)

!!! danger "Network Security"
    Setting `HOST=0.0.0.0` exposes HOLMES to your network. Only use this on trusted networks and consider firewall rules.

### PORT

The port number for the web server.

| Property | Value |
|----------|-------|
| Type | Integer |
| Default | `8000` |
| Range | `1`-`65535` |

```env
PORT=8000
```

!!! tip "Port Conflicts"
    If port 8000 is already in use by another application, change to an alternative like `8001` or `8080`.

## Example Configurations

### Personal Use (Default)

Minimal configuration for local use:

```env
# .env - Personal use
# No file needed, defaults are fine
```

Or explicitly:

```env
HOST=127.0.0.1
PORT=8000
```

### Development

Configuration for developing HOLMES:

```env
# .env - Development
DEBUG=True
RELOAD=True
```

### Classroom/Lab Setting

Share HOLMES with students on a local network:

```env
# .env - Classroom
HOST=0.0.0.0
PORT=8000
```

Students can then access HOLMES at `http://<your-ip>:8000`.

## Applying Configuration

Configuration changes require restarting the server:

1. Stop the running server (Ctrl+C)
2. Edit or create the `.env` file
3. Restart the server: `holmes`

## Environment Variables

Instead of a `.env` file, you can set environment variables directly:

=== "Linux/macOS"

    ```bash
    export PORT=8080
    holmes
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:PORT = "8080"
    holmes
    ```

=== "Windows (CMD)"

    ```batch
    set PORT=8080
    holmes
    ```

Environment variables take precedence over `.env` file values.

## Validation

HOLMES validates configuration values on startup. Invalid values result in a startup error:

```
HolmesConfigError: Invalid port: -1. Port must be between 1 and 65535.
```

Check the error message and correct your configuration.
