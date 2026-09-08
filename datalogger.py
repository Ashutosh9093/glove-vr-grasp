# datalogger.py
"""
RECTIFIED DataLogger v4.0 - Thread-safe CSV logger for flex + IMU + position samples
+ TASK STATE LOGGING

Logs complete sensor data + hand position + grasp state + TASK PHASE every frame.
"""

import os
import csv
import threading
import datetime
import time
import math


class DataLogger:
    def __init__(self, out_dir='logs', filename=None, num_flex=5):
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"session_{ts}.csv"
        self.filename = fname
        self.path = os.path.join(out_dir, fname)
        self.lock = threading.Lock()
        self.num_flex = num_flex

        # Track position for translational movement
        self._last_position = None
        self._position_history = []
        self._max_history = 10

        try:
            self._file = open(self.path, 'w', newline='', encoding='utf-8')
            self._writer = csv.writer(self._file)
        except Exception:
            self._file = None
            self._writer = None

        # RECTIFIED v4.0: Extended header with task phase
        header = ["timestamp", "millis"]

        # Flex sensor data (15 columns)
        header += [f"raw_f{i+1}" for i in range(num_flex)]
        header += [f"smooth_f{i+1}" for i in range(num_flex)]
        header += [f"norm_f{i+1}" for i in range(num_flex)]

        # IMU orientation data (7 columns)
        header += ["qw", "qx", "qy", "qz", "roll_deg", "pitch_deg", "yaw_deg"]

        # IMU inertial data (6 columns)
        header += ["gyro_x", "gyro_y", "gyro_z", "accel_x", "accel_y", "accel_z"]

        # Hand position tracking (3 columns)
        header += ["hand_pos_x", "hand_pos_y", "hand_pos_z"]

        # Translational movement (4 columns)
        header += ["hand_vel_x", "hand_vel_y", "hand_vel_z", "hand_displacement_m"]

        # Grasp information (2 columns)
        header += ["grasp_amount_0to1", "finger_contacts_count"]

        # Table transition detection (1 column)
        header += ["table_transition_flag"]

        # RECTIFIED v4.0: Task phase and elapsed time (2 columns)
        header += ["task_phase", "phase_elapsed_sec"]

        if self._writer:
            try:
                self._writer.writerow(header)
                self._file.flush()
            except Exception:
                pass

    def _calculate_movement(self, current_pos):
        """Calculate velocity and displacement from position history."""
        if not current_pos or len(current_pos) < 3:
            return [0.0, 0.0, 0.0], 0.0

        velocity = [0.0, 0.0, 0.0]
        displacement = 0.0

        if self._last_position:
            try:
                for i in range(3):
                    velocity[i] = float(current_pos[i]) - float(self._last_position[i])

                displacement = math.sqrt(velocity[0]**2 + velocity[1]**2 + velocity[2]**2)
            except Exception:
                pass

        return velocity, displacement

    def _detect_table_transition(self):
        """Detect if hand has moved significantly (table-to-table movement)."""
        if len(self._position_history) < 2:
            return False

        try:
            pos_current = self._position_history[-1]
            pos_previous = self._position_history[-2]

            displacement = 0.0
            for i in range(3):
                displacement += (float(pos_current[i]) - float(pos_previous[i])) ** 2
            displacement = math.sqrt(displacement)

            # Threshold for table transition (0.5m horizontal movement)
            return displacement > 0.5
        except Exception:
            return False

    def log_sample(self, timestamp, millis, flex_raw, flex_smooth, flex_norm=None,
                   quat=None, euler=None, gyro=None, accel=None, hand_pos=None,
                   grasp_amount=0.0, finger_contacts=0, task_phase="UNKNOWN", 
                   phase_elapsed=0.0):
        """
        Log a complete sample with all sensor data, hand position, and task phase.
        
        RECTIFIED v4.0: Added task_phase and phase_elapsed parameters.
        Called every frame (~50 Hz) from the main update loop.
        """
        with self.lock:
            ts = datetime.datetime.fromtimestamp(timestamp).isoformat()

            # Ensure millis is valid
            if millis is None or millis == "":
                millis = int(timestamp * 1000)
            else:
                try:
                    millis = int(millis)
                except Exception:
                    millis = int(timestamp * 1000)

            row = [ts, millis]

            # Flex raw (5 columns)
            row += [f"{v:.4f}" for v in (flex_raw or [])[:self.num_flex]]
            while len(row) < 2 + self.num_flex:
                row.append("0.0")

            # Flex smooth (5 columns)
            row += [f"{v:.4f}" for v in (flex_smooth or [])[:self.num_flex]]
            while len(row) < 2 + 2 * self.num_flex:
                row.append("0.0")

            # Flex normalized (5 columns)
            row += [f"{v:.4f}" for v in (flex_norm or [])[:self.num_flex]]
            while len(row) < 2 + 3 * self.num_flex:
                row.append("0.0")

            # Quaternion (4 columns)
            row += [f"{v:.6f}" for v in (quat or [0, 0, 0, 0])[:4]]

            # Euler angles (3 columns)
            row += [f"{v:.3f}" for v in (euler or [0, 0, 0])[:3]]

            # Gyroscope (3 columns)
            row += [f"{v:.6f}" for v in (gyro or [0, 0, 0])[:3]]

            # Accelerometer (3 columns)
            row += [f"{v:.6f}" for v in (accel or [0, 0, 0])[:3]]

            # Hand position (3 columns)
            if hand_pos and len(hand_pos) >= 3:
                row += [f"{float(hand_pos[0]):.6f}",
                        f"{float(hand_pos[1]):.6f}",
                        f"{float(hand_pos[2]):.6f}"]
            else:
                row += ["0.0", "0.0", "0.0"]

            # Calculate velocity and displacement (4 columns)
            velocity, displacement = self._calculate_movement(hand_pos)
            row += [f"{v:.6f}" for v in velocity]
            row += [f"{displacement:.6f}"]

            # Track position history
            if hand_pos:
                self._position_history.append(list(hand_pos))
                if len(self._position_history) > self._max_history:
                    self._position_history.pop(0)
                self._last_position = list(hand_pos)

            # Grasp amount and contacts (2 columns)
            row += [f"{float(grasp_amount):.4f}", f"{int(finger_contacts)}"]

            # Table transition detection (1 column)
            table_transition = 1 if self._detect_table_transition() else 0
            row += [str(table_transition)]

            # RECTIFIED v4.0: Task phase and elapsed time (2 columns)
            row += [str(task_phase), f"{float(phase_elapsed):.3f}"]

            if self._writer:
                try:
                    self._writer.writerow(row)
                except Exception:
                    pass

            try:
                # periodic flush every ~5s (safe non-blocking attempt)
                if int(time.time()) % 5 == 0 and self._file:
                    self._file.flush()
            except Exception:
                pass

    def close(self):
        """Close and flush the CSV file."""
        with self.lock:
            try:
                if self._file:
                    self._file.flush()
            except Exception:
                pass
            try:
                if self._file:
                    self._file.close()
            except Exception:
                pass