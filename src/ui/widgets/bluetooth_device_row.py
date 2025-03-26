#!/usr/bin/env python3

import gi
import logging

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango

class BluetoothDeviceRow(Gtk.ListBoxRow):
    def __init__(self, device):
        super().__init__()
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(10)
        self.set_margin_end(10)

        # Store device info
        self.device_path = device['path']
        self.mac_address = device['mac']
        self.device_name = device['name']
        self.is_connected = device['connected']
        self.is_paired = device['paired']
        self.device_type = device['icon'] if device['icon'] else 'unknown'

        # Main container for the row
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add(container)

        # Device icon based on type
        device_icon = Gtk.Image.new_from_icon_name(self.get_icon_name_for_device(), Gtk.IconSize.LARGE_TOOLBAR)
        container.pack_start(device_icon, False, False, 0)

        # Left side with device name and type
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        name_label = Gtk.Label(label=self.device_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(20)
        if self.is_connected:
            name_label.set_markup(f"<b>{self.device_name}</b>")
        name_box.pack_start(name_label, True, True, 0)

        if self.is_connected:
            connected_label = Gtk.Label(label=" (Connected)")
            connected_label.get_style_context().add_class("success-label")
            name_box.pack_start(connected_label, False, False, 0)

        left_box.pack_start(name_box, False, False, 0)

        # Device details box
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        type_label = Gtk.Label(label=self.get_friendly_device_type())
        type_label.set_halign(Gtk.Align.START)
        type_label.get_style_context().add_class("dim-label")
        details_box.pack_start(type_label, False, False, 0)

        mac_label = Gtk.Label(label=self.mac_address)
        mac_label.set_halign(Gtk.Align.START)
        mac_label.get_style_context().add_class("dim-label")
        details_box.pack_start(mac_label, False, False, 10)

        left_box.pack_start(details_box, False, False, 0)

        container.pack_start(left_box, True, True, 0)

        # Add connect/disconnect buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.set_sensitive(not self.is_connected)
        button_box.pack_end(self.connect_button, False, False, 0)

        self.disconnect_button = Gtk.Button(label="Disconnect")
        self.disconnect_button.set_sensitive(self.is_connected)
        button_box.pack_end(self.disconnect_button, False, False, 0)

        container.pack_end(button_box, False, False, 0)

    def get_icon_name_for_device(self):
        """Return appropriate icon based on device type"""
        if self.device_type == "audio-headset" or self.device_type == "audio-headphones":
            return "audio-headset-symbolic"
        elif self.device_type == "audio-card":
            return "audio-speakers-symbolic"
        elif self.device_type == "input-keyboard":
            return "input-keyboard-symbolic"
        elif self.device_type == "input-mouse":
            return "input-mouse-symbolic"
        elif self.device_type == "input-gaming":
            return "input-gaming-symbolic"
        elif self.device_type == "phone":
            return "phone-symbolic"
        else:
            return "bluetooth-symbolic"

    def get_friendly_device_type(self):
        """Return user-friendly device type name"""
        type_names = {
            "audio-headset": "Headset",
            "audio-headphones": "Headphones",
            "audio-card": "Speaker",
            "input-keyboard": "Keyboard",
            "input-mouse": "Mouse",
            "input-gaming": "Game Controller",
            "phone": "Phone",
            "unknown": "Device",
        }
        return type_names.get(self.device_type, "Bluetooth Device")

    def get_mac_address(self):
        return self.mac_address

    def get_device_name(self):
        return self.device_name

    def get_is_connected(self):
        return self.is_connected