# Release Notes

A summary of noteworthy changes for each release. Made for humans. :roll_of_paper:  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Wip wip...

### Fixed
- Missing spaces in UI text.


## [0.4.0] - 2023-11-01

### Shiny and New
- Tested to work with Blender 4.0.
- Linux audio device selection shows only input devices.

### Fixed
- Video preview flashing red when starting to record.
- Audio clipping at the end of the recording. Thanks to Sebastian Parborg!


## [0.3.0] - 2023-08-07

### Shiny and New
- macOS support.
- Windows support. Thanks to tintwotin and Daniele Giuliani!
- Better handling of short recordings (~2 sec), lag issues and clipping. Thanks to Sebastian Parborg!
- Graceful error reporting in the UI for unsupported platform, missing ffmpeg or mic.
- More robust visual feedback when recording.

### Fixed
- Crash when pressing delete while recording.
- Error about directory not existing showing instead of the 'blend file isn't saved' error.
- Errors syncing the audio device user configuration per platform.
- Performance: poll available sound cards only every 5 seconds.
- Development prints no longer show in the terminal.


## [0.2.0] - 2020-07-05

### Shiny and New
- UI dropdown for sound card selection.
- Explicit check if running on a supported platform (Linux) with UI reporting.
- Prefered sound card is stored per platform so users can share their settings accross workstations.

### Fixed
- Sound files could be empty for short recordings on Linux.


## [0.1.0] - 2020-06-17

First usable version with instructions and a button to start/stop recording using ffmpeg on Linux.

### Shiny and New
- Added button to start/stop recording in the sequencer strips toolbar.  
  It creates a strip for visual feedback and records sound from a microphone device.
- Sound clips get saved next to the blend file or to a user configured folder and file name.
- Audio recording based on ffmpeg being an available command on linux.
- Manual setting to select an audio device other than the default with an index.
