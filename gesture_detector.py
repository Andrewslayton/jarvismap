import time
from collections import deque

class GestureDetector:
    def __init__(self):
        self.wave_positions = deque(maxlen=8)
        self.last_gesture_time = 0
        self.gesture_cooldown = 2.0
    
    def _check_cooldown(self):
        current_time = time.time()
        if current_time - self.last_gesture_time > self.gesture_cooldown:
            self.last_gesture_time = current_time
            return True
        return False

    def _count_fingers(self, landmarks, include_thumb=True, threshold=0.02):
        """Count extended fingers. Thumb uses x-axis, others use y-axis."""
        count = 0
        if include_thumb and abs(landmarks[4].x - landmarks[3].x) > 0.04:
            count += 1
        for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
            if landmarks[tip].y < landmarks[pip].y - threshold:
                count += 1
        return count

    def detect_wave(self, landmarks, sensitive_mode=False):
        wrist = landmarks[0]  
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
        
        if is_wave and self._check_cooldown():
            self.wave_positions.clear()
            return True
        
        return False
    
    def detect_two_fists(self, left_landmarks, right_landmarks):
        """Detect two held fists to stop recording"""
        left_closed = not self.is_hand_open(left_landmarks)
        right_closed = not self.is_hand_open(right_landmarks)
        return left_closed and right_closed and self._check_cooldown()
    
    def detect_thumbs_up_save(self, landmarks):
        """Detect thumbs up gesture to save note"""
        thumb_up = landmarks[4].y < landmarks[2].y - 0.03
        wrist_y = landmarks[0].y
        fingers_down = all(
            landmarks[tip].y > wrist_y - 0.05
            for tip in (8, 12, 16, 20)
        )
        return thumb_up and fingers_down and self._check_cooldown()
    
    def detect_two_fingers_cancel(self, landmarks):
        """Detect exactly two fingers held up to cancel/discard note"""
        return self._count_fingers(landmarks, include_thumb=True) == 2 and self._check_cooldown()
    
    def detect_open_fist(self, left_landmarks, right_landmarks):
        """Detect one open hand and one closed fist for voice navigation"""
        left_open = self.is_hand_open(left_landmarks)
        right_open = self.is_hand_open(right_landmarks)
        return (left_open != right_open) and self._check_cooldown()
    
    def get_palm_center(self, landmarks):
        """Calculate approximate palm center from landmarks"""
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        
        palm_x = (wrist.x + middle_mcp.x) / 2
        palm_y = (wrist.y + middle_mcp.y) / 2
        palm_z = (wrist.z + middle_mcp.z) / 2
        
        return (palm_x, palm_y, palm_z)
    
    def is_hand_open(self, landmarks):
        """Hand is open if at least 3 fingers are extended"""
        return self._count_fingers(landmarks, include_thumb=True) >= 3
    
    def detect_eight_fingers_save(self, left_landmarks, right_landmarks):
        """Detect 4 fingers on each hand (8 total, excluding thumbs) to save note"""
        left_fingers = self.count_extended_fingers(left_landmarks)
        right_fingers = self.count_extended_fingers(right_landmarks)
        return left_fingers == 4 and right_fingers == 4 and self._check_cooldown()
    
    def count_extended_fingers(self, landmarks):
        """Count extended fingers excluding thumb (relaxed threshold for faster detection)"""
        return self._count_fingers(landmarks, include_thumb=False, threshold=0.015)