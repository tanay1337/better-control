<div align="center">

# ⚙️ Better Control ⚙️

<img src="https://github.com/user-attachments/assets/4ac1bfc4-6a0e-4134-83c3-1356d5a71e33" width="650">

### *A sleek GTK-themed control panel for Linux* 🐧

[![AUR Package](https://img.shields.io/aur/version/better-control-git?style=flat-square&logo=arch-linux&label=AUR&color=1793d1)](https://aur.archlinux.org/packages/better-control-git)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/quantumvoid0/better-control?style=flat-square&color=yellow)](https://github.com/quantumvoid0/better-control/stargazers)

</div>

<br>

> [!NOTE]
> 🎨 The application follows your system GTK theme for a native and integrated look.

> [!IMPORTANT]
> 🚧 This project is under active development. Contributions, feature requests, ideas, and testers are welcome!

<br>

## ✨ Features

- 🔄 Seamless integration with your desktop environment
- 📱 Modern, clean interface for system controls
- 🎚️ Quick access to common system settings
- 🌙 Respects your system's light/dark theme settings
- 🧩 Modular design - use only what you need

<br>

## 📋 Requirements

Before installing, ensure you have `git` and `base-devel` installed.

### Core Dependencies

| Dependency | Purpose |
|------------|---------|
| **GTK 3** | UI framework |
| **Python Libraries** | python-gobject, python-dbus, python-psutil |

### Feature-Specific Dependencies

| Feature | Required Packages |
|---------|------------------|
| **Wi-Fi Management** | NetworkManager, python-qrcode |
| **Bluetooth** | BlueZ & BlueZ Utils |
| **Audio Control** | PipeWire or PulseAudio |
| **Brightness** | brightnessctl |
| **Power Management** | power-profiles-daemon, upower |
| **Blue Light Filter** | gammastep |

> [!TIP]
> If you don't need a specific feature, you can safely omit its corresponding dependency and hide its tab in the settings.

<br>

### Usage

`control` or `better-control` command will run the gui application.

### Keybindings

| Keybinding | Action |
|------------|--------|
| `Shift + S` | Open Settings Dialog |
| `Q` or `Ctrl + Q` | Quit Application |


## 💾 Installation

<details>
<summary><b>🏗️ Arch-based Distributions</b></summary>

```bash
yay -S better-control-git
```
> This will directly install dependencies and the app. No further steps required.
</details>

<details>
<summary><b>❄️ Nix (Unofficial)</b></summary>

> This is an unofficial Nix flake maintained by the community. All issues should be directed to their repository:
> 
> https://github.com/Rishabh5321/better-control-flake
</details>

<details>
<summary><b>🐧 Debian-based Distributions</b></summary>

```bash
sudo apt update && sudo apt install -y libgtk-3-dev network-manager bluez bluez-utils pulseaudio brightnessctl python3-gi python3-dbus python3 power-profiles-daemon gammastep python3-requests python3-qrcode
```
</details>

<details>
<summary><b>🎩 Fedora-based Distributions</b></summary>

```bash
sudo dnf install -y gtk3 NetworkManager bluez bluez-utils pulseaudio brightnessctl python3-gobject python3-dbus python3 power-profiles-daemon gammastep python3-requests python3-qrcode
```
</details>

<details>
<summary><b>🌀 Void Linux</b></summary>

```bash
sudo xbps-install -S gtk3 NetworkManager bluez bluez-utils pulseaudio brightnessctl python3-gobject python3-dbus python3 power-profiles-daemon gammastep python3-requests python3-qrcode
```
</details>

<details>
<summary><b>🏔️ Alpine Linux</b></summary>

```bash
sudo apk add gtk3 networkmanager bluez bluez-utils pulseaudio brightnessctl py3-gobject py3-dbus python3 power-profiles-daemon gammastep py3-requests py3-qrcode
```
</details>

### Manual Installation Steps

```bash
git clone https://github.com/quantumvoid0/better-control.git
cd better-control
make
sudo make install
```

## 📚 Documentation

For more information, please refer to the [official documentation](https://github.com/quantumvoid0/better-control/wiki).

<br>

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for more details.

<br>

## 🗑️ Uninstallation

<details>
<summary><b>🏗️ Arch-based Distributions</b></summary>

```bash
yay -Rns better-control-git
```
</details>

<details>
<summary><b>📦 Other Distributions</b></summary>

```bash
git clone https://github.com/quantumvoid0/better-control
cd better-control
sudo make uninstall
```
</details>

<br>

## 🧪 Compatibility Matrix

Better-Control has been tested on Arch Linux with Hyprland, GNOME, and KDE Plasma. It should work on most Linux distributions with minor adjustments.

<table>
  <tr>
    <th align="center" width="200">Category</th>
    <th align="center">Compatibility</th>
  </tr>
  <tr>
    <td align="center"><b>Operating System</b></td>
    <td align="center">Linux</td>
  </tr>
  <tr>
    <td align="center"><b>Distributions</b></td>
    <td align="center">Arch-based ✓ • Fedora-based ✓ • Debian-based ✓ • Void ✓ • Alpine ✓</td>
  </tr>
  <tr>
    <td align="center"><b>Desktop Environments</b></td>
    <td align="center">GNOME (tested) ✓ • KDE Plasma (tested) ✓ • XFCE • LXDE/LXQT</td>
  </tr>
  <tr>
    <td align="center"><b>Window Managers</b></td>
    <td align="center">Hyprland (tested) ✓ • Sway (tested) ✓ • i3 • Openbox • Fluxbox</td>
  </tr>
  <tr>
    <td align="center"><b>Display Protocol</b></td>
    <td align="center">Wayland (recommended) ✓ • X11 (partial functionality)</td>
  </tr>
</table>

> [!NOTE]
> If you test Better-Control on a different setup, please share your experience in the discussions or issues section.

<br>

<div align="center">
  
### Made with ❤️ for the Linux community

[Report Bug](https://github.com/quantumvoid0/better-control/issues) • 
[Request Feature](https://github.com/quantumvoid0/better-control/issues) • 
[Contribute](https://github.com/quantumvoid0/better-control/pulls)

</div>
