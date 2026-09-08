# serial_reader.py
"""
SerialIMUReader - Thread-safe IMU + Flex sensor reader with smoothing and filtering.
Handles ESP32 data, calibration, and flex normalization.

RECTIFIED:
- Aggressive outlier rejection on raw flex values (glitch detection)
- Better handling of sensor disconnects/bad data
- More robust CSV parsing with field validation
"""

import serial
import serial.tools.list_ports
import threading
import time
import math
import json
import logging

logging.basicConfig(level=logging.INFO)


def quat_to_euler_degrees(q):
    """Convert quaternion [w,x,y,z] to Euler angles in degrees"""
    if not q or len(q) < 4:
        return [0.0, 0.0, 0.0]
    
    w, x, y, z = q
    
    # Roll (rotation around X axis)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    
    # Pitch (rotation around Y axis)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)
    
    # Yaw (rotation around Z axis)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]


class SerialIMUReader:
    """Reads IMU + Flex sensor data from ESP32 via serial"""
    
    def __init__(self, port='COM3', baud=115200, num_flex=5, window=15, use_hardware=True):
        self.port = port
        self.baud = baud
        self.num_flex = num_flex
        self.window = window
        self.use_hardware = use_hardware
        
        self.lock = threading.Lock()
        self.running = True
        
        # Calibration - RECTIFIED: use conservative defaults
        self.flex_min = [0.0] * num_flex
        self.flex_max = [1.0] * num_flex
        self.gyro_offset = [0.0, 0.0, 0.0]
        self.gyro_scale = [1.0, 1.0, 1.0]
        self.accel_offset = [0.0, 0.0, 0.0]
        self.accel_scale = [1.0, 1.0, 1.0]
        self.rest_quat = [1.0, 0.0, 0.0, 0.0]
        
        # Raw sensor data
        self.flex_raw = [0.0] * num_flex
        self.gyro_raw = [0.0, 0.0, 0.0]
        self.accel_raw = [0.0, 0.0, 0.0]
        self.quat_raw = [1.0, 0.0, 0.0, 0.0]
        
        # Filtered/smoothed data
        self.flex_smooth = [0.0] * num_flex
        self.gyro_smooth = [0.0, 0.0, 0.0]
        self.accel_smooth = [0.0, 0.0, 0.0]
        self.quat_smooth = [1.0, 0.0, 0.0, 0.0]
        
        # History for smoothing
        self.flex_history = [[0.0] * window for _ in range(num_flex)]
        self.gyro_history = [[0.0] * window for _ in range(3)]
        self.accel_history = [[0.0] * window for _ in range(3)]
        
        self.history_idx = 0
        
        # Connection status
        self.connected = False
        self.serial_port = None
        
        # External logger hook
        self._external_logger = None
        
        # Start reader thread
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        
        logging.info(f"SerialIMUReader: initialized (port={port}, baud={baud})")
    
    def set_calibration(self, sensor_min=None, sensor_max=None, 
                       gyro_offset=None, gyro_scale=None,
                       accel_offset=None, accel_scale=None,
                       rest_quat=None, rest_euler=None):
        """Set calibration values - RECTIFIED with sanitization"""
        with self.lock:
            if sensor_min:
                # RECTIFIED: reject any obviously corrupt values
                cleaned_min = []
                for v in sensor_min:
                    try:
                        fv = float(v)
                        if -1000 < fv < 1000 and math.isfinite(fv):
                            cleaned_min.append(fv)
                        else:
                            cleaned_min.append(0.0)
                            logging.warning(f"Rejected corrupt flex_min value: {fv}")
                    except:
                        cleaned_min.append(0.0)
                self.flex_min = cleaned_min
                logging.info(f"Flex sensor min set: {self.flex_min}")
            
            if sensor_max:
                # RECTIFIED: reject any obviously corrupt values
                cleaned_max = []
                for v in sensor_max:
                    try:
                        fv = float(v)
                        if -1000 < fv < 1000 and math.isfinite(fv):
                            cleaned_max.append(fv)
                        else:
                            cleaned_max.append(1.0)
                            logging.warning(f"Rejected corrupt flex_max value: {fv}")
                    except:
                        cleaned_max.append(1.0)
                self.flex_max = cleaned_max
                logging.info(f"Flex sensor max set: {self.flex_max}")
            
            if gyro_offset:
                self.gyro_offset = [float(v) if math.isfinite(float(v)) else 0.0 for v in gyro_offset]
                logging.info(f"Gyro offset set: {self.gyro_offset}")
            if gyro_scale:
                self.gyro_scale = [float(v) if math.isfinite(float(v)) else 1.0 for v in gyro_scale]
                logging.info(f"Gyro scale set: {self.gyro_scale}")
            if accel_offset:
                self.accel_offset = [float(v) if math.isfinite(float(v)) else 0.0 for v in accel_offset]
                logging.info(f"Accel offset set: {self.accel_offset}")
            if accel_scale:
                self.accel_scale = [float(v) if math.isfinite(float(v)) else 1.0 for v in accel_scale]
                logging.info(f"Accel scale set: {self.accel_scale}")
            if rest_quat:
                q = [float(v) if math.isfinite(float(v)) else 0.0 for v in rest_quat]
                mag = math.sqrt(sum(x*x for x in q))
                if mag > 1e-9:
                    self.rest_quat = [x/mag for x in q]
                logging.info(f"Rest quaternion set: {self.rest_quat}")
        
        logging.info("✓ Comprehensive calibration applied (with corruption checks)")
    
    def is_connected(self):
        """Check if reader is connected"""
        with self.lock:
            return self.connected
    
    def get_flex(self):
        """Get raw flex values"""
        with self.lock:
            return list(self.flex_raw)
    
    def get_smooth_flex(self):
        """Get smoothed flex values"""
        with self.lock:
            return list(self.flex_smooth)
    
    def get_normalized_smooth_flex(self):
        """Get normalized smoothed flex (0-1)"""
        with self.lock:
            normalized = []
            for i in range(self.num_flex):
                lo = self.flex_min[i]
                hi = self.flex_max[i]
                span = hi - lo
                
                # RECTIFIED: sanity check before dividing
                if span < 0.001 or not math.isfinite(span):
                    normalized.append(0.0)
                else:
                    val = (self.flex_smooth[i] - lo) / span
                    normalized.append(max(0.0, min(1.0, val)))
            return normalized
    
    def get_gyro(self):
        """Get raw gyroscope"""
        with self.lock:
            return list(self.gyro_raw)
    
    def get_accel(self):
        """Get raw accelerometer"""
        with self.lock:
            return list(self.accel_raw)
    
    def get_quat(self):
        """Get smoothed quaternion [w,x,y,z]"""
        with self.lock:
            return list(self.quat_smooth)
    
    def get_euler(self):
        """Get Euler angles from quaternion (degrees)"""
        with self.lock:
            return quat_to_euler_degrees(self.quat_smooth)
    
    def _reader_loop(self):
        """Main reader thread"""
        retry_count = 0
        max_retries = 5
        
        while self.running:
            try:
                # Find port
                ports = [p.device for p in serial.tools.list_ports.comports()
                        if any(x in p.description.lower() for x in ['ch340', 'cp210', 'usb', 'esp'])]
                
                if not ports:
                    with self.lock:
                        self.connected = False
                    time.sleep(1)
                    continue
                
                port = ports[0]
                
                try:
                    self.serial_port = serial.Serial(port, self.baud, timeout=0.5)
                    self.serial_port.reset_input_buffer()
                    time.sleep(0.3)
                    
                    with self.lock:
                        self.connected = True
                    
                    logging.info(f"SerialIMUReader: connected to {port} @ {self.baud}")
                    retry_count = 0
                    
                    while self.running and self.connected:
                        try:
                            line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                            
                            if not line or len(line) < 10:
                                continue
                            
                            self._parse_data_line(line)
                            
                        except Exception as e:
                            logging.debug(f"Parse error: {e}")
                            continue
                
                except serial.SerialException as e:
                    logging.warning(f"Serial connection lost: {e}")
                    with self.lock:
                        self.connected = False
                    retry_count += 1
                    
                    if retry_count >= max_retries:
                        time.sleep(2)
                        retry_count = 0
                    else:
                        time.sleep(0.5)
            
            except Exception as e:
                logging.warning(f"Reader error: {e}")
                time.sleep(1)
    
    def _parse_data_line(self, line):
        """Parse CSV data from ESP32 - RECTIFIED with better error handling"""
        try:
            parts = [p.strip() for p in line.split(',')]
            
            # RECTIFIED: validate field count more carefully
            if len(parts) < 15:
                return
            
            with self.lock:
                # Flex sensors (5 values) - RECTIFIED: range check
                for i in range(self.num_flex):
                    try:
                        val = float(parts[i])
                        # RECTIFIED: reject obviously bad values (sensor glitches)
                        if -1000 < val < 1000 and math.isfinite(val):
                            self.flex_raw[i] = val
                    except:
                        pass
                
                # Gyro (3 values) - RECTIFIED: range check
                for i in range(3):
                    try:
                        raw = float(parts[5 + i])
                        if -500 < raw < 500 and math.isfinite(raw):
                            self.gyro_raw[i] = (raw - self.gyro_offset[i]) * self.gyro_scale[i]
                    except:
                        pass
                
                # Accel (3 values) - RECTIFIED: range check
                for i in range(3):
                    try:
                        raw = float(parts[8 + i])
                        if -100 < raw < 100 and math.isfinite(raw):
                            self.accel_raw[i] = (raw - self.accel_offset[i]) * self.accel_scale[i]
                    except:
                        pass
                
                # Quaternion (4 values) - RECTIFIED: range check
                if len(parts) >= 15:
                    try:
                        q = [float(parts[11 + i]) for i in range(4)]
                        # Range check
                        if all(-2 < x < 2 and math.isfinite(x) for x in q):
                            # Normalize
                            mag = math.sqrt(sum(x*x for x in q))
                            if mag > 1e-9:
                                self.quat_raw = [x/mag for x in q]
                    except:
                        pass
                
                # Update smoothing
                self._update_smoothing()
        
        except Exception as e:
            logging.debug(f"Parse error: {e}")
    
    def _update_smoothing(self):
        """Update smoothed values from history"""
        # Add to history
        for i in range(self.num_flex):
            self.flex_history[i][self.history_idx] = self.flex_raw[i]
        
        for i in range(3):
            self.gyro_history[i][self.history_idx] = self.gyro_raw[i]
            self.accel_history[i][self.history_idx] = self.accel_raw[i]
        
        self.history_idx = (self.history_idx + 1) % self.window
        
        # Compute moving averages
        for i in range(self.num_flex):
            self.flex_smooth[i] = sum(self.flex_history[i]) / self.window
        
        for i in range(3):
            self.gyro_smooth[i] = sum(self.gyro_history[i]) / self.window
            self.accel_smooth[i] = sum(self.accel_history[i]) / self.window
        
        # Smooth quaternion with exponential smoothing
        alpha = 0.15
        for i in range(4):
            self.quat_smooth[i] = (1.0 - alpha) * self.quat_smooth[i] + alpha * self.quat_raw[i]
        
        # Normalize
        mag = math.sqrt(sum(x*x for x in self.quat_smooth))
        if mag > 1e-9:
            self.quat_smooth = [x/mag for x in self.quat_smooth]
    
    def stop(self):
        """Stop reader thread"""
        self.running = False
        try:
            if self.serial_port:
                self.serial_port.close()
        except:
            pass
        logging.info("SerialIMUReader: stopped")