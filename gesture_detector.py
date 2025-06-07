import numpy as np
import time
from collections import deque

class GestureDetector:
    def __init__(self):
        self.wave_positions = deque(maxlen=8)
        self.last_gesture_time = 0
        self.gesture_cooldown = 2.0
    
    def detect_wave(self, landmarks, sensitive_mode=False):
        """Detect hand waving gesture based on wrist movement"""
        wrist = landmarks[0]  # Wrist landmark
        current_time = time.time()
        self.wave_positions.append((wrist.x, current_time))
        
        if sensitive_mode:
            min_positions = 3  
            min_range = 0.10  
            max_time = 1.2     
            min_changes = 1    
        else:
            min_positions = 4
            min_range = 0.12
            max_time = 1.5
            min_changes = 2
        
        if len(self.wave_positions) < min_positions:
            return False
        

        positions = list(self.wave_positions)
        x_positions = [pos[0] for pos in positions]
        times = [pos[1] for pos in positions]
        x_range = max(x_positions) - min(x_positions)
        time_range = times[-1] - times[0]

        direction_changes = 0
        for i in range(1, len(x_positions) - 1):
            if (x_positions[i] > x_positions[i-1] and x_positions[i] > x_positions[i+1]) or \
               (x_positions[i] < x_positions[i-1] and x_positions[i] < x_positions[i+1]):
                direction_changes += 1
        
        is_wave = (x_range > min_range and direction_changes >= min_changes and time_range < max_time)
        
        if is_wave:
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                self.last_gesture_time = current_time
                self.wave_positions.clear()
                return True
        
        return False
    
    def detect_two_fists(self, left_landmarks, right_landmarks):
        """Detect two held fists to stop recording"""
        left_closed = not self.is_hand_open(left_landmarks)
        right_closed = not self.is_hand_open(right_landmarks)
        
        # Both hands are fists
        if left_closed and right_closed:
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                self.last_gesture_time = current_time
                return True
        
        return False
    
    def detect_thumbs_up_save(self, landmarks):
        """Detect thumbs up gesture to save note"""
        thumb_tip = landmarks[4]  # Thumb tip
        thumb_mcp = landmarks[2]  # Thumb MCP joint
        index_tip = landmarks[8]  # Index finger tip
        middle_tip = landmarks[12]  # Middle finger tip
        ring_tip = landmarks[16]  # Ring finger tip
        pinky_tip = landmarks[20]  # Pinky tip
        wrist = landmarks[0]  # Wrist
        thumb_up = thumb_tip.y < thumb_mcp.y - 0.03
        
        fingers_down = (index_tip.y > wrist.y - 0.05 and 
                       middle_tip.y > wrist.y - 0.05 and 
                       ring_tip.y > wrist.y - 0.05 and 
                       pinky_tip.y > wrist.y - 0.05)
        
        if thumb_up and fingers_down:
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                self.last_gesture_time = current_time
                return True
        
        return False
    
    def detect_two_fingers_cancel(self, landmarks):
        """Detect exactly two fingers held up to cancel/discard note"""
        # Check if exactly 2 fingers are extended
        finger_tips = [4, 8, 12, 16, 20] 
        finger_pips = [3, 6, 10, 14, 18]  
        
        extended_fingers = 0
        
        for tip, pip in zip(finger_tips, finger_pips):
            # For thumb, check x-axis (thumb moves differently)
            if tip == 4:  # Thumb
                if abs(landmarks[tip].x - landmarks[pip].x) > 0.04:
                    extended_fingers += 1
            else:  # Other fingers, check y-axis
                if landmarks[tip].y < landmarks[pip].y - 0.02:
                    extended_fingers += 1
        
        # Cancel gesture: exactly 2 fingers extended
        if extended_fingers == 2:
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                self.last_gesture_time = current_time
                return True
        
        return False
    
    def detect_open_fist(self, left_landmarks, right_landmarks):
        """Detect one open hand and one closed fist for voice navigation"""
        left_open = self.is_hand_open(left_landmarks)
        right_open = self.is_hand_open(right_landmarks)
        
        # One hand open, one closed
        is_gesture = (left_open and not right_open) or (not left_open and right_open)
        
        if is_gesture:
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                self.last_gesture_time = current_time
                return True
        
        return False
    
    def get_palm_center(self, landmarks):
        """Calculate approximate palm center from landmarks"""
        # Use wrist and middle finger MCP joint to approximate palm center
        wrist = landmarks[0]
        middle_mcp = landmarks[9]  # Middle finger MCP joint
        
        palm_x = (wrist.x + middle_mcp.x) / 2
        palm_y = (wrist.y + middle_mcp.y) / 2
        palm_z = (wrist.z + middle_mcp.z) / 2
        
        return (palm_x, palm_y, palm_z)
    
    def is_hand_open(self, landmarks):
        """Determine if hand is open based on finger positions"""
        # Check if fingers are extended
        finger_tips = [4, 8, 12, 16, 20]  # Thumb, Index, Middle, Ring, Pinky tips
        finger_pips = [3, 6, 10, 14, 18]  # Corresponding PIP joints
        
        extended_fingers = 0
        
        for tip, pip in zip(finger_tips, finger_pips):
            # For thumb, check x-axis (thumb moves differently)
            if tip == 4:  # Thumb
                if abs(landmarks[tip].x - landmarks[pip].x) > 0.04:
                    extended_fingers += 1
            else:  # Other fingers, check y-axis
                if landmarks[tip].y < landmarks[pip].y - 0.02:
                    extended_fingers += 1
        
        # Hand is considered open if at least 3 fingers are extended
        return extended_fingers >= 3
    
    def detect_eight_fingers_save(self, left_landmarks, right_landmarks):
        """Detect 4 fingers on each hand (8 total) to save note"""
        # Check if 4 fingers are extended on left hand
        left_fingers = self.count_extended_fingers(left_landmarks)
        # Check if 4 fingers are extended on right hand  
        right_fingers = self.count_extended_fingers(right_landmarks)
        
        # Save gesture: 4 fingers on each hand (8 total)
        if left_fingers == 4 and right_fingers == 4:
            current_time = time.time()
            if current_time - self.last_gesture_time > self.gesture_cooldown:
                self.last_gesture_time = current_time
                return True
        
        return False
    
    def count_extended_fingers(self, landmarks):
        """Count how many fingers are extended on a hand (excluding thumb for cleaner detection)"""
        extended_count = 0
        
        # Finger tip and pip joint indices (excluding thumb for cleaner detection)
        finger_tips = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky tips
        finger_pips = [6, 10, 14, 18]  # Corresponding PIP joints
        
        # Check each finger with slightly relaxed threshold for faster detection
        for tip, pip in zip(finger_tips, finger_pips):
            # Finger is extended if tip is higher than pip joint
            if landmarks[tip].y < landmarks[pip].y - 0.015:  # Slightly reduced threshold
                extended_count += 1
        
        return extended_count 