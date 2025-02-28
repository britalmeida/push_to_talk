# Release Notes

A summary of noteworthy changes for each release. Made for humans. 🧻  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.0.0] - 2025-02-28

Version 1 is officially released! 🎉

### Shiny and New
- Tested to work with Blender 4.4 and 4.5.
- macOS: use atunc, a new utility to record sound, instead of ffmpeg.
  This fixes the severely glitchy sound and comes bundled in the add-on so no external 
  dependencies are required. (#6)
- macOS + Linux: show improved microphone names and description in the UI.

### Fixed
- Audio recording off-sync by aligning the sound clip with the end instead of start time of the recording.  
  Sometimes the sound clip is shorter than the time since starting to record due to latency in 
  starting the recording process. The latency depends on the hardware and OS and can happen either 
  with atunc of ffmpeg. In our testing it was most often less than half a second, so we consider it 
  acceptable for the purpose of recording scratch dialog. The sound should now be added in sync with 
  the edit.

## [0.4.1] - 2024-11-01

Test conversion to the new Blender Extensions system and fixes for macOS.  
However!! the audio may sound severely glitchy on macOS depending on the ffmpeg configuration. We are looking into it.

### Shiny and New
- Tested to work with Blender 4.3.
- Packaged as an extension (test).
  *Not* listed on extensions.blender.org due to requiring a separate install of ffmpeg.

### Fixed
- macOS: ffmpeg not found when launching Blender through the GUI (#21)
- macOS: restoring preferences of preferred microphone.
- macOS: stability when (un)plugging devices while running.
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
