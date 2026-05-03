import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import mediapipe as mp
import speech_recognition as sr
import json
import os
import threading
import time
from PIL import Image, ImageTk
import numpy as np
from datetime import datetime
from gesture_detector import GestureDetector
import uuid
import openai


EDIT_INSTRUCTION = "Say 'Edit' to voice edit, 'Clean up' for AI cleanup, or 8 fingers to save & close"

class JarvisMap:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JarvisMap - Voice Controlled Notes")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2c3e50')
        
        # Initialize MediaPipe with dynamic settings
        self.mp_hands = mp.solutions.hands
        # Create two different hand tracking configurations
        self.hands_main = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,  # Higher accuracy for main page
            min_tracking_confidence=0.6    # Higher accuracy for main page
        )
        self.hands_editing = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.6,  # Optimized for editing
            min_tracking_confidence=0.2    # Optimized for editing
        )
        
        # Start with main page settings
        self.hands = self.hands_main
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Initialize gesture detector
        self.gesture_detector = GestureDetector()
        
        # Initialize OpenAI client (you'll need to set OPENAI_API_KEY environment variable)
        self.openai_client = None
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)
                print("OpenAI client initialized successfully")
            else:
                print("OpenAI API key not found. Note cleanup feature will be disabled.")
                print("Set OPENAI_API_KEY environment variable to enable AI cleanup.")
        except Exception as e:
            print(f"OpenAI initialization error: {e}")
        
        # Initialize speech recognition with optimized settings
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000  # Higher threshold for faster detection
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.5    # Shorter pause for faster response
        self.microphone = sr.Microphone()
        
        # Voice activity tracking
        self.voice_active = False
        self.voice_lock = threading.Lock()
        self.current_voice_thread = None
        
        # Camera setup with dynamic optimization
        self.cap = None
        self.camera_active = False
        self.frame_skip_counter = 0
        # Dynamic frame skipping based on mode
        self.main_mode_gesture_skip = 0      # Process every frame on main page for wave detection
        self.editing_mode_gesture_skip = 2   # Process every 3rd frame when editing/creating notes
        
        # Notes storage
        self.notes_file = "notes.json"
        self.notes = self.load_notes()
        
        # Application state
        self.current_mode = "main"  # main, new_note, voice_nav, editing
        self.current_note = None
        self.gesture_cooldown = 0
        self.last_gesture_time = 0
        self.open_note_windows = []  # Track open note windows
        
        # Performance optimization
        self.last_ui_update = 0
        self.ui_update_interval = 0.05  # Update UI every 50ms max
        
        # UI Setup
        self.setup_ui()
        
        # Start camera thread
        self.start_camera()
        
        # Adjust microphone for ambient noise
        self.adjust_microphone()
    
    def setup_ui(self):
        # Main frame
        self.main_frame = tk.Frame(self.root, bg='#2c3e50')
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(
            self.main_frame,
            text="JarvisMap",
            font=('Arial', 24, 'bold'),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        title_label.pack(pady=(0, 20))
        
        # Camera frame
        self.camera_frame = tk.Frame(self.main_frame, bg='#34495e', relief=tk.RAISED, bd=2)
        self.camera_frame.pack(side=tk.RIGHT, padx=(20, 0))
        
        self.camera_label = tk.Label(
            self.camera_frame,
            text="Camera Feed",
            font=('Arial', 12),
            fg='#ecf0f1',
            bg='#34495e'
        )
        self.camera_label.pack(pady=5)
        
        self.video_label = tk.Label(self.camera_frame, bg='#34495e')
        self.video_label.pack(padx=10, pady=10)
        
        # Status label
        self.status_label = tk.Label(
            self.camera_frame,
            text="Wave hand: New note\n2 Fists: Stop recording\n8 Fingers: Save note\n2 Fingers: Cancel\nOpen+Fist: Voice nav/delete",
            font=('Arial', 10),
            fg='#bdc3c7',
            bg='#34495e',
            justify=tk.LEFT
        )
        self.status_label.pack(pady=5)
        
        # Notes area
        self.notes_frame = tk.Frame(self.main_frame, bg='#2c3e50')
        self.notes_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Notes grid
        self.setup_notes_grid()
        
        # New note interface (initially hidden)
        self.setup_new_note_interface()
    
    def setup_notes_grid(self):
        # Clear existing notes display
        for widget in self.notes_frame.winfo_children():
            widget.destroy()
        
        notes_title = tk.Label(
            self.notes_frame,
            text="Your Notes",
            font=('Arial', 18, 'bold'),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        notes_title.pack(pady=(0, 15))
        
        # Scrollable frame for notes
        canvas = tk.Canvas(self.notes_frame, bg='#2c3e50', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.notes_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2c3e50')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Display notes in grid
        row, col = 0, 0
        for note_id, note_data in self.notes.items():
            note_frame = tk.Frame(
                scrollable_frame,
                bg='#34495e',
                relief=tk.RAISED,
                bd=2,
                width=200,
                height=150
            )
            note_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            note_frame.grid_propagate(False)
            
            # Note title
            title_label = tk.Label(
                note_frame,
                text=note_data.get('title', 'Untitled'),
                font=('Arial', 12, 'bold'),
                fg='#ecf0f1',
                bg='#34495e',
                wraplength=180
            )
            title_label.pack(pady=(10, 5))
            
            # Note preview
            content_preview = note_data.get('content', '')[:100] + ('...' if len(note_data.get('content', '')) > 100 else '')
            content_label = tk.Label(
                note_frame,
                text=content_preview,
                font=('Arial', 9),
                fg='#bdc3c7',
                bg='#34495e',
                wraplength=180,
                justify=tk.LEFT
            )
            content_label.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
            
            # Date
            date_label = tk.Label(
                note_frame,
                text=note_data.get('date', ''),
                font=('Arial', 8),
                fg='#95a5a6',
                bg='#34495e'
            )
            date_label.pack(side=tk.BOTTOM, pady=5)
            
            # Make note clickable
            def open_note(note_id=note_id):
                self.open_note(note_id)
            
            note_frame.bind("<Button-1>", lambda e, nid=note_id: self.open_note(nid))
            for child in note_frame.winfo_children():
                child.bind("<Button-1>", lambda e, nid=note_id: self.open_note(nid))
            
            col += 1
            if col >= 3:  # 3 columns
                col = 0
                row += 1
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def setup_new_note_interface(self):
        self.new_note_frame = tk.Frame(self.main_frame, bg='#2c3e50')
        
        # Title
        title_label = tk.Label(
            self.new_note_frame,
            text="New Note",
            font=('Arial', 18, 'bold'),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        title_label.pack(pady=(0, 20))
        
        # Status
        self.new_note_status = tk.Label(
            self.new_note_frame,
            text="Say 'Title' followed by your note title...",
            font=('Arial', 12),
            fg='#e74c3c',
            bg='#2c3e50'
        )
        self.new_note_status.pack(pady=10)
        
        # Content area
        self.note_content = tk.Text(
            self.new_note_frame,
            font=('Arial', 12),
            bg='#34495e',
            fg='#ecf0f1',
            height=20,
            width=60,
            wrap=tk.WORD
        )
        self.note_content.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = tk.Frame(self.new_note_frame, bg='#2c3e50')
        button_frame.pack(pady=10)
        
        save_btn = tk.Button(
            button_frame,
            text="Save Note",
            command=self.save_current_note,
            bg='#27ae60',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        save_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel_new_note,
            bg='#e74c3c',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        cancel_btn.pack(side=tk.LEFT, padx=10)
    
    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        self.camera_active = True
        self.camera_thread = threading.Thread(target=self.update_camera, daemon=True)
        self.camera_thread.start()
    
    def update_camera(self):
        while self.camera_active:
            ret, frame = self.cap.read()
            if ret:
                # Flip frame horizontally for mirror effect
                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Dynamic frame skipping based on current mode
                self.frame_skip_counter += 1
                
                # Use different gesture processing frequency based on mode
                if self.current_mode == "main":
                    # On main page: process every frame for responsive wave detection
                    should_process_gestures = (self.frame_skip_counter % (self.main_mode_gesture_skip + 1) == 0)
                    # Use high accuracy settings for main page
                    current_hands = self.hands_main
                else:
                    # When editing/creating: use optimized frequency
                    should_process_gestures = (self.frame_skip_counter % (self.editing_mode_gesture_skip + 1) == 0)
                    # Use optimized settings for editing
                    current_hands = self.hands_editing
                
                if should_process_gestures:
                    # Process hand gestures with dynamic frequency and accuracy
                    results = current_hands.process(frame_rgb)
                    
                    # Store landmarks for note window gesture detection
                    self.last_detected_landmarks = results.multi_hand_landmarks if results.multi_hand_landmarks else []
                    
                    # Draw hand landmarks
                    if results.multi_hand_landmarks:
                        for hand_landmarks in results.multi_hand_landmarks:
                            self.mp_drawing.draw_landmarks(
                                frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
                            )
                        
                        # Check for gestures
                        self.check_gestures(results.multi_hand_landmarks)
                
                # Convert to tkinter format with smaller resolution for better performance
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_rgb = cv2.resize(frame_rgb, (280, 210))  # Smaller for better performance
                img = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                
                # Throttle UI updates for better performance
                current_time = time.time()
                if current_time - self.last_ui_update > self.ui_update_interval:
                    self.root.after(0, self.update_video_label, imgtk)
                    self.last_ui_update = current_time
            
            time.sleep(0.02)  # ~50 FPS but with dynamic processing
    
    def update_video_label(self, imgtk):
        self.video_label.configure(image=imgtk)
        self.video_label.image = imgtk
    
    def check_gestures(self, hand_landmarks):
        current_time = time.time()
        
        # Cooldown to prevent rapid gesture detection (reduced for faster response)
        if current_time - self.last_gesture_time < 2.0:
            return
        
        # Check for wave detection first (works with 1 or 2 hands visible)
        wave_detected = False
        for hand_landmark in hand_landmarks:
            landmarks = hand_landmark.landmark
            # Use sensitive mode on main page for better wave detection
            sensitive_mode = (self.current_mode == "main")
            if self.gesture_detector.detect_wave(landmarks, sensitive_mode):
                wave_detected = True
                break
        
        if wave_detected:
            self.last_gesture_time = current_time
            # Only allow new notes if in main mode AND no note windows are open
            if self.current_mode == "main" and len(self.open_note_windows) == 0:
                self.root.after(0, self.start_new_note)
            return  # Exit early if wave detected
        
        # Check for two-finger cancel gesture (works with 1 or 2 hands visible)
        cancel_detected = False
        for hand_landmark in hand_landmarks:
            landmarks = hand_landmark.landmark
            if self.gesture_detector.detect_two_fingers_cancel(landmarks):
                cancel_detected = True
                break
        
        if cancel_detected:
            self.last_gesture_time = current_time
            if self.current_mode == "new_note":
                self.root.after(0, self.cancel_new_note)
            return  # Exit early if cancel detected
        
        # Two hand specific gestures (only when exactly 2 hands detected)
        if len(hand_landmarks) == 2:
            left_landmarks = hand_landmarks[0].landmark
            right_landmarks = hand_landmarks[1].landmark
            
            # 8 fingers detection - save note (works for both new notes and editing)
            if self.gesture_detector.detect_eight_fingers_save(left_landmarks, right_landmarks):
                self.last_gesture_time = current_time
                if self.current_mode == "new_note":
                    self.root.after(0, self.save_and_return_to_main)
                elif self.current_mode == "editing":
                    # Handle 8-finger save for editing notes
                    self.root.after(0, self.handle_editing_save_gesture)
                return  # Exit early if 8 fingers detected
            
            # Two fists detection - stop recording
            elif self.gesture_detector.detect_two_fists(left_landmarks, right_landmarks):
                self.last_gesture_time = current_time
                if self.current_mode == "new_note":
                    self.root.after(0, self.stop_recording)
            
            # Open hand + fist detection using improved detector
            elif self.gesture_detector.detect_open_fist(left_landmarks, right_landmarks):
                self.last_gesture_time = current_time
                # Only allow voice navigation if in main mode AND no note windows are open
                if self.current_mode == "main" and len(self.open_note_windows) == 0:
                    self.root.after(0, self.start_voice_navigation)
    

    
    def adjust_microphone(self):
        # Adjust microphone for ambient noise
        threading.Thread(target=self._adjust_mic, daemon=True).start()
    
    def _adjust_mic(self):
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"Microphone adjustment error: {e}")
    
    def start_new_note(self):
        """Start new note with proper cleanup and state management"""
        # Don't allow new notes if any note windows are open
        if len(self.open_note_windows) > 0:
            return
            
        self.stop_all_voice_activity()
        self.current_mode = "new_note"
        self.current_note = {"title": "", "content": "", "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
        
        # Clear the text widget completely
        self.note_content.delete(1.0, tk.END)
        
        # Hide notes grid, show new note interface
        self.notes_frame.pack_forget()
        self.new_note_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Start listening for title with delay to avoid conflicts
        self.new_note_status.config(text="Say 'Title' followed by your note title...")
        self.root.after(500, self.start_title_listening)
    
    def start_title_listening(self):
        """Start title listening with proper resource management"""
        if self.acquire_voice_lock():
            self.current_voice_thread = threading.Thread(target=self.listen_for_title, daemon=True)
            self.current_voice_thread.start()
    
    def listen_for_title(self):
        try:
            while self.voice_active and self.current_mode == "new_note":
                try:
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.1)  # Faster adjustment
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)  # Reduced timeouts
                    
                    text = self.recognizer.recognize_google(audio).lower()
                    
                    if text.startswith("title"):
                        title = text[5:].strip()  # Remove "title" prefix
                        self.current_note["title"] = title.title()
                        
                        # Update UI
                        self.root.after(0, self.update_title_status, title.title())
                        self.root.after(0, self.start_content_recording)
                        return
                    else:
                        self.root.after(0, self.update_title_status, "Please say 'Title' followed by your title")
                        
                except (sr.UnknownValueError, sr.WaitTimeoutError):
                    continue
                except sr.RequestError as e:
                    self.root.after(0, self.update_title_status, f"Error: {e}")
                    time.sleep(0.5)  # Shorter sleep
                    
        finally:
            self.release_voice_lock()
    
    def update_title_status(self, message):
        self.new_note_status.config(text=message)
    
    def start_content_recording(self):
        if not self.acquire_voice_lock():
            return
            
        self.new_note_status.config(text=f"Title: {self.current_note['title']}\nSay 'Begin' then speak your note content...")
        self.current_voice_thread = threading.Thread(target=self.listen_for_content, daemon=True)
        self.current_voice_thread.start()
    
    def listen_for_content(self):
        try:
            while self.voice_active and self.current_mode == "new_note":
                try:
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.1)  # Faster adjustment
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)  # Reduced timeouts
                    
                    text = self.recognizer.recognize_google(audio).lower()
                    
                    if text.startswith("begin"):
                        self.root.after(0, self.update_content_status, "Recording... (2 fists to stop)")
                        self.root.after(0, self.record_note_content)
                        return
                    else:
                        self.root.after(0, self.update_content_status, "Say 'Begin' to start recording")
                        
                except (sr.UnknownValueError, sr.WaitTimeoutError):
                    continue
                except sr.RequestError as e:
                    self.root.after(0, self.update_content_status, f"Error: {e}")
                    time.sleep(0.5)  # Shorter sleep
                    
        finally:
            self.release_voice_lock()
    
    def update_content_status(self, message):
        self.new_note_status.config(text=f"Title: {self.current_note['title']}\n{message}")
    
    def record_note_content(self):
        if not self.acquire_voice_lock():
            return
            
        content_parts = []
        
        def continuous_listen():
            try:
                while self.voice_active and self.current_mode == "new_note":
                    try:
                        with self.microphone as source:
                            audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=5)  # Faster response
                        
                        text = self.recognizer.recognize_google(audio)
                        content_parts.append(text)
                        
                        # Update content display
                        full_content = " ".join(content_parts)
                        self.current_note["content"] = full_content
                        self.root.after(0, self.update_note_content, full_content)
                        
                    except (sr.UnknownValueError, sr.WaitTimeoutError):
                        continue
                    except sr.RequestError as e:
                        print(f"Speech recognition error: {e}")
                        time.sleep(0.5)
                        
            finally:
                self.release_voice_lock()
        
        self.current_voice_thread = threading.Thread(target=continuous_listen, daemon=True)
        self.current_voice_thread.start()
    
    def update_note_content(self, content):
        self.note_content.delete(1.0, tk.END)
        self.note_content.insert(1.0, content)
    
    @staticmethod
    def _generate_note_id():
        return f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

    def save_current_note(self):
        if self.current_note and self.current_note["title"]:
            note_id = self._generate_note_id()
            self.notes[note_id] = self.current_note.copy()
            self.save_notes()
            self.return_to_main()
    
    def cancel_new_note(self):
        """Cancel new note with proper cleanup"""
        self.stop_all_voice_activity()
        self.current_note = None
        
        # Clear the text widget completely
        self.note_content.delete(1.0, tk.END)
        
        self.return_to_main()
    
    def return_to_main(self):
        """Return to main with proper cleanup"""
        self.stop_all_voice_activity()
        self.current_mode = "main"
        self.current_note = None
        
        # Hide new note interface, show notes grid
        self.new_note_frame.pack_forget()
        self.notes_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Refresh notes display
        self.setup_notes_grid()
    
    def start_voice_navigation(self):
        """Start voice navigation with proper resource management"""
        if not self.acquire_voice_lock():
            return
            
        self.current_mode = "voice_nav"
        self.current_voice_thread = threading.Thread(target=self.voice_navigate, daemon=True)
        self.current_voice_thread.start()
    
    def voice_navigate(self):
        """Voice navigation with improved error handling and delete functionality"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)  # Faster adjustment
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=3)  # Reduced timeouts
            
            text = self.recognizer.recognize_google(audio).lower()
            print(f"Voice navigation heard: {text}")
            
            # Check for delete command
            if text.startswith("delete"):
                delete_title = text[6:].strip()  # Remove "delete" prefix
                self.root.after(0, self.delete_note_by_title, delete_title)
                return
            
            # Find note by title to open
            for note_id, note_data in self.notes.items():
                if text.lower() in note_data.get('title', '').lower():
                    self.root.after(0, self.open_note, note_id)
                    return
            
            print(f"No note found with title containing: {text}")
            
        except Exception as e:
            print(f"Voice navigation error: {e}")
        finally:
            self.release_voice_lock()
            self.current_mode = "main"
    
    def delete_note_by_title(self, title):
        """Delete a note by its title"""
        note_to_delete = None
        note_title = None
        for note_id, note_data in self.notes.items():
            if title.lower() in note_data.get('title', '').lower():
                note_to_delete = note_id
                note_title = note_data.get('title', 'Unknown')
                break
        
        if note_to_delete:
            # Delete immediately without confirmation
            del self.notes[note_to_delete]
            self.save_notes()
            self.setup_notes_grid()  # Refresh the display
            print(f"Deleted note: {note_title}")
        else:
            print(f"No note found with title containing: {title}")
    
    def open_note(self, note_id):
        """Open note with improved state management"""
        # Don't allow opening notes if in new_note mode
        if self.current_mode == "new_note":
            return
            
        # Close any existing note windows first
        self.close_all_note_windows()
        
        # Stop any current voice activity
        self.stop_all_voice_activity()
        
        if note_id in self.notes:
            note_data = self.notes[note_id]
            
            # Create note viewing window
            note_window = tk.Toplevel(self.root)
            note_window.title(f"Note: {note_data.get('title', 'Untitled')}")
            note_window.geometry("600x500")
            note_window.configure(bg='#2c3e50')
            
            # Store note_id and editing state in window for gesture detection
            note_window.note_id = note_id
            note_window.is_editing = False
            
            # Add to tracking list
            self.open_note_windows.append(note_window)
            
            # Set mode to editing to prevent new notes
            self.current_mode = "editing"
            
            # Title
            title_label = tk.Label(
                note_window,
                text=note_data.get('title', 'Untitled'),
                font=('Arial', 16, 'bold'),
                fg='#ecf0f1',
                bg='#2c3e50'
            )
            title_label.pack(pady=10)
            
            # Edit instruction
            edit_label = tk.Label(
                note_window,
                text=EDIT_INSTRUCTION,
                font=('Arial', 10),
                fg='#3498db',
                bg='#2c3e50'
            )
            edit_label.pack(pady=5)
            
            # Content
            content_text = tk.Text(
                note_window,
                font=('Arial', 12),
                bg='#34495e',
                fg='#ecf0f1',
                wrap=tk.WORD
            )
            content_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            content_text.insert(1.0, note_data.get('content', ''))
            
            # Store content_text reference for saving
            note_window.content_text = content_text
            
            # Date
            date_label = tk.Label(
                note_window,
                text=f"Created: {note_data.get('date', '')}",
                font=('Arial', 10),
                fg='#95a5a6',
                bg='#2c3e50'
            )
            date_label.pack(pady=5)
            
            # Handle window closing
            def on_note_window_close():
                self.stop_all_voice_activity()
                self.remove_note_window(note_window)
                note_window.destroy()
                # Reset mode to main if no more windows open
                if len(self.open_note_windows) == 0:
                    self.current_mode = "main"
            
            note_window.protocol("WM_DELETE_WINDOW", on_note_window_close)
            
            # Start gesture detection for this window
            self.start_note_window_gesture_detection(note_window)
            
            # Start listening for "edit" command after a short delay
            self.root.after(1000, lambda: self.start_edit_listener(note_window, note_id, content_text, edit_label))
    
    def start_note_window_gesture_detection(self, note_window):
        """Start gesture detection specifically for note windows with optimization"""
        def check_note_gestures():
            if not note_window.winfo_exists():
                return
            
            # The main gesture detection now handles 8-finger detection for editing mode
            # This method is kept for any future note-specific gestures
            
            # Continue checking if window still exists (reduced frequency)
            if note_window.winfo_exists():
                self.root.after(200, check_note_gestures)  # Check every 200ms instead of 100ms
        
        # Start gesture checking
        self.root.after(200, check_note_gestures)
    
    def save_and_close_note_window(self, note_window):
        """Save note content and close the window"""
        # Don't check gesture cooldown here since it's already checked in gesture detection
        
        # Save the current content from the text widget
        if hasattr(note_window, 'note_id') and hasattr(note_window, 'content_text'):
            note_id = note_window.note_id
            if note_id in self.notes:
                # Get current content from text widget and save it
                current_content = note_window.content_text.get(1.0, tk.END).strip()
                self.notes[note_id]['content'] = current_content
                self.save_notes()
                
                # Refresh the main notes grid
                if self.current_mode != "new_note":
                    self.root.after(0, self.setup_notes_grid)
        
        # Close the window
        self.stop_all_voice_activity()
        self.remove_note_window(note_window)
        note_window.destroy()
        
        # Reset mode if no more windows open
        if len(self.open_note_windows) == 0:
            self.current_mode = "main"
    
    def start_edit_listener(self, note_window, note_id, content_text, edit_label):
        """Listen for 'edit' command with improved resource management"""
        if not note_window.winfo_exists():
            return
            
        # Wait a bit for any previous voice operations to complete
        def try_acquire_voice():
            if not note_window.winfo_exists():
                return
                
            if self.acquire_voice_lock():
                # Successfully acquired lock, start listening
                self.current_voice_thread = threading.Thread(
                    target=lambda: self.listen_for_edit_command(note_window, note_id, content_text, edit_label), 
                    daemon=True
                )
                self.current_voice_thread.start()
            else:
                # Voice is busy, try again later
                if note_window.winfo_exists():
                    self.root.after(1000, try_acquire_voice)
        
        # Start trying to acquire voice lock
        self.root.after(500, try_acquire_voice)  # Small delay to ensure window is fully ready
    
    def listen_for_edit_command(self, note_window, note_id, content_text, edit_label):
        """Listen for edit command with improved error handling"""
        try:
            while note_window.winfo_exists() and self.voice_active:
                try:
                    # Create a fresh microphone context for this specific operation
                    with sr.Microphone() as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.1)
                        edit_label.config(text=f"🎤 {EDIT_INSTRUCTION}", fg='#3498db')
                        audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=3)
                    
                    text = self.recognizer.recognize_google(audio).lower()
                    print(f"Edit listener heard: {text}")
                    
                    if "edit" in text:
                        # Switch to edit mode
                        self.root.after(0, self.start_note_editing, note_window, note_id, content_text, edit_label)
                        return
                    elif "clean up" in text or "cleanup" in text or "clean" in text:
                        # Start AI cleanup
                        self.root.after(0, self.start_note_cleanup, note_window, content_text, edit_label)
                        return
                        
                except (sr.UnknownValueError, sr.WaitTimeoutError):
                    # Reset label on timeout
                    if note_window.winfo_exists():
                        edit_label.config(text=EDIT_INSTRUCTION, fg='#3498db')
                    continue
                except sr.RequestError as e:
                    print(f"Speech recognition error: {e}")
                    time.sleep(0.5)
                    
        except Exception as e:
            print(f"Edit listener error: {e}")
        finally:
            # Reset label when stopping
            if note_window.winfo_exists():
                edit_label.config(text=EDIT_INSTRUCTION, fg='#3498db')
            self.release_voice_lock()
    
    def start_note_editing(self, note_window, note_id, content_text, edit_label):
        """Start voice editing mode with proper resource management"""
        if not self.acquire_voice_lock():
            return
            
        edit_label.config(text="🔴 Recording... Say your additions. 8 fingers to save & close.", fg='#e74c3c')
        note_window.is_editing = True
        
        # Get current content
        current_content = content_text.get(1.0, tk.END).strip()
        
        def continuous_edit_listen():
            content_parts = [current_content] if current_content else []
            
            try:
                while note_window.winfo_exists() and self.voice_active:
                    try:
                        # Use a fresh microphone context
                        with sr.Microphone() as source:
                            audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=5)
                        
                        text = self.recognizer.recognize_google(audio)
                        content_parts.append(text)
                        
                        # Update content display
                        full_content = " ".join(content_parts)
                        self.root.after(0, self.update_edit_content, content_text, full_content)
                        
                        # Update the note in memory - but don't save to file yet (save on 8 fingers)
                        self.notes[note_id]['content'] = full_content
                        
                    except (sr.UnknownValueError, sr.WaitTimeoutError):
                        continue
                    except sr.RequestError as e:
                        print(f"Speech recognition error: {e}")
                        time.sleep(0.5)
                        
            finally:
                self.release_voice_lock()
                # Reset editing mode when done
                if note_window.winfo_exists():
                    note_window.is_editing = False
                    # Restart edit listener
                    self.root.after(1000, lambda: self.start_edit_listener(note_window, note_id, content_text, edit_label))
        
        self.current_voice_thread = threading.Thread(target=continuous_edit_listen, daemon=True)
        self.current_voice_thread.start()
    
    def update_edit_content(self, content_text, content):
        """Update the content text widget during editing"""
        content_text.delete(1.0, tk.END)
        content_text.insert(1.0, content)
    
    def start_note_cleanup(self, note_window, content_text, edit_label):
        """Start AI cleanup process for the note"""
        print("start_note_cleanup called")
        if not self.openai_client:
            print("OpenAI client is None - showing error message")
            edit_label.config(text="⚠️ OpenAI not available. Set OPENAI_API_KEY environment variable.", fg='#e74c3c')
            # Reset after 3 seconds
            self.root.after(3000, lambda: edit_label.config(
                text=EDIT_INSTRUCTION, 
                fg='#3498db'
            ))
            return
        
        # Show processing status
        print("OpenAI client available - starting cleanup process")
        edit_label.config(text="🤖 AI is cleaning up your note...", fg='#f39c12')
        
        # Get current content
        current_content = content_text.get(1.0, tk.END).strip()
        print(f"Content to clean: '{current_content[:50]}...' (length: {len(current_content)})")
        
        if not current_content:
            print("Note content is empty")
            edit_label.config(text="⚠️ Note is empty - nothing to clean up", fg='#e74c3c')
            # Reset after 2 seconds
            self.root.after(2000, lambda: edit_label.config(
                text=EDIT_INSTRUCTION, 
                fg='#3498db'
            ))
            return
        
        # Run cleanup in background thread to avoid blocking UI
        def cleanup_thread():
            print("Cleanup thread started")
            cleaned_content, status = self.cleanup_note_with_ai(current_content)
            print(f"Cleanup returned: status='{status}', content_length={len(cleaned_content)}")
            
            if status == "success":
                print("Cleanup successful - automatically applying cleaned content")
                # Automatically update the note content
                self.root.after(0, lambda: content_text.delete(1.0, tk.END))
                self.root.after(0, lambda: content_text.insert(1.0, cleaned_content))
                
                # Save the cleaned content
                if hasattr(note_window, 'note_id') and note_window.note_id in self.notes:
                    self.notes[note_window.note_id]['content'] = cleaned_content
                    self.save_notes()
                
                # Show success message briefly
                self.root.after(0, lambda: edit_label.config(text="✅ Note cleaned up successfully!", fg='#27ae60'))
                # Reset after 2 seconds
                self.root.after(2000, lambda: edit_label.config(
                    text=EDIT_INSTRUCTION, 
                    fg='#3498db'
                ))
            else:
                print(f"Cleanup failed with status: {status}")
                # Show error briefly
                self.root.after(0, lambda: edit_label.config(text=f"❌ Cleanup failed", fg='#e74c3c'))
                # Reset after 3 seconds
                self.root.after(3000, lambda: edit_label.config(
                    text=EDIT_INSTRUCTION, 
                    fg='#3498db'
                ))
        
        print("Starting cleanup background thread")
        # Start cleanup in background
        cleanup_thread_obj = threading.Thread(target=cleanup_thread, daemon=True)
        cleanup_thread_obj.start()
    
    def load_notes(self):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading notes: {e}")
        return {}
    
    def save_notes(self):
        try:
            with open(self.notes_file, 'w') as f:
                json.dump(self.notes, f, indent=2)
        except Exception as e:
            print(f"Error saving notes: {e}")
    
    def on_closing(self):
        self.camera_active = False
        self.close_all_note_windows()  # Close all note windows
        if self.cap:
            self.cap.release()
        # Clean up both MediaPipe instances
        if hasattr(self, 'hands_main'):
            self.hands_main.close()
        if hasattr(self, 'hands_editing'):
            self.hands_editing.close()
        self.root.destroy()
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def stop_recording(self):
        """Stop recording but don't save - triggered by two fists"""
        if self.current_mode == "new_note":
            self.new_note_status.config(text=f"Title: {self.current_note['title']}\nRecording stopped. 8 fingers to save, 2 fingers to cancel, or click buttons below.")
    
    def save_and_return_to_main(self):
        """Save note and return to main - triggered by 8 fingers gesture"""
        if self.current_note and self.current_note.get("title"):
            # Check if we should offer AI cleanup for new notes
            content = self.current_note.get("content", "").strip()
            if content and self.openai_client and len(content) > 50:  # Only for substantial content
                self.offer_new_note_cleanup()
            else:
                # Save without cleanup
                note_id = self._generate_note_id()
                self.notes[note_id] = self.current_note.copy()
                self.save_notes()
                self.return_to_main()
        else:
            # If no title, just return to main without saving
            self.return_to_main()
    
    def offer_new_note_cleanup(self):
        """Offer AI cleanup for new notes before saving"""
        # Create a simple dialog to ask if user wants AI cleanup
        dialog = tk.Toplevel(self.root)
        dialog.title("AI Cleanup Option")
        dialog.geometry("400x200")
        dialog.configure(bg='#2c3e50')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # Question
        question_label = tk.Label(
            dialog,
            text="Would you like AI to clean up\nyour note before saving?",
            font=('Arial', 14, 'bold'),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        question_label.pack(pady=20)
        
        subtitle_label = tk.Label(
            dialog,
            text="(Fixes grammar, removes filler words, improves structure)",
            font=('Arial', 10),
            fg='#bdc3c7',
            bg='#2c3e50'
        )
        subtitle_label.pack(pady=(0, 20))
        
        button_frame = tk.Frame(dialog, bg='#2c3e50')
        button_frame.pack(pady=10)
        
        def cleanup_and_save():
            dialog.destroy()
            # Show processing status
            self.new_note_status.config(text="🤖 AI is cleaning up your note...")
            
            # Run cleanup in background
            def cleanup_thread():
                content = self.current_note.get("content", "")
                cleaned_content, status = self.cleanup_note_with_ai(content)
                
                if status == "success":
                    # Automatically use cleaned content and save
                    self.current_note['content'] = cleaned_content
                    # Update the display
                    self.root.after(0, lambda: self.update_note_content(cleaned_content))
                    self.root.after(0, lambda: self.new_note_status.config(text="✅ Note cleaned and ready to save!"))
                    # Auto-save after a moment
                    self.root.after(1000, self.save_without_cleanup)
                else:
                    # Save without cleanup on error
                    self.root.after(0, self.save_without_cleanup)
                    self.root.after(0, lambda: self.new_note_status.config(
                        text=f"Cleanup failed, saved original version"
                    ))
            
            cleanup_thread_obj = threading.Thread(target=cleanup_thread, daemon=True)
            cleanup_thread_obj.start()
        
        def save_without_cleanup():
            dialog.destroy()
            note_id = self._generate_note_id()
            self.notes[note_id] = self.current_note.copy()
            self.save_notes()
            self.return_to_main()
        
        cleanup_btn = tk.Button(
            button_frame,
            text="✨ Yes, Clean Up",
            command=cleanup_and_save,
            bg='#27ae60',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        cleanup_btn.pack(side=tk.LEFT, padx=10)
        
        save_btn = tk.Button(
            button_frame,
            text="💾 Save As-Is",
            command=save_without_cleanup,
            bg='#3498db',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        save_btn.pack(side=tk.LEFT, padx=10)
    
    def _build_comparison_window(self, original_content, cleaned_content, on_accept, on_reject, on_manual_edit):
        """Build a side-by-side comparison window. Callbacks receive (comparison_window, clean_text)."""
        comparison_window = tk.Toplevel(self.root)
        comparison_window.title("AI Note Cleanup - Compare & Choose")
        comparison_window.geometry("800x600")
        comparison_window.configure(bg='#2c3e50')

        tk.Label(
            comparison_window, text="AI Note Cleanup Comparison",
            font=('Arial', 16, 'bold'), fg='#ecf0f1', bg='#2c3e50'
        ).pack(pady=10)

        main_frame = tk.Frame(comparison_window, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        orig_frame = tk.Frame(main_frame, bg='#2c3e50')
        orig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(orig_frame, text="Original", font=('Arial', 14, 'bold'), fg='#e74c3c', bg='#2c3e50').pack(pady=(0, 5))
        orig_text = tk.Text(orig_frame, font=('Arial', 11), bg='#34495e', fg='#ecf0f1', wrap=tk.WORD, state=tk.DISABLED)
        orig_text.pack(fill=tk.BOTH, expand=True)
        orig_text.config(state=tk.NORMAL)
        orig_text.insert(1.0, original_content)
        orig_text.config(state=tk.DISABLED)

        clean_frame = tk.Frame(main_frame, bg='#2c3e50')
        clean_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        tk.Label(clean_frame, text="AI Cleaned", font=('Arial', 14, 'bold'), fg='#27ae60', bg='#2c3e50').pack(pady=(0, 5))
        clean_text = tk.Text(clean_frame, font=('Arial', 11), bg='#34495e', fg='#ecf0f1', wrap=tk.WORD)
        clean_text.pack(fill=tk.BOTH, expand=True)
        clean_text.insert(1.0, cleaned_content)

        button_frame = tk.Frame(comparison_window, bg='#2c3e50')
        button_frame.pack(pady=20)

        for text, cmd, bg_color in [
            ("\u2713 Use AI Cleaned Version", lambda: on_accept(comparison_window, clean_text), '#27ae60'),
            ("\u270e Use My Edits", lambda: on_manual_edit(comparison_window, clean_text), '#3498db'),
            ("\u2717 Keep Original", lambda: on_reject(comparison_window, clean_text), '#e74c3c'),
        ]:
            tk.Button(
                button_frame, text=text, command=cmd, bg=bg_color,
                fg='white', font=('Arial', 12, 'bold'), padx=20
            ).pack(side=tk.LEFT, padx=10)

        tk.Label(
            comparison_window,
            text="You can edit the AI cleaned version on the right before accepting it",
            font=('Arial', 10), fg='#bdc3c7', bg='#2c3e50'
        ).pack(pady=(0, 10))

    def show_new_note_cleanup_comparison(self, original_content, cleaned_content):
        """Show cleanup comparison for new notes"""
        def _save_and_close(content, cw):
            self.current_note['content'] = content
            note_id = self._generate_note_id()
            self.notes[note_id] = self.current_note.copy()
            self.save_notes()
            cw.destroy()
            self.return_to_main()

        self._build_comparison_window(
            original_content, cleaned_content,
            on_accept=lambda cw, ct: _save_and_close(cleaned_content, cw),
            on_reject=lambda cw, ct: _save_and_close(original_content, cw),
            on_manual_edit=lambda cw, ct: _save_and_close(ct.get(1.0, tk.END).strip(), cw),
        )

    def show_cleanup_comparison(self, window, original_content, cleaned_content):
        """Show comparison for existing note edits"""
        def _apply_content(content, cw):
            if hasattr(window, 'content_text'):
                window.content_text.delete(1.0, tk.END)
                window.content_text.insert(1.0, content)
                if hasattr(window, 'note_id') and window.note_id in self.notes:
                    self.notes[window.note_id]['content'] = content
                    self.save_notes()
            cw.destroy()

        self._build_comparison_window(
            original_content, cleaned_content,
            on_accept=lambda cw, ct: _apply_content(cleaned_content, cw),
            on_reject=lambda cw, ct: cw.destroy(),
            on_manual_edit=lambda cw, ct: _apply_content(ct.get(1.0, tk.END).strip(), cw),
        )
        """Show cleanup comparison for new notes"""
        # Similar to the existing comparison but for new notes
        comparison_window = tk.Toplevel(self.root)
        comparison_window.title("AI Note Cleanup - Compare & Choose")
        comparison_window.geometry("800x600")
        comparison_window.configure(bg='#2c3e50')
        
        # Title
        title_label = tk.Label(
            comparison_window,
            text="AI Note Cleanup Comparison",
            font=('Arial', 16, 'bold'),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        title_label.pack(pady=10)
        
        # Main frame for side-by-side comparison
        main_frame = tk.Frame(comparison_window, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Original content frame
        orig_frame = tk.Frame(main_frame, bg='#2c3e50')
        orig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        orig_label = tk.Label(
            orig_frame,
            text="Original",
            font=('Arial', 14, 'bold'),
            fg='#e74c3c',
            bg='#2c3e50'
        )
        orig_label.pack(pady=(0, 5))
        
        orig_text = tk.Text(
            orig_frame,
            font=('Arial', 11),
            bg='#34495e',
            fg='#ecf0f1',
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        orig_text.pack(fill=tk.BOTH, expand=True)
        orig_text.config(state=tk.NORMAL)
        orig_text.insert(1.0, original_content)
        orig_text.config(state=tk.DISABLED)
        
        # Cleaned content frame
        clean_frame = tk.Frame(main_frame, bg='#2c3e50')
        clean_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        clean_label = tk.Label(
            clean_frame,
            text="AI Cleaned",
            font=('Arial', 14, 'bold'),
            fg='#27ae60',
            bg='#2c3e50'
        )
        clean_label.pack(pady=(0, 5))
        
        clean_text = tk.Text(
            clean_frame,
            font=('Arial', 11),
            bg='#34495e',
            fg='#ecf0f1',
            wrap=tk.WORD
        )
        clean_text.pack(fill=tk.BOTH, expand=True)
        clean_text.insert(1.0, cleaned_content)
        
        # Buttons frame
        button_frame = tk.Frame(comparison_window, bg='#2c3e50')
        button_frame.pack(pady=20)
        
        def accept_cleaned():
            # Save with cleaned content
            self.current_note['content'] = cleaned_content
            note_id = self._generate_note_id()
            self.notes[note_id] = self.current_note.copy()
            self.save_notes()
            comparison_window.destroy()
            self.return_to_main()
        
        def reject_cleaned():
            # Save with original content
            note_id = self._generate_note_id()
            self.notes[note_id] = self.current_note.copy()
            self.save_notes()
            comparison_window.destroy()
            self.return_to_main()
        
        def use_manual_edit():
            # Save with manually edited content
            manual_content = clean_text.get(1.0, tk.END).strip()
            self.current_note['content'] = manual_content
            note_id = self._generate_note_id()
            self.notes[note_id] = self.current_note.copy()
            self.save_notes()
            comparison_window.destroy()
            self.return_to_main()
        
        accept_btn = tk.Button(
            button_frame,
            text="✓ Use AI Cleaned Version",
            command=accept_cleaned,
            bg='#27ae60',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        accept_btn.pack(side=tk.LEFT, padx=10)
        
        edit_btn = tk.Button(
            button_frame,
            text="✎ Use My Edits",
            command=use_manual_edit,
            bg='#3498db',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        edit_btn.pack(side=tk.LEFT, padx=10)
        
        reject_btn = tk.Button(
            button_frame,
            text="✗ Keep Original",
            command=reject_cleaned,
            bg='#e74c3c',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        reject_btn.pack(side=tk.LEFT, padx=10)
        
        # Instructions
        instruction_label = tk.Label(
            comparison_window,
            text="You can edit the AI cleaned version on the right before accepting it",
            font=('Arial', 10),
            fg='#bdc3c7',
            bg='#2c3e50'
        )
        instruction_label.pack(pady=(0, 10))
    
    def save_without_cleanup(self):
        """Save note without cleanup"""
        note_id = self._generate_note_id()
        self.notes[note_id] = self.current_note.copy()
        self.save_notes()
        self.return_to_main()

    def acquire_voice_lock(self):
        """Acquire voice lock to prevent multiple voice operations"""
        with self.voice_lock:
            if not self.voice_active:
                self.voice_active = True
                return True
            return False
    
    def release_voice_lock(self):
        """Release voice lock"""
        with self.voice_lock:
            self.voice_active = False
            self.current_voice_thread = None
    
    def stop_all_voice_activity(self):
        """Stop all voice recognition activities"""
        with self.voice_lock:
            self.voice_active = False
            if self.current_voice_thread and self.current_voice_thread.is_alive():
                # Thread will stop naturally when voice_active becomes False
                pass
            self.current_voice_thread = None

    def close_all_note_windows(self):
        """Close all open note windows"""
        for window in self.open_note_windows[:]:  # Create a copy of the list
            try:
                if window.winfo_exists():
                    window.destroy()
            except:
                pass
        self.open_note_windows.clear()
        self.current_mode = "main"

    def remove_note_window(self, window):
        """Remove a note window from tracking"""
        if window in self.open_note_windows:
            self.open_note_windows.remove(window)

    def handle_editing_save_gesture(self):
        """Handle 8-finger save gesture when editing notes"""
        # Find the currently open note window and save it
        for window in self.open_note_windows:
            if window.winfo_exists():
                self.save_and_close_note_window(window)
                break

    def cleanup_note_with_ai(self, note_content):
        """Use OpenAI to clean up and improve note content"""
        if not self.openai_client:
            print("OpenAI client not available for cleanup")
            return note_content, "OpenAI not available"
        
        print(f"Starting AI cleanup for content: {note_content[:100]}...")
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cheapest model available
                messages=[
                    {
                        "role": "system",
                        "content": "Clean up this voice-to-text note: fix grammar, remove filler words (um, uh, like), break up run-on sentences, organize into paragraphs. Keep original meaning. Return only cleaned text."
                    },
                    {
                        "role": "user",
                        "content": note_content
                    }
                ],
                max_tokens=500,  # Reduced for cost savings - most notes won't need more
                temperature=0.1  # Lower for more consistent/cheaper results
            )
            
            cleaned_content = response.choices[0].message.content.strip()
            print(f"AI cleanup successful. Original length: {len(note_content)}, Cleaned length: {len(cleaned_content)}")
            return cleaned_content, "success"
            
        except Exception as e:
            print(f"AI cleanup failed: {str(e)}")
            return note_content, f"Error: {str(e)}"

        comparison_window = tk.Toplevel(self.root)
        comparison_window.title("AI Note Cleanup - Compare & Choose")
        comparison_window.geometry("800x600")
        comparison_window.configure(bg='#2c3e50')
        
        # Title
        title_label = tk.Label(
            comparison_window,
            text="AI Note Cleanup Comparison",
            font=('Arial', 16, 'bold'),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        title_label.pack(pady=10)
        
        # Main frame for side-by-side comparison
        main_frame = tk.Frame(comparison_window, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Original content frame
        orig_frame = tk.Frame(main_frame, bg='#2c3e50')
        orig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        orig_label = tk.Label(
            orig_frame,
            text="Original",
            font=('Arial', 14, 'bold'),
            fg='#e74c3c',
            bg='#2c3e50'
        )
        orig_label.pack(pady=(0, 5))
        
        orig_text = tk.Text(
            orig_frame,
            font=('Arial', 11),
            bg='#34495e',
            fg='#ecf0f1',
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        orig_text.pack(fill=tk.BOTH, expand=True)
        orig_text.config(state=tk.NORMAL)
        orig_text.insert(1.0, original_content)
        orig_text.config(state=tk.DISABLED)
        
        # Cleaned content frame
        clean_frame = tk.Frame(main_frame, bg='#2c3e50')
        clean_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        clean_label = tk.Label(
            clean_frame,
            text="AI Cleaned",
            font=('Arial', 14, 'bold'),
            fg='#27ae60',
            bg='#2c3e50'
        )
        clean_label.pack(pady=(0, 5))
        
        clean_text = tk.Text(
            clean_frame,
            font=('Arial', 11),
            bg='#34495e',
            fg='#ecf0f1',
            wrap=tk.WORD
        )
        clean_text.pack(fill=tk.BOTH, expand=True)
        clean_text.insert(1.0, cleaned_content)
        
        # Buttons frame
        button_frame = tk.Frame(comparison_window, bg='#2c3e50')
        button_frame.pack(pady=20)
        
        def accept_cleaned():
            # Update the original note window with cleaned content
            if hasattr(window, 'content_text'):
                window.content_text.delete(1.0, tk.END)
                window.content_text.insert(1.0, cleaned_content)
                # Save the note with cleaned content
                if hasattr(window, 'note_id') and window.note_id in self.notes:
                    self.notes[window.note_id]['content'] = cleaned_content
                    self.save_notes()
            comparison_window.destroy()
        
        def reject_cleaned():
            comparison_window.destroy()
        
        def use_manual_edit():
            # Get manually edited content from the clean_text widget
            manual_content = clean_text.get(1.0, tk.END).strip()
            if hasattr(window, 'content_text'):
                window.content_text.delete(1.0, tk.END)
                window.content_text.insert(1.0, manual_content)
                # Save the note with manually edited content
                if hasattr(window, 'note_id') and window.note_id in self.notes:
                    self.notes[window.note_id]['content'] = manual_content
                    self.save_notes()
            comparison_window.destroy()
        
        accept_btn = tk.Button(
            button_frame,
            text="✓ Use AI Cleaned Version",
            command=accept_cleaned,
            bg='#27ae60',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        accept_btn.pack(side=tk.LEFT, padx=10)
        
        edit_btn = tk.Button(
            button_frame,
            text="✎ Use My Edits",
            command=use_manual_edit,
            bg='#3498db',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        edit_btn.pack(side=tk.LEFT, padx=10)
        
        reject_btn = tk.Button(
            button_frame,
            text="✗ Keep Original",
            command=reject_cleaned,
            bg='#e74c3c',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20
        )
        reject_btn.pack(side=tk.LEFT, padx=10)
        
        # Instructions
        instruction_label = tk.Label(
            comparison_window,
            text="You can edit the AI cleaned version on the right before accepting it",
            font=('Arial', 10),
            fg='#bdc3c7',
            bg='#2c3e50'
        )
        instruction_label.pack(pady=(0, 10))

if __name__ == "__main__":
    app = JarvisMap()
    app.run() 