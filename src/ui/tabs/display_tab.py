#!/usr/bin/env python3

import gi  # type: ignore
import subprocess

from utils.logger import LogLevel, Logger

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # type: ignore

from utils.settings import load_settings, save_settings
from tools.display import get_brightness, set_brightness


class DisplayTab(Gtk.Box):
    """Display settings tab"""

    def __init__(self, logging: Logger):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.logging = logging
        self.update_timeout_id = None
        self.update_interval = 500  # milliseconds

        self.set_margin_start(15)
        self.set_margin_end(15)
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Create header box with title
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(True)

        # Create title box with icon and label
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Add display icon
        display_icon = Gtk.Image.new_from_icon_name(
            "video-display-symbolic", Gtk.IconSize.DIALOG
        )
        title_box.pack_start(display_icon, False, False, 0)

        # Add title
        display_label = Gtk.Label()
        display_label.set_markup(
            "<span weight='bold' size='large'>Display Settings</span>"
        )
        display_label.set_halign(Gtk.Align.START)
        title_box.pack_start(display_label, False, False, 0)

        header_box.pack_start(title_box, True, True, 0)

        self.pack_start(header_box, False, False, 0)

        # Create scrollable content
        scroll_window = Gtk.ScrolledWindow()
        scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_window.set_vexpand(True)

        # Create main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        # Brightness section
        brightness_label = Gtk.Label()
        brightness_label.set_markup("<b>Screen Brightness</b>")
        brightness_label.set_halign(Gtk.Align.START)
        content_box.pack_start(brightness_label, False, True, 0)

        # Brightness control
        brightness_frame = Gtk.Frame()
        brightness_frame.set_shadow_type(Gtk.ShadowType.IN)
        brightness_frame.set_margin_top(5)
        brightness_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        brightness_box.set_margin_start(10)
        brightness_box.set_margin_end(10)
        brightness_box.set_margin_top(10)
        brightness_box.set_margin_bottom(10)

        # Brightness scale
        self.brightness_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.brightness_scale.set_value(get_brightness(self.logging))
        self.brightness_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.brightness_scale.connect("value-changed", self.on_brightness_changed)
        brightness_box.pack_start(self.brightness_scale, True, True, 0)

        # Quick brightness buttons
        brightness_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        for value in [0, 25, 50, 75, 100]:
            button = Gtk.Button(label=f"{value}%")
            button.connect("clicked", self.on_brightness_button_clicked, value)
            brightness_buttons.pack_start(button, True, True, 0)

        brightness_box.pack_start(brightness_buttons, False, False, 0)
        brightness_frame.add(brightness_box)
        content_box.pack_start(brightness_frame, False, True, 0)

        # Blue light section
        bluelight_label = Gtk.Label()
        bluelight_label.set_markup("<b>Blue Light</b>")
        bluelight_label.set_halign(Gtk.Align.START)
        bluelight_label.set_margin_top(15)
        content_box.pack_start(bluelight_label, False, True, 0)

        # Blue light control
        bluelight_frame = Gtk.Frame()
        bluelight_frame.set_shadow_type(Gtk.ShadowType.IN)
        bluelight_frame.set_margin_top(5)
        bluelight_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        bluelight_box.set_margin_start(10)
        bluelight_box.set_margin_end(10)
        bluelight_box.set_margin_top(10)
        bluelight_box.set_margin_bottom(10)

        # Blue light scale
        self.bluelight_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        settings = load_settings(self.logging)
        saved_gamma = settings.get("gamma", 6500)
        # Convert temperature to percentage
        percentage = (saved_gamma - 2500) / 40  # (6500-2500)/100 = 40
        self.bluelight_scale.set_value(percentage)
        self.bluelight_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.bluelight_scale.connect("value-changed", self.on_bluelight_changed)
        bluelight_box.pack_start(self.bluelight_scale, True, True, 0)

        # Quick blue light buttons
        bluelight_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        # Map percentage to temperature values
        for value in [0, 25, 50, 75, 100]:
            button = Gtk.Button(label=f"{value}%")
            button.connect("clicked", self.on_bluelight_button_clicked, value)
            bluelight_buttons.pack_start(button, True, True, 0)

        bluelight_box.pack_start(bluelight_buttons, False, False, 0)
        bluelight_frame.add(bluelight_box)
        content_box.pack_start(bluelight_frame, False, True, 0)

        scroll_window.add(content_box)
        self.pack_start(scroll_window, True, True, 0)
        
        # Connect destroy signal to cleanup
        self.connect("destroy", self.on_destroy)
        
        # Start auto-refresh immediately
        self.start_auto_update()

    def on_brightness_changed(self, scale):
        """Handle brightness scale changes"""
        value = int(scale.get_value())
        set_brightness(value, self.logging)

    def on_brightness_button_clicked(self, button, value):
        """Handle brightness button clicks"""
        self.brightness_scale.set_value(value)
        set_brightness(value, self.logging)

    def set_bluelight(self, temperature):
        """Set blue light level"""
        temperature = int(temperature)
        settings = load_settings(self.logging)
        settings["gamma"] = temperature
        save_settings(settings, self.logging)

        # Kill any existing gammastep process
        subprocess.run(
            ["pkill", "-f", "gammastep"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Start new gammastep process with new temperature
        subprocess.Popen(
            ["gammastep", "-O", str(temperature)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def on_bluelight_changed(self, scale):
        """Handle blue light scale changes"""
        percentage = int(scale.get_value())
        temperature = int(2500 + (percentage * 40))
        self.set_bluelight(temperature)

    def on_bluelight_button_clicked(self, button, value):
        """Handle blue light button clicks"""
        self.bluelight_scale.set_value(value)
        # Convert percentage to temperature
        temperature = int(2500 + (value * 40))
        self.set_bluelight(temperature)

    def refresh_display_settings(self, *args):
        """Refresh display settings"""
        self.logging.log(LogLevel.Info, "Refreshing display settings")

        # Block the value-changed signal before updating the brightness slider
        self.brightness_scale.disconnect_by_func(self.on_brightness_changed)

        # Update brightness slider with current value
        current_brightness = get_brightness(self.logging)
        self.brightness_scale.set_value(current_brightness)

        # Reconnect the value-changed signal
        self.brightness_scale.connect("value-changed", self.on_brightness_changed)

        # Reload settings from file
        settings = load_settings(self.logging)
        saved_gamma = settings.get("gamma", 6500)
        # Convert temperature to percentage (non-inverted: 2500K = 0%, 6500K = 100%)
        percentage = (saved_gamma - 2500) / 40  # (6500-2500)/100 = 40
        self.bluelight_scale.set_value(percentage)

        # Return True to keep the timer running if this was called by the timer
        return True
    
    def start_auto_update(self):
        """Start auto-updating display settings"""
        if self.update_timeout_id is None:
            self.update_timeout_id = GLib.timeout_add(
                self.update_interval, self.refresh_display_settings
            )
            self.logging.log(LogLevel.Info, f"Auto-update started with {self.update_interval}ms interval")
    
    def stop_auto_update(self):
        """Stop auto-updating display settings"""
        if self.update_timeout_id is not None:
            GLib.source_remove(self.update_timeout_id)
            self.update_timeout_id = None
            self.logging.log(LogLevel.Info, "Auto-update stopped")
    
    def on_destroy(self, widget):
        """Clean up resources when widget is destroyed"""
        self.stop_auto_update()
