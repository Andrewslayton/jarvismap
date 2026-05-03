# JarvisMap - Voice Controlled Note Taking Application

JarvisMap is a desktop application that combines computer vision, hand gesture recognition, and voice commands to create an intuitive note-taking experience.

## Features

- **Hand Gesture Controls**:

  - 👋 Wave hand quickly: Create a new note
  - ✊✊ Two fists held: Stop recording (but don't save)
  - 👍 Thumbs up: Save note and return to main
  - ✌️ Hold up 2 fingers: Cancel/discard current note
  - ✋🤛 Hold one hand open + one fist: Voice navigation to notes

- **Voice Recognition**:

  - Say "Title [your title]" to set note titles
  - Say "Begin" to start recording note content
  - Say "Edit" when viewing a note to start voice editing
  - Voice navigation to find notes by title

- **Local Storage**: All notes are saved locally in JSON format
- **Grid View**: Beautiful grid layout showing all your notes
- **Real-time Camera Feed**: Live camera view with hand tracking
- **Voice Editing**: Edit existing notes by voice command

## Requirements

- Python 3.7 or higher
- Webcam
- Microphone
- Windows 10 or later

## Installation

### Automatic Installation (Recommended)

1. Double-click `install_and_run.bat`
2. Wait for dependencies to install
3. The application will start automatically

### Manual Installation

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Run the application:
   ```
   python jarvismap.py
   ```

## Usage Guide

### Getting Started

1. Launch the application
2. Allow camera and microphone access when prompted
3. Position yourself in front of the camera so your hands are visible

### Creating a New Note

1. **Wave your hand quickly** in front of the camera
2. The application will switch to "New Note" mode
3. Say **"Title"** followed by your desired title (e.g., "Title Meeting Notes")
4. Say **"Begin"** to start recording your note content
5. Speak your note content - it will appear in real-time
6. **Make two fists** to stop recording (optional)
7. **Give a thumbs up** to save and return to main page
8. **Hold up 2 fingers** to cancel and discard the note

### Editing Existing Notes

1. Click on any note from the main grid to open it
2. Say **"Edit"** to start voice editing mode
3. Speak your additional content - it will be appended to the existing note
4. Close the window to save your changes automatically

**Note:** The "Edit" command is only for existing notes. When creating new notes, you don't need to say "Edit" - just follow the Title → Begin → Content flow above.

### Navigating to Existing Notes

1. From the main page, **hold one hand open and make a fist with the other**
2. Say the title (or part of the title) of the note you want to open
3. The note will open in a new window

### Viewing Notes

- All notes are displayed in a grid on the main page
- Click any note to open it in a detailed view
- Notes show title, content preview, and creation date

## Gesture Recognition Tips

- **Wave Detection**: Move your hand quickly from side to side (at least 3 direction changes)
- **Two Fists**: Make clear fists with both hands simultaneously to stop recording
- **Thumbs Up Save**: Extend thumb upward while keeping other fingers closed/down
- **Two-Finger Cancel**: Hold up exactly 2 fingers (like peace sign or index+middle) to discard note
- **Open/Fist Navigation**: Keep one hand completely open (fingers extended) and make a clear fist with the other
- **Camera Position**: Keep your hands within the camera frame and well-lit
- **Distance**: Stay 2-3 feet from the camera for optimal detection

## Troubleshooting

### Camera Issues

- Make sure no other applications are using your camera
- Check that your camera is properly connected
- Try restarting the application

### Microphone Issues

- Verify microphone permissions in Windows settings
- Speak clearly and at normal volume
- Reduce background noise for better recognition

### Gesture Recognition Issues

- Ensure good lighting
- Make deliberate, clear gestures
- Wait for the cooldown period between gestures (1 second)
- Keep your hands clearly visible in the camera frame

### Speech Recognition Issues

- Check your internet connection (uses Google Speech Recognition)
- Speak clearly and at normal pace
- Ensure minimal background noise

## File Structure

```
jarvismap/
├── jarvismap.py          # Main application
├── gesture_detector.py   # Hand gesture recognition module
├── requirements.txt      # Python dependencies
├── install_and_run.bat  # Installation script
├── notes.json           # Your notes (created automatically)
└── README.md           # This file
```

## Dependencies

- **opencv-python**: Camera access and computer vision
- **mediapipe**: Hand tracking and landmark detection
- **SpeechRecognition**: Voice recognition
- **pyaudio**: Audio input handling
- **Pillow**: Image processing for UI
- **numpy**: Numerical operations

## Privacy & Security

- All notes are stored locally on your computer
- No data is sent to external servers except for speech recognition
- Camera feed is processed locally and not transmitted anywhere
- Voice commands use Google's speech recognition service

## Support

If you encounter any issues:

1. Check the troubleshooting section above
2. Ensure all dependencies are properly installed
3. Verify camera and microphone permissions
4. Try running the application as administrator

## Future Enhancements

Planned features for future versions:

- Offline speech recognition
- Note editing capabilities
- Export/import functionality
- Custom gesture training
- Dark/light theme options
- Search functionality
