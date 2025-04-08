#!/usr/bin/env python3

import logging
import traceback
import gi  # type: ignore
import threading
import sys

from tools.bluetooth import BluetoothManager
from utils.arg_parser import ArgParse

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk  # type: ignore

from ui.tabs.autostart_tab import AutostartTab
from ui.tabs.battery_tab import BatteryTab
from ui.tabs.bluetooth_tab import BluetoothTab
from ui.tabs.display_tab import DisplayTab
from ui.tabs.power_tab import PowerTab
from ui.tabs.volume_tab import VolumeTab
from ui.tabs.wifi_tab import WiFiTab
from ui.tabs.settings_tab import SettingsTab
from ui.tabs.usbguard_tab import USBGuardTab
from utils.settings import load_settings, save_settings
from utils.logger import LogLevel, Logger
from ui.css.animations import load_animations_css  # animate_widget_show not used
from utils.translations import Translation, get_translations
from tools.globals import check_hardware_support


class BetterControl(Gtk.Window):

    def __init__(self, txt: Translation, arg_parser: ArgParse, logging: Logger) -> None:
        # Initialize thread lock before anything else
        self._tab_creation_lock = threading.RLock()

        # Initialize GTK window
        super().__init__(title="Better Control")

        self.logging = logging
        self.set_default_size(600, 400)
        self.logging.log(LogLevel.Info, "Initializing application")

        # Initialize important instance variables to prevent segfaults
        self.tabs = {}
        self.tab_pages = {}
        self.tabs_thread_running = False

        # Check if minimal mode is enabled
        self.minimal_mode = arg_parser.find_arg(("-m", "--minimal"))
        if self.minimal_mode:
            self.logging.log(LogLevel.Info, "Minimal mode enabled")

        # Apply custom CSS to remove button focus/selection outline
        css_provider = Gtk.CssProvider()
        css = b"""
            button {
                outline: none;
                -gtk-outline-radius: 0;
                border: none;
            }
            button:focus, button:hover, button:active {
                outline: none;
                box-shadow: none;
                border: none;
            }
            notebook tab {
                outline: none;
            }
            notebook tab:focus {
                outline: none;
            }
            /* Make selections invisible */
            selection {
                background-color: transparent;
                color: inherit;
            }
            *:selected {
                background-color: transparent;
                color: inherit;
            }
            textview text selection {
                background-color: transparent;
            }
            entry selection {
                background-color: transparent;
            }
            label selection {
                background-color: transparent;
            }
            treeview:selected {
                background-color: transparent;
            }
            menuitem:selected {
                background-color: transparent;
            }
            listbox row:selected {
                background-color: transparent;
            }
        """
        css_provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Load animations CSS
        self.animations_css_provider = load_animations_css()

        # Load settings and ensure we have the latest language setting
        self.settings = load_settings(logging)
        lang = self.settings.get("language", "en")
        self.logging.log(LogLevel.Info, f"Main window loaded language setting: {lang}")
        self.txt = get_translations(logging, lang)
        self.logging.log(LogLevel.Info, "Settings loaded")

        self.notebook = Gtk.Notebook()
        self.add(self.notebook)

        # Show the window as early as possible for faster perceived startup
        self.show_all()

        # Hide tab bar in minimal mode
        if self.minimal_mode:
            self.notebook.set_show_tabs(False)

        # Connect key-press-event to disable tab selection with Tab key
        self.notebook.connect("key-press-event", self.on_notebook_key_press)
        # Also connect key-press-event to the main window to catch all tab presses
        self.connect("key-press-event", self.on_key_press)

        # Initialize tabs and tab_pages earlier to avoid race conditions
        # These were previously initialized here but moved up to prevent segfaults

        # Skip loading spinner entirely for faster startup
        self.loading_page = -1  # No loading page used anymore

        # Store arg_parser before creating tabs
        self.arg_parser = arg_parser

        self.create_lazy_tabs()
        self.create_settings_button()

        self.connect("destroy", self.on_destroy)
        self.notebook.connect("switch-page", self.on_tab_switched)

    def create_lazy_tabs(self):
        """Create only the initial tab, defer others until selected"""
        self.logging.log(LogLevel.Info, "Initializing lazy tab loading")

        # Map tab names to classes
        self.tab_classes = {
            "Volume": VolumeTab,
            "Wi-Fi": WiFiTab,
            "Bluetooth": BluetoothTab,
            "Battery": BatteryTab,
            "Display": DisplayTab,
            "Power": PowerTab,
            "Autostart": AutostartTab,
            "USBGuard": USBGuardTab,
        }

        # Map tab names to translated labels
        self.tab_name_mapping = {
            "Volume": self.txt.msg_tab_volume,
            "Wi-Fi": self.txt.msg_tab_wifi,
            "Bluetooth": self.txt.msg_tab_bluetooth,
            "Battery": self.txt.msg_tab_battery,
            "Display": self.txt.msg_tab_display,
            "Power": self.txt.msg_tab_power,
            "Autostart": self.txt.msg_tab_autostart,
            "USBGuard": self.txt.msg_tab_usbguard,
        }

        # Initialize tabs dict
        self.tabs = {}
        self.tab_pages = {}

        # Define tab order from user settings or default
        tab_order = self.settings.get("tab_order", ["Volume", "Wi-Fi", "Bluetooth", "Battery", "Display", "Power", "Autostart", "USBGuard"])

        # Default initial tab to first in saved tab order
        requested_tab = tab_order[0] if tab_order else "Volume"

        # Override with command-line args if specified
        if self.arg_parser.find_arg(("-V", "--volume")) or self.arg_parser.find_arg(("-v", "")):
            requested_tab = "Volume"
        elif self.arg_parser.find_arg(("-w", "--wifi")):
            requested_tab = "Wi-Fi"
        elif self.arg_parser.find_arg(("-a", "--autostart")):
            requested_tab = "Autostart"
        elif self.arg_parser.find_arg(("-b", "--bluetooth")):
            requested_tab = "Bluetooth"
        elif self.arg_parser.find_arg(("-B", "--battery")):
            requested_tab = "Battery"
        elif self.arg_parser.find_arg(("-d", "--display")):
            requested_tab = "Display"
        elif self.arg_parser.find_arg(("-p", "--power")):
            requested_tab = "Power"
        elif self.arg_parser.find_arg(("-u", "--usbguard")):
            requested_tab = "USBGuard"

        # Load saved tab visibility settings
        visibility = self.settings.get("visibility", {})

        # Create placeholders or tabs respecting visibility
        for idx, tab_name in enumerate(tab_order):
            if not visibility.get(tab_name, True):
                # Skip hidden tabs
                continue

            if tab_name == requested_tab:
                # Create requested tab immediately
                try:
                    tab_instance = self.tab_classes[tab_name](self.logging, self.txt)
                    tab_instance.show_all()
                    page_num = self.notebook.append_page(
                        tab_instance,
                        self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name))
                    )
                    self.tabs[tab_name] = tab_instance
                    self.tab_pages[tab_name] = page_num
                    self.notebook.set_current_page(page_num)
                    self.logging.log(LogLevel.Info, f"Created initial tab: {tab_name}")
                except Exception as e:
                    self.logging.log(LogLevel.Error, f"Failed to create initial tab {tab_name}: {e}")
            else:
                # Insert empty placeholder
                placeholder = Gtk.Box()
                placeholder.show_all()
                page_num = self.notebook.append_page(
                    placeholder,
                    self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name))
                )
                self.tabs[tab_name] = placeholder  # Track placeholder widget
                self.tab_pages[tab_name] = page_num

        # Connect switch-page to lazy load other tabs
        self.notebook.connect("switch-page", self.lazy_load_tab)

        # Show all widgets
        self.show_all()

    def lazy_load_tab(self, notebook, page, page_num):
        """Instantiate tab on first switch if not yet created"""
        # Determine tab name by page_num
        tab_name = None
        for name, num in self.tab_pages.items():
            if num == page_num:
                tab_name = name
                break
        if not tab_name:
            return

        # If already created, do nothing
        if self.tabs.get(tab_name):
            return

        # Defer real tab creation to avoid segfault during switch-page
        def replace_placeholder():
            try:
                tab_class = self.tab_classes.get(tab_name)
                if not tab_class:
                    return False
                tab_instance = tab_class(self.logging, self.txt)
                tab_instance.show_all()
                self.notebook.remove_page(page_num)
                new_page_num = self.notebook.insert_page(
                    tab_instance,
                    self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name)),
                    page_num
                )
                self.tabs[tab_name] = tab_instance
                self.tab_pages[tab_name] = new_page_num
                self.logging.log(LogLevel.Info, f"Lazily created tab: {tab_name}")
                self.show_all()
                # Activate the newly created tab immediately
                self.notebook.set_current_page(new_page_num)
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Failed to lazily create tab {tab_name}: {e}")
            return False  # Only run once

        GLib.idle_add(replace_placeholder)

    def _add_tab_to_ui(self, tab_name, tab):
        """Add a tab to the UI (called from main thread)"""
        # Store the tab
        self.tabs[tab_name] = tab

        # Special handling for the Power tab to ensure keybinds work
        if tab_name == "Power":
            # Ensure keybinds will work by connecting directly to the window
            self.connect("key-press-event", tab.on_key_press)
            # Make sure the is_visible flag is set correctly based on current view
            tab.is_visible = self.minimal_mode

        # Make sure tab is visible
        tab.show_all()

        # Add animation class to the tab
        tab.get_style_context().add_class("fade-in")

        tab.set_margin_start(12)
        tab.set_margin_end(12)
        tab.set_margin_top(6)
        tab.set_margin_bottom(6)

        # Remove animation class after animation completes
        def remove_animation_class():
            if tab and not tab.get_parent() is None:
                tab.get_style_context().remove_class("fade-in")
            return False

        # Schedule class removal after animation duration
        GLib.timeout_add(350, remove_animation_class)

        # Check visibility settings
        visibility = self.settings.get("visibility", {})
        should_show = True if self.minimal_mode else visibility.get(tab_name, True)

        if should_show:
            # Add tab to notebook with proper label
            page_num = self.notebook.append_page(
                tab,
                self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name))
            )
            self.tab_pages[tab_name] = page_num
            
            # Apply consistent padding to tab content
            content = self.notebook.get_nth_page(page_num)
            if content:
                content.set_margin_start(10)
                content.set_margin_end(10)
                content.set_margin_top(0)
                content.set_margin_bottom(0)

        self.logging.log(LogLevel.Info, f"Created {tab_name} tab")
        return False  # Required for GLib.idle_add

    def _create_fallback_tab(self):
        """Create a fallback tab if thread creation fails"""
        try:
            self.logging.log(LogLevel.Info, "Creating fallback tab")
            # Create a simple label
            label = Gtk.Label(label="Failed to load tabs. Please restart the application.")
            label.set_margin_top(20)
            label.set_margin_bottom(20)
            label.set_margin_start(20)
            label.set_margin_end(20)

            # Add it to the notebook
            self.notebook.append_page(label, Gtk.Label(label="Error"))
            self.notebook.show_all()
            self.logging.log(LogLevel.Info, "Fallback tab created")
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to create fallback tab: {e}")

    def _finish_tab_loading(self):
        """Finish tab loading by applying visibility and order (on main thread)"""
        try:
            # Handle minimal mode differently for faster loading
            if self.minimal_mode:
                self.logging.log(LogLevel.Info, "Minimal mode: Finalizing UI with single tab")

                # In minimal mode, we only need to set the active tab
                # and remove the loading page
                active_tab = None

                # Find the tab we loaded
                if len(self.tab_pages) == 1:
                    # We only have one tab, so use it
                    tab_name = list(self.tab_pages.keys())[0]
                    page_num = list(self.tab_pages.values())[0]
                    self.notebook.set_current_page(page_num)
                    active_tab = tab_name

                    # Set the window title
                    translated_tab_name = self.tab_name_mapping.get(tab_name, tab_name) if hasattr(self, 'tab_name_mapping') else tab_name
                    self.set_title(f"Better Control - {translated_tab_name}")

                    # Show all to ensure content is visible
                    self.show_all()
            else:
                # Normal mode: Apply tab order and visibility
                self.logging.log(LogLevel.Info, "All tabs created, finalizing UI")

                # Ensure all tabs are present in the tab_order setting
                tab_order = self.settings.get("tab_order", ["Volume", "Wi-Fi", "Bluetooth", "Battery", "Display", "Power", "Autostart", "USBGuard"])

                # Make sure all created tabs are in the tab_order
                for tab_name in self.tabs.keys():
                    if tab_name not in tab_order:
                        # If we're adding Power for the first time, put it before Autostart
                        if tab_name == "Power":
                            # Find the position of Autostart
                            if "Autostart" in tab_order:
                                autostart_index = tab_order.index("Autostart")
                                tab_order.insert(autostart_index, tab_name)
                            else:
                                tab_order.append(tab_name)
                        # If we're adding Autostart for the first time, put it at the end
                        elif tab_name == "Autostart":
                            tab_order.append(tab_name)
                        else:
                            tab_order.append(tab_name)

                # Update the settings with the complete tab list
                self.settings["tab_order"] = tab_order

                # Apply tab order (visibility is already applied)
                try:
                    self.apply_tab_order()
                except Exception as e:
                    self.logging.log(LogLevel.Error, f"Error applying tab order: {e}")

                # Show all tabs to ensure content is visible
                self.show_all()

                # Log tab page numbers for debugging
                self.logging.log(
                    LogLevel.Debug, f"Tab pages: {self.tab_pages}"
                )

                # Initialize the active tab
                active_tab = None

            # Set active tab based on command line arguments
            if (self.arg_parser.find_arg(("-V", "--volume")) or self.arg_parser.find_arg(("-v", ""))) and "Volume" in self.tab_pages:
                page_num = self.tab_pages["Volume"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Volume (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Volume"
                if self.minimal_mode:
                    self.set_title(f"Better Control - Volume")
            elif self.arg_parser.find_arg(("-w", "--wifi")) and "Wi-Fi" in self.tab_pages:
                page_num = self.tab_pages["Wi-Fi"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Wi-Fi (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Wi-Fi"
                if self.minimal_mode:
                    self.set_title(f"Better Control - Wi-Fi")
            elif (
                self.arg_parser.find_arg(("-a", "--autostart"))
                and "Autostart" in self.tab_pages
            ):
                page_num = self.tab_pages["Autostart"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Autostart (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Autostart"
                if self.minimal_mode:
                    translated_tab_name = self.tab_name_mapping.get("Autostart", "Autostart") if hasattr(self, 'tab_name_mapping') else "Autostart"
                    self.set_title(f"Better Control - {translated_tab_name}")
            elif (
                self.arg_parser.find_arg(("-b", "--bluetooth"))
                and "Bluetooth" in self.tab_pages
            ):
                page_num = self.tab_pages["Bluetooth"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Bluetooth (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Bluetooth"
                if self.minimal_mode:
                    translated_tab_name = self.tab_name_mapping.get("Bluetooth", "Bluetooth") if hasattr(self, 'tab_name_mapping') else "Bluetooth"
                    self.set_title(f"Better Control - {translated_tab_name}")
            elif (
                self.arg_parser.find_arg(("-B", "--battery"))
                and "Battery" in self.tab_pages
            ):
                page_num = self.tab_pages["Battery"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Battery (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Battery"
                if self.minimal_mode:
                    translated_tab_name = self.tab_name_mapping.get("Battery", "Battery") if hasattr(self, 'tab_name_mapping') else "Battery"
                    self.set_title(f"Better Control - {translated_tab_name}")
            elif (
                self.arg_parser.find_arg(("-d", "--display"))
                and "Display" in self.tab_pages
            ):
                page_num = self.tab_pages["Display"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Display (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Display"
                if self.minimal_mode:
                    translated_tab_name = self.tab_name_mapping.get("Display", "Display") if hasattr(self, 'tab_name_mapping') else "Display"
                    self.set_title(f"Better Control - {translated_tab_name}")
            elif (
                self.arg_parser.find_arg(("-u", "--usbguard"))
                and "USBGuard" in self.tab_pages
            ):
                page_num = self.tab_pages["USBGuard"]
                self.logging.log(LogLevel.Info, f"Setting active tab to USBGuard (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "USBGuard"
                if self.minimal_mode:
                    translated_tab_name = self.tab_name_mapping.get("USBGuard", "USBGuard") if hasattr(self, 'tab_name_mapping') else "USBGuard"
                    self.set_title(f"Better Control - {translated_tab_name}")
            elif (
                self.arg_parser.find_arg(("-p", "--power"))
                and "Power" in self.tab_pages
            ):
                page_num = self.tab_pages["Power"]
                self.logging.log(LogLevel.Info, f"Setting active tab to Power (page {page_num})")
                self.notebook.set_current_page(page_num)
                active_tab = "Power"
                if self.minimal_mode:
                    translated_tab_name = self.tab_name_mapping.get("Power", "Power") if hasattr(self, 'tab_name_mapping') else "Power"
                    self.set_title(f"Better Control - {translated_tab_name}")
            else:
                # Default to first tab instead of using last active tab from settings
                if self.notebook.get_n_pages() > 0:
                    self.notebook.set_current_page(0)
                    # Find which tab is at this position
                    for tab_name, tab_page in self.tab_pages.items():
                        if tab_page == 0:
                            active_tab = tab_name
                            if self.minimal_mode:
                                translated_tab_name = self.tab_name_mapping.get(tab_name, tab_name) if hasattr(self, 'tab_name_mapping') else tab_name
                                self.set_title(f"Better Control - {translated_tab_name}")
                            break

            # Set visibility status on the active tab
            if active_tab == "Wi-Fi" and active_tab in self.tabs:
                self.tabs[active_tab].tab_visible = True

            # Load WiFi networks if WiFi tab is active
            if "Wi-Fi" in self.tabs and active_tab == "Wi-Fi":
                try:
                    self.tabs["Wi-Fi"].load_networks()
                except Exception as e:
                    self.logging.log(LogLevel.Error, f"Error loading WiFi networks: {e}")

            # Remove loading tab with proper error handling
            try:
                # Only try to remove the loading page if it exists (not in minimal mode)
                if self.loading_page >= 0 and self.loading_page < self.notebook.get_n_pages():
                    self.notebook.remove_page(self.loading_page)
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Error removing loading page: {e}")

            # Connect page switch signal to handle tab visibility
            self.notebook.connect("switch-page", self.on_tab_switched)

            # Store strong references to prevent GC issues
            self._keep_refs = True  # Flag to indicate we're keeping references

            self.logging.log(LogLevel.Info, "Tab loading finished successfully")
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Critical error finalizing UI: {e}")
            import traceback
            traceback.print_exc()

        return False  # Required for GLib.idle_add

    def unhide_tab(self, tab_name):
        """Unhide a previously hidden tab"""
        # First check if tab exists in our tabs dictionary
        if tab_name not in self.tabs:
            # Tab doesn't exist???, well then create it
            try:
                tab_classes = {
                    "Bluetooth": BluetoothTab,
                    "Volume": VolumeTab,
                    "Wi-Fi": WiFiTab,
                    "Battery": BatteryTab,
                    "Display": DisplayTab,
                    "Power": PowerTab,
                    "Autostart": AutostartTab,
                    "USBGuard": USBGuardTab
                }
                
                if tab_name in tab_classes:
                    self.logging.log(LogLevel.Info, f"Creating missing tab: {tab_name}")
                    tab = tab_classes[tab_name](self.logging, self.txt)
                    self.tabs[tab_name] = tab
                    
                    # Special handling for Power tab , why? cuz its special
                    if tab_name == "Power":
                        self.connect("key-press-event", tab.on_key_press)
                        tab.is_visible = self.minimal_mode
                else:
                    self.logging.log(LogLevel.Warn, f"Cannot unhide non-existent tab: {tab_name}")
                    return
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Failed to create tab {tab_name}: {e}")
                return

        # Update visibility setting and ensure it persists
        if "visibility" not in self.settings:
            self.settings["visibility"] = {}
        self.settings["visibility"][tab_name] = True
        
        # Special handling for Bluetooth tab to ensure persistence
        if tab_name == "Bluetooth":
            self.settings["bluetooth_visible"] = True
            
        save_settings(self.settings, self.logging)

        # Apply the change
        try:
            self.apply_tab_visibility_with_order(tab_name)
            
            # Special handling for WiFi tab to load networks
            if tab_name == "Wi-Fi" and hasattr(self.tabs[tab_name], 'load_networks'):
                self.tabs[tab_name].load_networks()
                
            # Ensure tab is properly shown and stays visible
            if tab_name in self.tab_pages:
                page_num = self.tab_pages[tab_name]
                self.notebook.set_current_page(page_num)
                
                # For Bluetooth tab, ensure it remains visible
                if tab_name == "Bluetooth":
                    self.tabs[tab_name].set_visible(True)
                    self.tabs[tab_name].show_all()
                
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Error applying visibility for {tab_name}: {e}")

    def apply_tab_visibility(self):
        """Apply tab visibility settings"""
        self.apply_tab_visibility_with_order()

    def apply_tab_visibility_with_order(self, newly_unhidden_tab=None):
        """Apply tab visibility settings with optional tab ordering"""
        visibility = self.settings.get("visibility", {})
        tab_order = self.settings.get("tab_order", [])
        
        # Iterate through all tabs
        for tab_name, tab in self.tabs.items():
            # Default to showing tab if no setting exists
            should_show = visibility.get(tab_name, True)
            # Get the current position if it exists
            page_num = -1
            for i in range(self.notebook.get_n_pages()):
                if self.notebook.get_nth_page(i) == tab:
                    page_num = i
                    break
            
            # Apply visibility
            if should_show and page_num == -1:
                # Need to add the tab
                tab.show_all()  # Ensure tab is visible
                page_num = self.notebook.append_page(
                    tab,
                    self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name)),
                )
                self.tab_pages[tab_name] = page_num
                
                # If this is a newly unhidden tab, reorder it properly
                if tab_name == newly_unhidden_tab and tab_name in tab_order:
                    target_pos = tab_order.index(tab_name)
                    # Count only visible tabs before this one
                    visible_count = 0
                    for t in tab_order[:target_pos]:
                        if t in self.tabs and visibility.get(t, True):
                            visible_count += 1
                    if page_num != visible_count:
                        self.notebook.reorder_child(tab, visible_count)
                        # Update page numbers
                        self.tab_pages[tab_name] = visible_count
                        for name, num in self.tab_pages.items():
                            if name != tab_name and num >= visible_count and num < page_num:
                                self.tab_pages[name] = num + 1
                
                self.notebook.show_all()  # Ensure notebook updates
            elif not should_show and page_num != -1:
                # Need to remove the tab
                self.notebook.remove_page(page_num)
                # Update page numbers for tabs after this one
                for name, num in self.tab_pages.items():
                    if num > page_num:
                        self.tab_pages[name] = num - 1
                # Remove from tab_pages
                if tab_name in self.tab_pages:
                    del self.tab_pages[tab_name]

    def apply_tab_order(self):
        """Apply tab order settings"""
        # Get current tab order from settings or use default
        tab_order = self.settings.get(
            "tab_order", ["Volume", "Wi-Fi", "Bluetooth", "Battery", "Display", "Power", "Autostart", "USBGuard"]
        )

        # Make sure all tabs are present in the tab_order
        for tab_name in self.tabs.keys():
            if tab_name not in tab_order:
                if tab_name == "Autostart":
                    # Find the position of USBGuard
                    if "USBGuard" in tab_order:
                        autostart_index = tab_order.index("USBGuard")
                        tab_order.insert(autostart_index, tab_name)
                    else:
                        tab_order.append(tab_name)
                elif tab_name == "USBGuard":
                    tab_order.append(tab_name)
                else:
                    tab_order.append(tab_name)

        # Update the settings with the modified order
        self.settings["tab_order"] = tab_order

        # Log the desired tab order
        self.logging.log(LogLevel.Debug, f"Applying tab order: {tab_order}")

        # Clear the tab_pages mapping
        self.tab_pages = {}

        # Remove all tabs from the notebook while preserving them
        tab_widgets = {}
        for tab_name, tab in self.tabs.items():
            for i in range(self.notebook.get_n_pages()):
                if self.notebook.get_nth_page(i) == tab:
                    self.notebook.remove_page(i)
                    tab_widgets[tab_name] = tab
                    break

        # Re-add tabs in the correct order
        for i, tab_name in enumerate(tab_order):
            if tab_name in self.tabs and tab_name in tab_widgets:
                # Add tab to notebook with proper label
                page_num = self.notebook.append_page(
                    self.tabs[tab_name],
                    self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name))
                )
                self.tab_pages[tab_name] = page_num
                self.logging.log(LogLevel.Debug, f"Tab {tab_name} added at position {page_num}")

        # Show all tabs
        self.notebook.show_all()

    def get_icon_for_tab(self, tab_name):
        """Get icon name for a tab"""
        icons = {
            "Volume": "audio-volume-high-symbolic",
            "Wi-Fi": "network-wireless-symbolic",
            "Bluetooth": "bluetooth-symbolic",
            "Battery": "battery-good-symbolic",
            "Display": "video-display-symbolic",
            "Settings": "preferences-system-symbolic",
            "Power": "system-shutdown-symbolic",
            "Autostart": "system-run-symbolic",
            "USBGuard": "drive-removable-media-symbolic",
        }
        return icons.get(tab_name, "application-x-executable-symbolic")

    def create_settings_button(self):
        """Create settings button in the notebook action area"""
        # Don't show settings button in minimal mode
        if self.minimal_mode:
            self.logging.log(LogLevel.Info, "Settings button not created in minimal mode")
            return

        settings_button = Gtk.Button()
        self.settings_icon = Gtk.Image.new_from_icon_name(
            "preferences-system-symbolic", Gtk.IconSize.BUTTON
        )
        settings_button.set_image(self.settings_icon)
        self.settings_icon.get_style_context().add_class("rotate-gear")
        settings_button.set_tooltip_text(self.txt.settings_title)

        # Connect the clicked signal
        settings_button.connect("clicked", self.toggle_settings_panel)

        # Add to the notebook action area
        self.notebook.set_action_widget(settings_button, Gtk.PackType.END)
        settings_button.show_all()

        self.logging.log(
            LogLevel.Info, "Settings button created and attached to notebook"
        )

    def toggle_settings_panel(self, widget):
        self.logging.log(
            LogLevel.Info, "Settings button clicked, opening settings dialog"
        )
        self.settings_icon.get_style_context().add_class("rotate-gear-active")
        self.settings_icon.get_style_context().remove_class("rotate-gear")

        try:
            dialog = Gtk.Dialog(
                title=self.txt.settings_title,
                parent=self,
                flags=Gtk.DialogFlags.MODAL,
                buttons=(self.txt.close, Gtk.ResponseType.CLOSE),
            )
            dialog.set_default_size(600, 540)
            dialog.set_size_request(600, 540)
            dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
            # Create a fresh instance of the settings tab to use in the dialog
            settings_tab = SettingsTab(self.logging, self.txt)
            settings_tab.connect(
                "tab-visibility-changed", self.on_tab_visibility_changed
            )
            settings_tab.connect("tab-order-changed", self.on_tab_order_changed)
            # Add the settings content to the dialog's content area
            content_area = dialog.get_content_area()
            content_area.add(settings_tab)
            content_area.set_border_width(10)

            # Add animation class to settings tab
            settings_tab.get_style_context().add_class("fade-in")

            # Show the dialog and all its contents
            dialog.show_all()

            # Run the dialog
            response = dialog.run()

            if response == Gtk.ResponseType.CLOSE:
                self.logging.log(LogLevel.Info, "Settings dialog closed")

            # Clean up the dialog
            dialog.destroy()
            self.settings_icon.get_style_context().remove_class("rotate-gear-active")
            self.settings_icon.get_style_context().add_class("rotate-gear")

        except Exception as e:
            self.logging.log(LogLevel.Error, f"Error in toggle_settings_panel: {e}")
            traceback.print_exc()

    def on_tab_visibility_changed(self, widget, tab_name, visible):
        """Handle tab visibility changed signal from settings tab"""
        if visible:
            self.unhide_tab(tab_name)
        else:
            # Update settings
            if "visibility" not in self.settings:
                self.settings["visibility"] = {}
            self.settings["visibility"][tab_name] = False
            save_settings(self.settings, self.logging)

            # Remove tab or placeholder immediately if it exists
            if tab_name in self.tabs:
                tab_widget = self.tabs[tab_name]
                if tab_widget is not None:
                    page_num = -1
                    # Find current page number
                    for i in range(self.notebook.get_n_pages()):
                        if self.notebook.get_nth_page(i) == tab_widget:
                            page_num = i
                            break

                    if page_num != -1:
                        self.notebook.remove_page(page_num)
                        # Update tab_pages mapping
                        for name, num in list(self.tab_pages.items()):
                            if num > page_num:
                                self.tab_pages[name] = num - 1
                        if tab_name in self.tab_pages:
                            del self.tab_pages[tab_name]

    def on_tab_order_changed(self, widget, tab_order):
        """Handle tab order changed signal from settings tab"""
        self.settings["tab_order"] = tab_order
        save_settings(self.settings, self.logging)
        self.apply_tab_order()

    def create_tab_label(self, text: str, icon_name: str) -> Gtk.Box:
        """Create a tab label with icon and text

        Args:
            text (str): Tab label text (internal name)
            icon_name (str): Icon name

        Returns:
            Gtk.Box: Box containing icon and label
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)

        # Use the translated tab name if available
        translated_text = self.tab_name_mapping.get(text, text) if hasattr(self, 'tab_name_mapping') else text
        label = Gtk.Label(label=translated_text)

        box.pack_start(icon, False, False, 0)
        box.pack_start(label, False, False, 0)
        box.show_all()
        return box


    def on_tab_switched(self, notebook, page, page_num):
        """Handle tab switching"""

        # Apply animation to the new tab
        current_page = notebook.get_nth_page(page_num)
        if current_page:
            # Add fade-in animation class
            current_page.get_style_context().add_class("fade-in")

            # Remove the animation class after it completes
            def remove_animation_class():
                if current_page and not current_page.get_parent() is None:
                    current_page.get_style_context().remove_class("fade-in")
                return False

            # Schedule class removal after animation duration
            GLib.timeout_add(350, remove_animation_class)

        # Update tab visibility status
        for tab_name, tab in self.tabs.items():
            # Check if this tab is at the current page number
            is_visible = self.tab_pages.get(tab_name) == page_num

            # If tab has tab_visible property (WiFi tab), update it
            if hasattr(tab, 'tab_visible'):
                tab.tab_visible = is_visible

            # Update window title in minimal mode
            if is_visible and self.minimal_mode:
                # Use translated tab name in window title
                translated_tab_name = self.tab_name_mapping.get(tab_name, tab_name) if hasattr(self, 'tab_name_mapping') else tab_name
                self.set_title(f"Better Control - {translated_tab_name}")

    def on_notebook_key_press(self, widget, event):
        """Prevent tab selection with Tab key"""
        # Get keyval from event
        keyval = event.keyval
        # Prevent Tab key (65289) and Shift+Tab (65056)
        if keyval in (65289, 65056):
            # Stop propagation of the event
            return True  # Event handled, don't propagate
        return False  # Let other handlers process the event

    def on_key_press(self, widget, event):
        """Prevent tab selection globally"""
        keyval = event.keyval
        state = event.state

        # Check if Power tab exists and handle its keys globally
        if "Power" in self.tabs:
            power_tab = self.tabs["Power"]
            from ui.tabs.power_tab import PowerTab
            if isinstance(power_tab, PowerTab):
                # Always let Power tab handle keys first, regardless of which tab is active
                if power_tab.on_key_press(widget, event):
                    return True

        # In minimal mode, we want to let the active tab handle key events first
        if self.minimal_mode:
            # Get the current page
            current_page = self.notebook.get_current_page()
            if current_page >= 0:
                # Get the widget at the current page
                child = self.notebook.get_nth_page(current_page)
                if child and hasattr(child, 'on_key_press') and child != self.tabs.get("Power"):
                    # Let the tab handle the key press first
                    self.logging.log(LogLevel.Debug, f"Forwarding key press to tab in minimal mode")
                    # If the tab handles it, don't process further
                    if child.on_key_press(widget, event):
                        return True

        if keyval in (65289, 65056):  # Tab and Shift+Tab
            return True  # Stop propagation
        # on shift + s show settings dialog
        if keyval in (115, 83) and state & Gdk.ModifierType.SHIFT_MASK and not self.minimal_mode:
            # show settings dialog
            self.toggle_settings_panel(None)
            return True
        #  ctrl + q or q will quit the application
        if keyval in (113, 81) or  (keyval == 113 and state & Gdk.ModifierType.CONTROL_MASK):
            self.logging.log(LogLevel.Info, "Application quitted")
            Gtk.main_quit()
        return False  # Let other handlers process the event

    def on_destroy(self, window):
        """Save settings and quit"""
        self.logging.log(LogLevel.Info, "Application shutting down")

        # Stop any ongoing tab creation - use lock to prevent race conditions
        if hasattr(self, '_tab_creation_lock') and hasattr(self, 'tabs_thread_running'):
            with self._tab_creation_lock:
                self.tabs_thread_running = False

        # Ensure USBGuard is in the tab_order setting before saving
        if "tab_order" in self.settings:
            tab_order = self.settings["tab_order"]
            # Make sure all known tabs are included
            all_tabs = ["Volume", "Wi-Fi", "Bluetooth", "Battery", "Display", "Power", "Autostart", "USBGuard"]
            for tab_name in all_tabs:
                if tab_name not in tab_order:
                    # If we're adding USBGuard for the first time, put it at the end
                    if tab_name == "USBGuard":
                        tab_order.append(tab_name)
                    else:
                        tab_order.append(tab_name)
            self.settings["tab_order"] = tab_order

        # Always load the latest settings from disk to ensure we have the most recent language setting
        latest_settings = load_settings(self.logging)
        if "language" in latest_settings:
            # Update our in-memory settings with the latest language setting from disk
            self.logging.log(LogLevel.Info, f"Using latest language setting from disk: {latest_settings['language']}")
            self.settings["language"] = latest_settings["language"]
        elif "language" in self.settings:
            self.logging.log(LogLevel.Info, f"Using language setting from memory: {self.settings['language']}")
        else:
            self.logging.log(LogLevel.Warn, "No language setting found in memory or on disk")

        # Signal all tabs to clean up their resources
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, 'on_destroy'):
                try:
                    tab.on_destroy(None)
                except Exception as e:
                    self.logging.log(LogLevel.Error, f"Error destroying {tab_name} tab: {e}")

        # Stop any monitoring threads
        if hasattr(self, "monitor_pulse_events_running"):
            self.monitor_pulse_events_running = False
        if hasattr(self, "load_networks_thread_running"):
            self.load_networks_thread_running = False

        # Ensure logging is set up
        if not hasattr(self, "logging") or not self.logging:
            self.logging = logging.getLogger("BetterControl")
            handler = logging.StreamHandler(sys.__stdout__)
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s", "%H:%M:%S"))
            self.logging.addHandler(handler)
            self.logging.setLevel(logging.Info)

        # Log the final settings before saving
        self.logging.log(LogLevel.Info, f"Final settings keys before saving: {list(self.settings.keys())}")
        if "language" in self.settings:
            self.logging.log(LogLevel.Info, f"Final language setting before saving: {self.settings['language']}")

        # Save settings in a separate thread to avoid blocking
        try:
            # Use a direct call to save_settings instead of a thread to ensure it completes
            self.logging.log(LogLevel.Info, "Saving settings directly to ensure completion")
            save_settings(self.settings, self.logging)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Error saving settings: {e}")

        self.logging.log(LogLevel.Info, "Application shutdown complete")

        # Close any file descriptors
        if hasattr(self.logging, "flush"):
            self.logging.flush()

        # Use try/except to avoid errors during shutdown
        try:
            sys.stdout = open('/dev/null', 'w')
            sys.stderr = open('/dev/null', 'w')
        except Exception:
            pass

        # Let GTK know we're quitting
        Gtk.main_quit()
