# Push To Talk

Convenient recording of scratch dialog for an edit.

## Usage

In the `Sequencer` header click `Start Recording` to capture your microphone's audio and click again to finish.

### Configuring the Audio Input

If there is more than one microphone available, a specific one can be selected in the recording configuration panel.
On Linux, it typically starts with `sysdefault` or `usb`.

![Recoding configuration panel UI](docs/panel.png)

Note: For Audio input detection to work on linux, you need to have `arecord` available (see [Requirements](#requirements)).

## Installation

1. Download this repository as ZIP file.
2. In Blender's `Edit > Preferences > Add-ons`, click `Install` and select the ZIP.

### Updating

1. Download the newest version ZIP.
2. In Blender's `Edit > Preferences > Add-ons`, find this add-on, expand it, and click `Remove`.
3. Click `Install` and select the ZIP.

**Alternatively:** this git repository can be **cloned** to a folder on disk and that folder linked to the `scripts/addons` folder of the Blender executable. This way, the add-on and be kept up to date with `git pull` without the need to remove/install it.


### Requirements
- **`ffmpeg`**. See [instructions for Windows](https://www.geeksforgeeks.org/how-to-install-ffmpeg-on-windows/).
-  `arecord` (Linux only). On Arch you can install it via the `alsa-utils` package

### Compatibility

| Blender Version | Status |
| - | - |
| 4.0+ | Supported |
| 3.6 LTS | Supported |
| 3.3 LTS | Supported |
| 2.93 LTS and older | Unsupported |
