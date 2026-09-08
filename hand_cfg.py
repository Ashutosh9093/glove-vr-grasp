# hand_cfg.py
"""
hand_cfg.py - Hand Configuration Class
Importable module for hand.cfg configuration

RECTIFIED v4.0: Unified defaults and config loading from hand.cfg file.
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO)


class HandConfig:
    def __init__(self, config_path='hand.cfg'):
        # Defaults: put hand in front of camera
        self.position = [0.0, 1.25, 3.0]
        self.scale = [1.0, 1.0, 1.0]
        self.rotation = [0, 0, 0]
        self.hand_euler_offset = [-180.0, 0, -90.0]
        self.finger_bones = {
            'thumb': [1, 2, 3],
            'index': [4, 5, 6],
            'middle': [8, 9, 10],
            'ring': [12, 13, 14],
            'pinky': [16, 17, 18]
        }

        self.grasp_threshold = 0.55
        self.release_threshold = 0.25
        self.grab_distance = 0.20
        self.target_hand_span = None
        self.grasp_reach_scale = None
        self.pickup_radius = None
        self.contact_margin = None
        self.min_finger_contacts = None

        self.color = [1.0, 1.0, 1.0]
        self.enable_physics = False
        self.visible = True
        self.model = None
        self.config_loaded = False

        if os.path.exists(config_path):
            self._parse_config(config_path)
            self.config_loaded = True
            logging.info(f"HandConfig: loaded from {config_path}")
        else:
            logging.info("HandConfig: no hand.cfg found - using defaults")

    def _parse_config(self, path):
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception:
            return

        def parse_nums(rhs, cast=float):
            parts = [p.strip() for p in rhs.split(',') if p.strip()]
            out = []
            for p in parts:
                try:
                    out.append(cast(p))
                except Exception:
                    s = p.strip()
                    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
                        out.append(s[1:-1])
                    else:
                        out.append(p)
            return out

        m = re.search(r'^\s*model\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            rhs = m.group(1).strip()
            if (rhs.startswith("'") and rhs.endswith("'")) or (rhs.startswith('"') and rhs.endswith('"')):
                self.model = rhs[1:-1]
            else:
                self.model = rhs

        m = re.search(r'^\s*position\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            vals = parse_nums(m.group(1))
            if len(vals) >= 3:
                try:
                    self.position = [float(vals[0]), float(vals[1]), float(vals[2])]
                except Exception:
                    pass

        m = re.search(r'^\s*scale\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            vals = parse_nums(m.group(1))
            if len(vals) >= 3:
                try:
                    self.scale = [float(vals[0]), float(vals[1]), float(vals[2])]
                except Exception:
                    pass

        m = re.search(r'^\s*rotation\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            vals = parse_nums(m.group(1))
            if len(vals) >= 3:
                try:
                    self.rotation = [float(vals[0]), float(vals[1]), float(vals[2])]
                except Exception:
                    pass

        m = re.search(r'^\s*hand_euler_offset\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            vals = parse_nums(m.group(1))
            if len(vals) >= 3:
                try:
                    self.hand_euler_offset = [float(vals[0]), float(vals[1]), float(vals[2])]
                except Exception:
                    pass

        for finger in ['thumb', 'index', 'middle', 'ring', 'pinky']:
            m = re.search(r'^\s*' + re.escape(finger) + r'\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
            if m:
                vals = parse_nums(m.group(1), cast=int)
                if vals:
                    try:
                        self.finger_bones[finger] = [int(v) for v in vals]
                    except Exception:
                        pass

        m = re.search(r'^\s*grasp_threshold\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            try:
                self.grasp_threshold = float(m.group(1).strip())
            except Exception:
                pass

        m = re.search(r'^\s*release_threshold\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            try:
                self.release_threshold = float(m.group(1).strip())
            except Exception:
                pass

        m = re.search(r'^\s*grab_distance\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            try:
                self.grab_distance = float(m.group(1).strip())
            except Exception:
                pass

        m = re.search(r'^\s*target_hand_span\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            try:
                self.target_hand_span = float(m.group(1).strip())
            except Exception:
                pass

        for key in ('grasp_reach_scale', 'pickup_radius', 'contact_margin'):
            m = re.search(r'^\s*' + re.escape(key) + r'\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
            if m:
                try:
                    setattr(self, key, float(m.group(1).strip()))
                except Exception:
                    pass

        m = re.search(r'^\s*min_finger_contacts\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            try:
                self.min_finger_contacts = int(float(m.group(1).strip()))
            except Exception:
                pass

        m = re.search(r'^\s*color\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            vals = parse_nums(m.group(1))
            if len(vals) >= 3:
                try:
                    self.color = [float(vals[0]), float(vals[1]), float(vals[2])]
                except Exception:
                    pass

        m = re.search(r'^\s*enable_physics\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            val = m.group(1).strip().lower()
            self.enable_physics = val in ['true', '1', 'yes', 'on']

        m = re.search(r'^\s*visible\s*=\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if m:
            val = m.group(1).strip().lower()
            self.visible = val in ['true', '1', 'yes', 'on']

    def __str__(self):
        """Return a formatted string representation of the hand configuration."""
        lines = [
            "=" * 50,
            "HAND CONFIGURATION",
            "=" * 50,
            f"Model:              {self.model if self.model else 'Default'}",
            f"Position (x,y,z):   {self.position}",
            f"Scale (x,y,z):      {self.scale}",
            f"Rotation (r,p,y):   {self.rotation}",
            f"Euler Offset:       {self.hand_euler_offset}",
            f"Color (R,G,B):      {self.color}",
            f"Visible:            {self.visible}",
            f"Physics Enabled:    {self.enable_physics}",
            f"Grasp Threshold:    {self.grasp_threshold}",
            f"Release Threshold:  {self.release_threshold}",
            f"Grab Distance:      {self.grab_distance}",
            f"Target Hand Span:   {self.target_hand_span if self.target_hand_span else 'auto (launcher default)'}",
            "",
            "FINGER BONES:",
        ]

        for finger, bones in self.finger_bones.items():
            lines.append(f"  {finger.capitalize():8} -> {bones}")

        lines.append("=" * 50)

        return "\n".join(lines)

    def get_position(self):
        return self.position

    def get_scale(self):
        return self.scale

    def get_rotation(self):
        return self.rotation

    def get_euler_offset(self):
        return self.hand_euler_offset

    def get_all_finger_bones(self):
        return self.finger_bones

    def get_grasp_threshold(self):
        return self.grasp_threshold

    def get_release_threshold(self):
        return self.release_threshold

    def get_grab_distance(self):
        return self.grab_distance

    def get_target_hand_span(self):
        return self.target_hand_span

    def get_grasp_reach_scale(self):
        return self.grasp_reach_scale

    def get_pickup_radius(self):
        return self.pickup_radius

    def get_contact_margin(self):
        return self.contact_margin

    def get_min_finger_contacts(self):
        return self.min_finger_contacts

    def get_color(self):
        return self.color

    def is_visible(self):
        return self.visible

    def get_model(self):
        return self.model

    def is_config_loaded(self):
        return self.config_loaded