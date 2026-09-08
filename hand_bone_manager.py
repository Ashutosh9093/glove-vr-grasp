# hand_bone_manager.py
"""
HandBoneManager - Controls individual finger bones based on normalized flex sensor values (0-1).
RECTIFIED v4.0: Silently discovers bone hierarchy without verbose error messages.
"""

import logging

logging.basicConfig(level=logging.INFO)


class HandBoneManager:
    """Manages individual finger bone rotations based on flex sensor input."""

    def __init__(self, hand_node, bone_map=None, max_angle=80.0):
        """
        Args:
            hand_node: Vizard hand model node
            bone_map: dict mapping finger names to bone indices (optional, will auto-detect)
            max_angle: maximum rotation angle in degrees
        """
        self.hand_node = hand_node
        self.max_angle = float(max_angle)
        self.bone_map = bone_map or {
            'thumb': [1, 2, 3],
            'index': [4, 5, 6],
            'middle': [8, 9, 10],
            'ring': [12, 13, 14],
            'pinky': [16, 17, 18]
        }

        self.finger_smooth = [0.0] * 5
        self.finger_smooth_alpha = 0.25
        self.target_flex = [0.0] * 5
        self._bone_cache = {}
        self._discovery_complete = False
        self._available_bones = []

        self._discover_hand_hierarchy()
        logging.info("✓ HandBoneManager initialized")

    def _discover_hand_hierarchy(self):
        """Silently discover available bones in the hand model."""
        if not self.hand_node:
            return

        try:
            self._available_bones = []
            for i in range(0, 50):
                try:
                    bone = self.hand_node.getChild(i)
                    if bone:
                        self._available_bones.append((i, bone))
                except Exception:
                    if i > 20:
                        break
        except Exception:
            pass

        self._discovery_complete = True

        if self._available_bones:
            logging.info(f"✓ Discovered {len(self._available_bones)} bones in hand model")
        else:
            logging.warning("⚠ No bones discovered - hand model may use different structure")

    def has_bones(self):
        """RECTIFIED: Explicit check for whether bone discovery found anything."""
        return bool(self._available_bones)

    def set_finger_flex(self, flex_values):
        """
        Set target finger flex values (0-1 normalized from glove sensors).

        Args:
            flex_values: list of 5 float values [thumb, index, middle, ring, pinky]
                        Each value 0.0 (open) to 1.0 (fully closed)
        """
        if not flex_values or len(flex_values) < 5:
            return

        try:
            for i in range(5):
                self.target_flex[i] = max(0.0, min(1.0, float(flex_values[i])))
        except Exception as e:
            logging.debug(f"Failed to set finger flex: {e}")

    def get_finger_smooth(self):
        """Get smoothed finger flex values."""
        return list(self.finger_smooth)

    def update(self):
        """Update finger bone rotations with smoothed flex values."""
        if not self.hand_node:
            return

        alpha = self.finger_smooth_alpha
        for i in range(5):
            self.finger_smooth[i] = (
                (1.0 - alpha) * self.finger_smooth[i] +
                alpha * self.target_flex[i]
            )

        for idx, (bone_id, bone_node) in enumerate(self._available_bones):
            try:
                finger_idx = idx // 3
                if finger_idx >= 5:
                    continue

                flex_value = self.finger_smooth[finger_idx]
                angle = flex_value * self.max_angle

                try:
                    try:
                        bone_node.setEuler([0.0, angle, 0.0])
                    except TypeError:
                        bone_node.setEuler(0.0, angle, 0.0)
                except Exception:
                    try:
                        bone_node.setRotation(angle, 0.0, 1.0, 0.0)
                    except Exception:
                        pass
            except Exception:
                pass

    def reset_all_fingers(self):
        """Reset all fingers to open position."""
        self.target_flex = [0.0] * 5
        self.finger_smooth = [0.0] * 5
        self.update()

    def close_all_fingers(self):
        """Close all fingers to full grasp."""
        self.target_flex = [1.0] * 5
        self.update()