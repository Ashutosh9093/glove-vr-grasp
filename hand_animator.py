# hand_animator.py
"""
HandAnimator - Applies finger curl values (0..1) to discovered finger nodes.
RECTIFIED v4.0: Robust to missing nodes, uses scale fallback or whole-hand rotation fallback.
"""

import logging
import math

logging.basicConfig(level=logging.INFO)


class HandAnimator:
    def __init__(self, hand_node, max_rotation=60.0, finger_weights=None):
        self.hand_node = hand_node
        self.max_rotation = float(max_rotation)
        self.finger_smooth = [0.0] * 5
        self.finger_smooth_alpha = 0.15
        self.target_flex = [0.0] * 5
        self.finger_nodes = []
        self._orig_eulers = []
        self.finger_weights = finger_weights or [0.8, 1.0, 1.0, 0.9, 0.7]

        try:
            candidates = []
            if hasattr(hand_node, 'getChild'):
                for i in range(0, 50):
                    try:
                        c = hand_node.getChild(i)
                        if c is not None:
                            candidates.append(c)
                    except Exception:
                        break
            if hasattr(hand_node, 'getChildren'):
                try:
                    for c in hand_node.getChildren():
                        if c not in candidates:
                            candidates.append(c)
                except Exception:
                    pass
            if len(candidates) < 5:
                extra = []
                for c in candidates:
                    try:
                        if hasattr(c, 'getChildren'):
                            for g in c.getChildren():
                                extra.append(g)
                    except Exception:
                        pass
                for e in extra:
                    if e not in candidates:
                        candidates.append(e)
            scored = []
            for c in candidates:
                score = 0.0
                try:
                    name = str(c.getName()).lower()
                    if any(k in name for k in ('finger', 'phal', 'thumb', 'index', 'middle', 'ring', 'pinky')):
                        score += 10.0
                except Exception:
                    pass
                try:
                    p = c.getPosition()
                    score += abs(p[1]) + abs(p[2]) + abs(p[0])
                except Exception:
                    pass
                scored.append((score, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            self.finger_nodes = [c for _, c in scored[:5]]
        except Exception:
            self.finger_nodes = []

        while len(self.finger_nodes) < 5:
            self.finger_nodes.append(None)

        for i, node in enumerate(self.finger_nodes):
            if node:
                try:
                    e = list(node.getEuler())
                    self._orig_eulers.append(e)
                except Exception:
                    self._orig_eulers.append([0.0, 0.0, 0.0])
            else:
                self._orig_eulers.append([0.0, 0.0, 0.0])

        logging.info(f"✓ HandAnimator initialized - finger nodes discovered: {sum(1 for n in self.finger_nodes if n)}")

    def set_finger_flex(self, flex_values):
        if not flex_values or len(flex_values) < 5:
            return
        for i in range(5):
            try:
                self.target_flex[i] = max(0.0, min(1.0, float(flex_values[i])))
            except Exception:
                self.target_flex[i] = 0.0

    def get_finger_smooth(self):
        return list(self.finger_smooth)

    def get_grasp_amount(self):
        weighted = 0.0
        wsum = 0.0
        for i, v in enumerate(self.finger_smooth):
            w = self.finger_weights[i] if i < len(self.finger_weights) else 1.0
            weighted += v * w
            wsum += w
        return weighted / max(1e-6, wsum)

    def update(self):
        if not self.hand_node:
            return
        alpha = self.finger_smooth_alpha
        for i in range(5):
            self.finger_smooth[i] = (1.0 - alpha) * self.finger_smooth[i] + alpha * self.target_flex[i]

        applied = False
        for i, node in enumerate(self.finger_nodes):
            flex_val = self.finger_smooth[i]
            angle = flex_val * self.max_rotation
            if node:
                applied = True
                try:
                    orig = self._orig_eulers[i] or [0.0, 0.0, 0.0]
                    new_euler = [orig[0] + angle, orig[1], orig[2]]
                    try:
                        node.setEuler(new_euler)
                    except Exception:
                        try:
                            node.setEuler(float(new_euler[0]), float(new_euler[1]), float(new_euler[2]))
                        except Exception:
                            try:
                                node.setRotation(angle, 1.0, 0.0, 0.0)
                            except Exception:
                                pass
                except Exception:
                    pass

        if not applied:
            try:
                composite = self.get_grasp_amount()
                scale_factor = 1.0 + composite * 0.05
                try:
                    self.hand_node.setScale(scale_factor, scale_factor, scale_factor)
                except Exception:
                    try:
                        s = self.hand_node.getScale()
                        if isinstance(s, (list, tuple)) and len(s) == 3:
                            self.hand_node.setScale(s[0] * scale_factor, s[1] * scale_factor, s[2] * scale_factor)
                    except Exception:
                        pass
            except Exception:
                pass

    def reset_hand(self):
        self.target_flex = [0.0] * 5
        self.finger_smooth = [0.0] * 5
        self.update()

    def close_hand(self):
        self.target_flex = [1.0] * 5
        self.update()