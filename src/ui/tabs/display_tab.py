#!/usr/bin/env python3

import gi  # type: ignore
import subprocess

from utils.logger import LogLevel, Logger
from utils.translations import Translation

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # type: ignore

from utils.settings import load_settings, save_settings
from tools.display import get_brightness, get_display_info, get_displays, rotate_display, set_brightness
from tools.hyprland import get_hyprland_displays, set_hyprland_transform, get_hyprland_rotation
from tools.globals import get_current_session
from ui.dialogs.rotation_dialog import RotationConfirmDialog

class DisplayTab(Gtk.Box):
    """Display settings tab"""

    def __init__(self, logging: Logger, txt: Translation):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.txt = txt
        self.logging = logging
        self.update_timeout_id = None
        self.update_interval = 500  # milliseconds
        self.is_visible = False
        self.session = get_current_session()
        displays = get_displays(self.logging)
        self.current_display = displays[0] if displays else None

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

        # Add display icon with hover animations
        display_icon = Gtk.Image.new_from_icon_name(
            "video-display-symbolic", Gtk.IconSize.DIALOG
        )
        ctx = display_icon.get_style_context()
        ctx.add_class("display-icon")
        
        def on_enter(widget, event):
            ctx.add_class("display-icon-animate")
        
        def on_leave(widget, event):
            ctx.remove_class("display-icon-animate")
        
        # Wrap in event box for hover detection
        icon_event_box = Gtk.EventBox()
        icon_event_box.add(display_icon)
        icon_event_box.connect("enter-notify-event", on_enter)
        icon_event_box.connect("leave-notify-event", on_leave)
        
        title_box.pack_start(icon_event_box, False, False, 0)

        # Add title
        display_label = Gtk.Label()
        display_label.set_markup(
            f"<span weight='bold' size='large'>{self.txt.display_title}</span>"
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

        # Display orientation section
        orientation_label = Gtk.Label()
        orientation_label.set_markup(f"<b>{self.txt.display_orientation}</b>")
        orientation_label.set_halign(Gtk.Align.START)
        
        # Orientation frame
        orientation_frame = Gtk.Frame()
        orientation_frame.set_shadow_type(Gtk.ShadowType.IN)
        orientation_frame.set_margin_top(5)
        orientation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        orientation_box.set_margin_start(10)
        orientation_box.set_margin_end(10)
        orientation_box.set_margin_top(10)
        orientation_box.set_margin_bottom(10)
        
        # Orientation buttons
        orientation_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        # Get displays according to current session
        displays = []
        if "Hyprland" in self.session:
            hypr_displays = get_hyprland_displays()
            displays = list(hypr_displays.keys())
        else:
            displays = get_displays(self.logging)
            
        self.current_display = displays[0] if displays else None
        
        display_combo = Gtk.ComboBoxText()
        for display in displays:
            display_combo.append_text(display)
        if self.current_display:
            display_combo.set_active(0)
        display_combo.connect("changed", self.on_display_changed)
        orientation_buttons.pack_start(display_combo, True, True, 0)
              
        orientation_box.pack_start(orientation_buttons, False, False, 0)
        
        # Rotation controls in an expander (collapsed by default)
        rotation_expander = Gtk.Expander(label=f"<b>{self.txt.display_rotation}</b>")
        rotation_expander.set_use_markup(True)
        rotation_expander.set_expanded(False)
        rotation_expander.set_margin_top(10)
        
        # Create a container for rotation controls
        rotation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        rotation_box.set_margin_top(10)
        rotation_box.pack_start(self.create_rotation_controls(), True, True, 0)
        rotation_expander.add(rotation_box)
        orientation_box.pack_start(rotation_expander, False, False, 0)
        
        orientation_frame.add(orientation_box)
        
        # Brightness section
        brightness_label = Gtk.Label()
        brightness_label.set_markup(f"<b>{self.txt.display_brightness}</b>")
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
        bluelight_label.set_markup(f"<b>{self.txt.display_blue_light}</b>")
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
        content_box.pack_start(orientation_label, False, True, 0)
        content_box.pack_start(orientation_frame, False, True, 0)

        scroll_window.add(content_box)
        self.pack_start(scroll_window, True, True, 0)

        # Connect destroy signal to cleanup
        self.connect("destroy", self.on_destroy)

        # Connect visibility signals
        self.connect("map", self.on_mapped)
        self.connect("unmap", self.on_unmapped)

        # Only start auto-refresh when the tab becomes visible
        if self.get_mapped():
            self.is_visible = True
            self.start_auto_update()
        
        self.previous_orientation = "normal"
    
    def on_display_changed(self, combo):
        self.current_display = combo.get_active_text()

    def on_rotation_clicked(self, button, rotation):
        """Handle orientation button click"""
        if self.current_display:
            
            # Get orientation if in hyprland
            if "Hyprland" in self.session:
                current_orientation = get_hyprland_rotation()
            else:
                current_orientation = self.get_current_orientation()
            
            # Skip if trying to rotate to current orientation
            if rotation.lower() == current_orientation.lower():
                self.logging.log(LogLevel.Info, f"Already in {get_hyprland_rotation()}")
                return
            
            self.previous_orientation = current_orientation
            if "Hyprland" in self.session:
                success = set_hyprland_transform(self.logging, self.current_display, rotation)
            else:
                success = rotate_display(self.current_display, "generic", rotation, self.logging)

            if success:
                # show confirmation dialog for display rotation
                dialog = RotationConfirmDialog(
                    self.get_toplevel(),
                    self.current_display,
                    self.previous_orientation, 
                    self.session,
                    self.logging
                )               
                response = dialog.run()
                dialog.destroy()
                
                if response == Gtk.ResponseType.OK:
                    self.previous_orientation = rotation

    def get_current_orientation(self) -> str:
        """Get current display orientation"""
        try:
            if "Hyprland" in self.session:
                displays = get_hyprland_displays()
                # mapped according to hyprctl display -> transform: 0 
                transform_map = {
                    0: "normal",
                    1: "right",
                    2: "inverted",
                    3: "left"
                }
                return transform_map.get(displays.get(self.current_display, 0), "normal").lower()
            else:
                info = get_display_info(self.current_display, self.logging)
                return info.get("rotation", "normal").lower()
        except:
            return "normal"

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

        # Block the value-changed signal before updating the blue light filter slider
        self.bluelight_scale.disconnect_by_func(self.on_bluelight_changed)

        # Update blue light filter slider with saved value
        self.bluelight_scale.set_value(percentage)

        # Reconnect the value-changed signal
        self.bluelight_scale.connect("value-changed", self.on_bluelight_changed)

        # Return True to keep the timer running if this was called by the timer
        return True

    def on_mapped(self, widget):
        """Called when the widget becomes visible"""
        self.is_visible = True
        self.start_auto_update()
        self.logging.log(LogLevel.Info, "Display tab became visible, starting auto-update")

    def on_unmapped(self, widget):
        """Called when the widget is hidden"""
        self.is_visible = False
        self.stop_auto_update()
        self.logging.log(LogLevel.Info, "Display tab hidden, stopping auto-update")

    def start_auto_update(self):
        """Start auto-updating display settings"""
        if self.update_timeout_id is None and self.is_visible:
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

    def create_rotation_controls(self):
        """Create rotation controls with hyprland's transform options"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # Section 1: Simple Rotations (CW/CCW)
        simple_rotation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        simple_label = Gtk.Label()
        simple_label.set_markup("<span weight='medium'>Quick Rotate</span>")
        simple_label.set_halign(Gtk.Align.START)
        simple_rotation_box.pack_start(simple_label, False, False, 0)

        simple_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        simple_buttons.set_homogeneous(True)

        # Rotate CW/CCW buttons
        rotations = [
            ("rotate-cw", "object-rotate-right-symbolic", "Rotate Clockwise"),
            ("rotate-ccw", "object-rotate-left-symbolic", "Rotate Counter-Clockwise")
        ]

        for action, icon_name, tooltip in rotations:
            button = Gtk.Button()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            box.pack_start(icon, False, False, 0)
            label = Gtk.Label(tooltip)
            box.pack_start(label, False, False, 0)
            button.add(box)
            button.set_tooltip_text(tooltip)
            button.connect("clicked", self.on_rotation_clicked, action)
            simple_buttons.pack_start(button, True, True, 0)

        simple_rotation_box.pack_start(simple_buttons, False, False, 0)
        main_box.pack_start(simple_rotation_box, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)
        separator.set_margin_bottom(6)
        main_box.pack_start(separator, False, False, 0)

        # Section 2: basic rotations (0-3)
        basic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        basic_label = Gtk.Label()
        basic_label.set_markup("<span weight='medium'>Basic Rotations</span>")
        basic_label.set_halign(Gtk.Align.START)
        basic_box.pack_start(basic_label, False, False, 0)

        basic_grid = Gtk.Grid()
        basic_grid.set_row_spacing(8)
        basic_grid.set_column_spacing(8)
        basic_grid.set_row_homogeneous(True)
        basic_grid.set_column_homogeneous(True)

        # Hyprland transforms 0-3
        rotations = [
            ("normal", "Normal (0°)", 0, 0),
            ("90°", "90° Right", 0, 1),
            ("180°", "180°", 1, 0),
            ("270°", "90° Left", 1, 1)
        ]

        for action, label, row, col in rotations:
            button = Gtk.Button(label=label)
            button.connect("clicked", self.on_rotation_clicked, action)
            basic_grid.attach(button, col, row, 1, 1)

        basic_box.pack_start(basic_grid, False, False, 0)
        main_box.pack_start(basic_box, False, False, 0)

        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator2.set_margin_top(6)
        separator2.set_margin_bottom(6)
        main_box.pack_start(separator2, False, False, 0)

        # Section 3: flip controls (4-7)
        flip_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        flip_label = Gtk.Label()
        flip_label.set_markup("<span weight='medium'>Flip Controls</span>")
        flip_label.set_halign(Gtk.Align.START)
        flip_box.pack_start(flip_label, False, False, 0)

        flip_grid = Gtk.Grid()
        flip_grid.set_row_spacing(8)
        flip_grid.set_column_spacing(8)
        flip_grid.set_row_homogeneous(True)
        flip_grid.set_column_homogeneous(True)

        # Hyprland transforms 4-7
        flips = [
            ("flip", "Flip Horizontal", 0, 0),
            ("flip-vertical", "Flip Vertical", 0, 1),
            ("flip-90°", "Flip + 90°", 1, 0),
            ("flip-270°", "Flip + 270°", 1, 1)
        ]

        for action, label, row, col in flips:
            button = Gtk.Button(label=label)
            button.connect("clicked", self.on_rotation_clicked, action)
            flip_grid.attach(button, col, row, 1, 1)

        flip_box.pack_start(flip_grid, False, False, 0)
        main_box.pack_start(flip_box, False, False, 0)

        # Add help text explaining transforms
        help_text = Gtk.Label()
        help_text.set_markup(
            "<i><small>"
            "Transform values:\n"
            "0: Normal | 1: 90° | 2: 180° | 3: 270° \n"
            "4: Flip H | 5: Flip V | 6: Flip+90° | 7: Flip+270°"
            "</small></i>"
        )
        help_text.set_margin_top(8)
        help_text.set_xalign(0)  # Align left
        help_text.set_line_wrap(True)
        main_box.pack_start(help_text, False, False, 0)

        return main_box