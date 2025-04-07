#!/usr/bin/env python3

import subprocess
from typing import List, Dict
import re

from utils.logger import LogLevel, Logger


def get_volume(logging: Logger) -> int:
    """Get current volume level

    Returns:
        int: Volume percentage
    """
    try:
        output = subprocess.getoutput("pactl get-sink-volume @DEFAULT_SINK@")

        if output == "":
            logging.log(LogLevel.Error, "pactl couldnt get volume!")
            return 0

        volume = int(output.split("/")[1].strip().strip("%"))
        return volume
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting volume: {e}")
        return 0


def set_volume(value: int, logging: Logger) -> None:
    """Set volume level

    Args:
        value (int): Volume percentage
    """
    try:
        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting volume: {e}")


def get_mute_state(logging: Logger) -> bool:
    """Get mute state

    Returns:
        bool: True if muted, False otherwise
    """
    try:
        output = subprocess.getoutput("pactl get-sink-mute @DEFAULT_SINK@")
        return "yes" in output.lower()
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting mute state: {e}")
        return False


def toggle_mute(logging: Logger) -> None:
    """Toggle mute state"""
    try:
        subprocess.run(
            ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed toggling mute: {e}")


def get_sources(logging: Logger) -> List[Dict[str, str]]:
    """Get list of audio sources (input devices)

    Returns:
        List[Dict[str, str]]: List of source dictionaries
    """
    try:
        output = subprocess.getoutput("pactl list sources")
        sources = []
        current_source = {}
        for line in output.split("\n"):
            if line.startswith("Source #"):
                if current_source:
                    sources.append(current_source)
                current_source = {"id": line.split("#")[1].strip()}
            elif ":" in line and current_source:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "Name":
                    current_source["name"] = value
                elif key == "Description":
                    current_source["description"] = value

        if current_source:
            sources.append(current_source)

        return sources
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting sources: {e}")
        return []


def get_applications(logging: Logger) -> List[Dict[str, str]]:
    """Get list of audio applications.

    Returns:
        List[Dict[str, str]]: List of application dictionaries
    """
    output = subprocess.getoutput("pactl list sink-inputs")
    apps = []
    current_app = {}

    for line in output.split("\n"):
        line = line.strip()
        logging.log(LogLevel.Debug, f"Parsing Line: {line}")

        # Handle new application entry
        if line.startswith("Sink Input #"):
            # Process previous app before starting a new one
            _finalize_app(current_app, apps, logging)

            # Start new app entry
            current_app = {"id": line.split("#")[1].strip()}
            logging.log(
                LogLevel.Debug, f"New app detected with ID: {current_app['id']}"
            )

        # Handle application name
        elif "application.name" in line:
            current_app["name"] = line.split("=", 1)[1].strip().strip('"')
            logging.log(
                LogLevel.Debug, f"Detected & Stored App Name: {current_app['name']}"
            )

        # Handle media name as fallback
        elif "media.name" in line and "name" not in current_app:
            current_app["name"] = line.split("=", 1)[1].strip().strip('"')
            logging.log(LogLevel.Debug, f"Using Media Name: {current_app['name']}")

        # Handle binary information
        elif "application.process.binary" in line:
            current_app["binary"] = line.split("=", 1)[1].strip().strip('"')
            logging.log(
                LogLevel.Debug,
                f"Detected & Stored Process Binary: {current_app['binary']}",
            )

            # Try to determine an appropriate icon name based on the binary
            binary_name = current_app["binary"].lower()
            if binary_name:
                current_app["icon"] = binary_name

        # Handle icon name
        elif "application.icon_name" in line:
            current_app["icon"] = line.split("=", 1)[1].strip().strip('"')
            logging.log(
                LogLevel.Debug, f"Detected & Stored App Icon: {current_app['icon']}"
            )

        # Handle volume info
        elif "Volume:" in line:
            logging.log(LogLevel.Debug, f"Found Volume Line: {line}")
            match = re.search(r"(\d+)%", line)
            if match:
                current_app["volume"] = int(match.group(1))  # type: ignore
                logging.log(
                    LogLevel.Debug, f"Detected & Stored Volume: {current_app['volume']}"
                )
            else:
                logging.log(LogLevel.Debug, f"Failed to parse volume from: {line}")

        # Handle sink info
        elif "Sink:" in line:
            sink_id = line.split(":")[1].strip()
            current_app["sink"] = sink_id
            logging.log(
                LogLevel.Debug, f"Detected & Stored Sink ID: {current_app['sink']}"
            )

    # Process the final app entry
    _finalize_app(current_app, apps, logging)

    # Post-process applications to ensure they have icon information
    _ensure_app_icons(apps)

    logging.log(
        LogLevel.Debug,
        f"Parsed Applications: {apps}",
    )
    return apps


def _finalize_app(current_app: Dict[str, str], apps: List[Dict[str, str]], logging: Logger) -> None:
    """Helper to finalize and add an app to the list if valid."""
    if not current_app:
        return

    logging.log(LogLevel.Debug, f"Finalizing app: {current_app}")

    if "name" in current_app and "volume" in current_app:
        apps.append(current_app)
    else:
        logging.log(
            LogLevel.Warn,
            f"Skipping app due to missing name or volume: {current_app}",
        )


def _ensure_app_icons(apps: List[Dict[str, str]]) -> None:
    """Ensure all apps have an icon property."""
    for app in apps:
        if "icon" not in app and "binary" in app:
            app["icon"] = app["binary"].lower()

        if "icon" not in app and "name" in app:
            # Create icon name from app name (lowercase, remove spaces)
            app["icon"] = app["name"].lower().replace(" ", "-")


def get_sink_name_by_id(sink_id: str, logging: Logger) -> str:
    """Get the name of a sink by its ID number

    Args:
        sink_id (str): The sink ID (number)

    Returns:
        str: The sink name
    """
    try:
        output = subprocess.getoutput("pactl list sinks short")
        for line in output.split("\n"):
            parts = line.split()
            if parts and parts[0] == sink_id:
                return parts[1]  # The second column is the sink name
        return ""
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting sink name: {e}")
        return ""


def set_application_volume(app_id: str, value: int, logging: Logger) -> None:
    """Set volume for a specific application

    Args:
        app_id (str): Application sink input ID
        value (int): Volume percentage
    """
    try:
        subprocess.run(
            ["pactl", "set-sink-input-volume", app_id, f"{value}%"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting application volume: {e}")


def move_application_to_sink(app_id: str, sink_name: str, logging: Logger) -> None:
    """Move an application to a different audio output device

    Args:
        app_id (str): Application sink input ID
        sink_name (str): Name of the sink to move the application to
    """
    try:
        subprocess.run(["pactl", "move-sink-input", app_id, sink_name], check=True)
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed moving application to sink: {e}")


def set_default_sink(sink_name: str, logging: Logger) -> None:
    try:
        subprocess.run(["pactl", "set-default-sink", sink_name], check=True)

        # Move all running apps to the new sink
        output = subprocess.getoutput("pactl list short sink-inputs")
        for line in output.split("\n"):
            if line.strip():
                app_id = line.split()[0]
                subprocess.run(
                    ["pactl", "move-sink-input", app_id, sink_name], check=True
                )

    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting default sink: {e}")


def get_sinks(logging: Logger) -> List[Dict[str, str]]:
    """Get list of audio sinks (output devices)."""
    try:
        output = subprocess.getoutput("pactl list sinks")
        sinks = []
        current_sink = {}

        for line in output.split("\n"):
            if line.startswith("Sink #"):
                if current_sink:
                    sinks.append(current_sink)
                current_sink = {"id": line.split("#")[1].strip()}
            elif ":" in line and current_sink:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "Name":
                    current_sink["name"] = value
                elif key == "Description":
                    current_sink["description"] = value

        if current_sink:
            sinks.append(current_sink)

        return sinks
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting sinks: {e}")
        return []


def set_default_source(source_name: str, logging: Logger) -> None:
    """Set default audio input device

    Args:
        source_name (str): Source name
    """
    try:
        subprocess.run(["pactl", "set-default-source", source_name], check=True)
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting default source: {e}")


def get_mic_volume(logging: Logger) -> int:
    """Get microphone volume level

    Returns:
        int: Volume percentage
    """
    try:
        output = subprocess.getoutput("pactl get-source-volume @DEFAULT_SOURCE@")
        volume = int(output.split("/")[1].strip().strip("%"))
        return volume
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting mic volume: {e}")
        return 0


def set_mic_volume(value: int, logging: Logger) -> None:
    """Set microphone volume level

    Args:
        value (int): Volume percentage
    """
    try:
        subprocess.run(
            ["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{value}%"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting mic volume: {e}")


def get_mic_mute_state(logging: Logger) -> bool:
    """Get microphone mute state

    Returns:
        bool: True if muted, False otherwise
    """
    try:
        output = subprocess.getoutput("pactl get-source-mute @DEFAULT_SOURCE@")
        return "yes" in output.lower()
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting mic mute state: {e}")
        return False


def toggle_mic_mute(logging: Logger) -> None:
    """Toggle microphone mute state"""
    try:
        subprocess.run(
            ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed toggling mic mute: {e}")


def get_application_mute_state(app_id: str, logging: Logger) -> bool:
    """Get mute state for a specific application

    Args:
        app_id (str): Application sink input ID

    Returns:
        bool: True if muted, False otherwise
    """
    try:
        output = subprocess.getoutput(
            f"pactl list sink-inputs | grep -A 15 'Sink Input #{app_id}'"
        )
        return "Mute: yes" in output
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting application mute state: {e}")
        return False


def toggle_application_mute(app_id: str, logging: Logger) -> None:
    """Toggle mute state for a specific application

    Args:
        app_id (str): Application sink input ID
    """
    try:
        subprocess.run(["pactl", "set-sink-input-mute", app_id, "toggle"], check=True)
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed toggling application mute: {e}")


def get_source_outputs(logging: Logger) -> List[Dict[str, str]]:
    """Get list of source outputs (applications using microphone)

    Returns:
        List[Dict[str, str]]: List of source output dictionaries
    """
    try:
        output = subprocess.getoutput("pactl list source-outputs")
        return _parse_source_outputs(output, logging)
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting source outputs: {e}")
        return []


def _parse_source_outputs(output: str, logging: Logger) -> List[Dict[str, str]]:
    """Parse source outputs from pactl output

    Args:
        output (str): Output from pactl command
        logging (Logger): Logger instance

    Returns:
        List[Dict[str, str]]: List of source output dictionaries
    """
    outputs = []
    current_output = {}
    # Track seen applications and instance counters
    seen_apps = {}

    for line in output.split("\n"):
        line = line.strip()
        logging.log(LogLevel.Debug, f"Parsing source output line: {line}")

        if line.startswith("Source Output #"):
            _process_current_output(current_output, outputs, logging)
            current_output = {"id": line.split("#")[1].strip()}
            logging.log(
                LogLevel.Debug,
                f"New source output detected with ID: {current_output['id']}",
            )

        elif "application.name" in line:
            _process_app_name(current_output, line, seen_apps, logging)

        elif "media.name" in line and "name" not in current_output:
            _process_media_name(current_output, line, seen_apps, logging)

        elif "application.process.binary" in line:
            _process_binary(current_output, line, logging)

        elif "application.icon_name" in line:
            current_output["icon"] = line.split("=", 1)[1].strip().strip('"')
            logging.log(
                LogLevel.Debug,
                f"Detected & Stored Source Output Icon: {current_output['icon']}",
            )

        elif "Mute:" in line:
            current_output["muted"] = "yes" in line.lower()  # type: ignore
            logging.log(
                LogLevel.Debug,
                f"Detected & Stored Source Output Mute State: {current_output['muted']}",
            )

        elif "Source:" in line:
            source_id = line.split(":")[1].strip()
            current_output["source"] = source_id
            logging.log(
                LogLevel.Debug,
                f"Detected & Stored Source ID: {current_output['source']}",
            )

    # Process final output
    _process_current_output(current_output, outputs, logging)

    # Ensure all outputs have icon information
    _ensure_output_icons(outputs)

    logging.log(LogLevel.Debug, f"Parsed Source Outputs: {outputs}")
    return outputs


def _process_current_output(current_output: Dict, outputs: List[Dict], logging: Logger) -> None:
    """Process current output and add to outputs list if valid"""
    if not current_output:
        return

    logging.log(LogLevel.Debug, f"Finalizing source output: {current_output}")
    if "id" in current_output and "name" in current_output:
        # Add current output to the list
        outputs.append(current_output)
    else:
        logging.log(
            LogLevel.Debug,
            f"Skipping source output due to missing id or name: {current_output}",
        )


def _process_app_name(current_output: Dict, line: str, seen_apps: Dict, logging: Logger) -> None:
    """Process application name from pactl output line"""
    app_name = line.split("=", 1)[1].strip().strip('"')

    # Track instances of the same application
    if app_name in seen_apps:
        seen_apps[app_name] += 1
        # For additional instances, append instance number
        current_output["name"] = f"{app_name} ({seen_apps[app_name]})"
        logging.log(
            LogLevel.Debug,
            f"Multiple instances detected, renamed to: {current_output['name']}",
        )
    else:
        seen_apps[app_name] = 1
        current_output["name"] = app_name
        logging.log(
            LogLevel.Debug,
            f"Detected & Stored Source Output Name: {current_output['name']}",
        )

    # Store original name for icon lookup
    current_output["original_name"] = app_name


def _process_media_name(current_output: Dict, line: str, seen_apps: Dict, logging: Logger) -> None:
    """Process media name from pactl output line"""
    media_name = line.split("=", 1)[1].strip().strip('"')

    # Track instances of the same application
    if media_name in seen_apps:
        seen_apps[media_name] += 1
        # For additional instances, append instance number
        current_output["name"] = f"{media_name} ({seen_apps[media_name]})"
        logging.log(
            LogLevel.Debug,
            f"Multiple instances detected, renamed to: {current_output['name']}",
        )
    else:
        seen_apps[media_name] = 1
        current_output["name"] = media_name
        logging.log(
            LogLevel.Debug,
            f"Using Media Name for Source Output: {current_output['name']}",
        )

    # Store original name for icon lookup
    current_output["original_name"] = media_name


def _process_binary(current_output: Dict, line: str, logging: Logger) -> None:
    """Process binary information from pactl output line"""
    current_output["binary"] = line.split("=", 1)[1].strip().strip('"')
    logging.log(
        LogLevel.Debug,
        f"Detected & Stored Source Output Process Binary: {current_output['binary']}",
    )

    # Try to determine an appropriate icon name based on the binary
    binary_name = current_output["binary"].lower()
    if binary_name:
        current_output["icon"] = binary_name


def _ensure_output_icons(outputs: List[Dict]) -> None:
    """Ensure all outputs have icon information"""
    for output in outputs:
        if "icon" not in output and "binary" in output:
            output["icon"] = output["binary"].lower()

        if "icon" not in output and "original_name" in output:
            # Create icon name from original app name (lowercase, remove spaces)
            output["icon"] = output["original_name"].lower().replace(" ", "-")
        elif "icon" not in output and "name" in output:
            # Fall back to modified name if original name not available
            output["icon"] = output["name"].lower().replace(" ", "-").split(" (")[0]


def get_application_mic_mute_state(app_id: str, logging: Logger) -> bool:
    """Get microphone mute state for a specific application

    Args:
        app_id (str): Application source output ID

    Returns:
        bool: True if muted, False otherwise
    """
    try:
        output = subprocess.getoutput(
            f"pactl list source-outputs | grep -A 15 'Source Output #{app_id}'"
        )
        return "Mute: yes" in output
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting application mic mute state: {e}")
        return False


def toggle_application_mic_mute(app_id: str, logging: Logger) -> None:
    """Toggle microphone mute state for a specific application

    Args:
        app_id (str): Application source output ID
    """
    try:
        subprocess.run(
            ["pactl", "set-source-output-mute", app_id, "toggle"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed toggling application mic mute: {e}")


def get_application_mic_volume(app_id: str, logging: Logger) -> int:
    """Get microphone volume level for a specific application

    Args:
        app_id (str): Application source output ID

    Returns:
        int: Volume percentage
    """
    try:
        output = subprocess.getoutput(
            f"pactl list source-outputs | grep -A 15 'Source Output #{app_id}'"
        )

        # Find volume line
        for line in output.split("\n"):
            if "Volume:" in line:
                # Parse volume percentage
                match = re.search(r"(\d+)%", line)
                if match:
                    return int(match.group(1))

        # Default return if volume not found
        return 100
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting application mic volume: {e}")
        return 100


def set_application_mic_volume(app_id: str, value: int, logging: Logger) -> None:
    """Set microphone volume level for a specific application

    Args:
        app_id (str): Application source output ID
        value (int): Volume percentage
    """
    try:
        subprocess.run(
            ["pactl", "set-source-output-volume", app_id, f"{value}%"], check=True
        )
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting application mic volume: {e}")
