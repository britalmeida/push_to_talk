# Push To Talk

Convenient recording of scratch dialog in Blender's VSE.

![Screenshot showing record button and created audio strip](docs/strip_and_button.png)

## Usage

In the `Sequencer` header click `Start Recording` to capture your microphone's audio and click again to finish.

Please account for some latency in starting the recording (less than a second).

### Configuration

<img src="docs/panel.png" alt="Recoding configuration panel UI" height="121px"/>


#### Audio files
Recordings are stored as WAV files called `temp_audio_...` next to the .blend file, with options to choose another location and name scheme.

#### Microphone
If there is more than one microphone available, a specific one can be selected in the recording configuration panel.


## Installing

### Requirements
- **`ffmpeg`** (Windows and Linux). See [instructions for Windows](https://www.geeksforgeeks.org/how-to-install-ffmpeg-on-windows/).
- **`arecord`** (Linux only). It is part of the `alsa-utils` package.

Note: macOS does not have additional requirements.


### Installing as Extension

Note: this add-on is available as an extension, but is not on [extensions.blender.org](https://extensions.blender.org) since it requires dependencies.

1. Download the [latest extension release from GitHub](https://github.com/britalmeida/push_to_talk/releases).
2. `Drag&drop` the ZIP into Blender.


### Installing as Legacy Add-on

1. Download the latest extension release or the repository as ZIP file.
2. In Blender's `Edit > Preferences > Add-ons`, click `Install` and select the ZIP.

### Updating

1. Remove a previous version if installed as an add-on:  
   In Blender's `Edit > Preferences > Add-ons`, find this add-on, expand it, and click `Remove`.
2. Download and install a new version as an extension.  
   New versions of an extension can simply be installed on top without needing to manually delete the previous version.
   This add-on is still provided as "Legacy Add-on" for versions of Blender 4.1 and older.

### Compatibility

| Blender Version    | Status      |
|--------------------|-------------|
| 4.3, 4.4, 4.5      | Supported   |
| 4.2 LTS            | Supported   |
| 3.6 LTS            | Supported   |
| 3.3 LTS            | Supported   |
| 2.93 LTS and older | Unsupported |


## Development

Push to Talk was initially made for recording temp dialog for [Sprite Fright](https://studio.blender.org/projects/sprite-fright/) at Blender Studio.  
It has since gotten improvements and support for microphone recording on all platforms.
It is considered stable and with no plans for future development.  
We do address bugs and questions, the add-on is actively maintained.

Contributions and feedback are very welcome.
