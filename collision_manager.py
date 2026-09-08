# collision_manager.py
"""
CollisionManager - Handles collision detection between hand and scene objects.
Includes cylinder/box/sphere support and separation vector computation.

RECTIFIED v4.0: Fixed hand passing through bottle by enforcing collision resolution
every frame, excluding bottle only during grasp/reach window.
"""

import math
import logging

logging.basicConfig(level=logging.INFO)


class BoundingBox:
    """Axis-Aligned Bounding Box for collision detection."""

    def __init__(self, center, size):
        self.center = list(center)
        self.size = [float(s) for s in list(size)]
        self.min_point = [
            center[0] - self.size[0] / 2.0,
            center[1] - self.size[1] / 2.0,
            center[2] - self.size[2] / 2.0
        ]
        self.max_point = [
            center[0] + self.size[0] / 2.0,
            center[1] + self.size[1] / 2.0,
            center[2] + self.size[2] / 2.0
        ]

    def contains_point(self, point):
        for i in range(3):
            if point[i] < self.min_point[i] or point[i] > self.max_point[i]:
                return False
        return True

    def closest_point_in_box(self, point):
        closest = []
        for i in range(3):
            closest.append(max(self.min_point[i], min(point[i], self.max_point[i])))
        return closest

    def distance_to_point(self, point):
        closest = self.closest_point_in_box(point)
        dist_sq = 0.0
        for i in range(3):
            d = point[i] - closest[i]
            dist_sq += d * d
        return math.sqrt(dist_sq)


class Sphere:
    def __init__(self, center, radius):
        self.center = list(center)
        self.radius = float(radius)

    def contains_point(self, point):
        dist_sq = 0.0
        for i in range(3):
            d = point[i] - self.center[i]
            dist_sq += d * d
        return dist_sq <= (self.radius * self.radius)

    def distance_to_point(self, point):
        dist_sq = 0.0
        for i in range(3):
            d = point[i] - self.center[i]
            dist_sq += d * d
        dist = math.sqrt(dist_sq)
        return max(0.0, dist - self.radius)

    def closest_point_on_surface(self, point):
        dist_sq = 0.0
        for i in range(3):
            d = point[i] - self.center[i]
            dist_sq += d * d
        dist = math.sqrt(dist_sq)
        if dist < 1e-6:
            return [self.center[0] + self.radius, self.center[1], self.center[2]]
        closest = []
        for i in range(3):
            closest.append(self.center[i] + (point[i] - self.center[i]) / dist * self.radius)
        return closest


class Cylinder:
    def __init__(self, center, radius, height):
        self.center = list(center)
        self.radius = float(radius)
        self.height = float(height)
        self.top = center[1] + self.height / 2.0
        self.bottom = center[1] - self.height / 2.0

    def contains_point(self, point):
        dx = point[0] - self.center[0]
        dz = point[2] - self.center[2]
        radial_sq = dx * dx + dz * dz
        inside_radial = radial_sq <= (self.radius * self.radius)
        inside_height = (point[1] >= self.bottom and point[1] <= self.top)
        return inside_radial and inside_height

    def distance_to_point(self, point):
        dx = point[0] - self.center[0]
        dz = point[2] - self.center[2]
        radial = math.sqrt(dx * dx + dz * dz)
        dy = 0.0
        if point[1] < self.bottom:
            dy = self.bottom - point[1]
        elif point[1] > self.top:
            dy = point[1] - self.top
        radial_dist = max(0.0, radial - self.radius)
        if dy > 0.0:
            return math.sqrt(radial_dist * radial_dist + dy * dy)
        return radial_dist

    def closest_point_on_surface(self, point):
        y = max(self.bottom, min(self.top, point[1]))
        dx = point[0] - self.center[0]
        dz = point[2] - self.center[2]
        radial = math.sqrt(dx * dx + dz * dz)
        if radial < 1e-6:
            cx = self.center[0] + self.radius
            cz = self.center[2]
        else:
            cx = self.center[0] + dx / radial * self.radius
            cz = self.center[2] + dz / radial * self.radius
        return [cx, y, cz]


class CollisionObject:
    def __init__(self, name, collision_type, center, bounds, enabled=True):
        self.name = name
        self.collision_type = collision_type
        self.center = list(center)
        self.bounds = bounds.copy() if isinstance(bounds, dict) else {}
        self.enabled = enabled
        self.collision_shape = None
        self._init_collision_shape()

    def _init_collision_shape(self):
        try:
            if self.collision_type == 'box':
                size = self.bounds.get('size', [1.0, 1.0, 1.0])
                self.collision_shape = BoundingBox(self.center, size)
            elif self.collision_type == 'sphere':
                radius = self.bounds.get('radius', 0.5)
                self.collision_shape = Sphere(self.center, radius)
            elif self.collision_type == 'cylinder':
                radius = self.bounds.get('radius', 0.5)
                height = self.bounds.get('height', 1.0)
                self.collision_shape = Cylinder(self.center, radius, height)
        except Exception:
            self.collision_shape = None

    def update_position(self, center):
        self.center = list(center)
        if not self.collision_shape:
            return
        if isinstance(self.collision_shape, BoundingBox):
            self.collision_shape.center = list(center)
            s = self.collision_shape.size
            self.collision_shape.min_point = [
                center[0] - s[0] / 2.0,
                center[1] - s[1] / 2.0,
                center[2] - s[2] / 2.0
            ]
            self.collision_shape.max_point = [
                center[0] + s[0] / 2.0,
                center[1] + s[1] / 2.0,
                center[2] + s[2] / 2.0
            ]
        elif isinstance(self.collision_shape, Sphere):
            self.collision_shape.center = list(center)
        elif isinstance(self.collision_shape, Cylinder):
            self.collision_shape.center = list(center)
            self.collision_shape.top = center[1] + self.collision_shape.height / 2.0
            self.collision_shape.bottom = center[1] - self.collision_shape.height / 2.0

    def distance_to_point(self, point):
        if not self.enabled or not self.collision_shape:
            return float('inf')
        return self.collision_shape.distance_to_point(point)

    def get_separation_vector(self, point, hand_radius=0.08):
        if not self.enabled or not self.collision_shape:
            return [0.0, 0.0, 0.0]

        shape = self.collision_shape

        # Box
        if isinstance(shape, BoundingBox):
            closest = shape.closest_point_in_box(point)
            dist = shape.distance_to_point(point)
            if dist < hand_radius:
                vec = [point[i] - closest[i] for i in range(3)]
                vec_len = math.sqrt(sum(v * v for v in vec))
                if vec_len > 1e-6:
                    needed = hand_radius - dist + 0.002
                    return [vec[i] / vec_len * needed for i in range(3)]
                return [0.0, hand_radius + 0.01, 0.0]

        # Sphere
        if isinstance(shape, Sphere):
            dist_to_surface = shape.distance_to_point(point)
            if dist_to_surface < hand_radius:
                dx = point[0] - shape.center[0]
                dy = point[1] - shape.center[1]
                dz = point[2] - shape.center[2]
                mag = math.sqrt(dx * dx + dy * dy + dz * dz)
                if mag > 1e-6:
                    needed = hand_radius - dist_to_surface + 0.002
                    return [dx / mag * needed, dy / mag * needed, dz / mag * needed]
                return [0.0, hand_radius + 0.01, 0.0]

        # Cylinder
        if isinstance(shape, Cylinder):
            dist_to_surface = shape.distance_to_point(point)
            if dist_to_surface < hand_radius:
                cp = shape.closest_point_on_surface(point)
                vec = [point[i] - cp[i] for i in range(3)]
                vec_len = math.sqrt(sum(v * v for v in vec))
                if vec_len > 1e-6:
                    needed = hand_radius - dist_to_surface + 0.002
                    return [vec[i] / vec_len * needed for i in range(3)]
                return [0.0, hand_radius + 0.01, 0.0]

        return [0.0, 0.0, 0.0]


class CollisionManager:
    """Manages all collision detection and resolution."""

    def __init__(self, hand_collision_radius=0.08, debug=False):
        self.hand_collision_radius = float(hand_collision_radius)
        self.collision_objects = {}
        self.debug = debug
        self.collision_events = []

    def register_object(self, name, collision_type, center, bounds, enabled=True):
        self.collision_objects[name] = CollisionObject(name, collision_type, center, bounds, enabled)
        if self.debug:
            logging.debug(f"Registered collision object: {name} ({collision_type})")

    def unregister_object(self, name):
        if name in self.collision_objects:
            del self.collision_objects[name]
            if self.debug:
                logging.debug(f"Unregistered collision object: {name}")

    def update_object_position(self, name, center):
        if name in self.collision_objects:
            self.collision_objects[name].update_position(center)

    def set_object_enabled(self, name, enabled):
        if name in self.collision_objects:
            self.collision_objects[name].enabled = enabled

    def check_collision(self, hand_pos, exclude=None):
        """RECTIFIED: Check for collisions, excluding specific objects as needed."""
        exclude = set(exclude) if exclude else set()
        min_distance = float('inf')
        closest_object = None
        for obj_name, obj in self.collision_objects.items():
            if not obj.enabled or obj_name in exclude:
                continue
            dist = obj.distance_to_point(hand_pos)
            if dist < self.hand_collision_radius and dist < min_distance:
                min_distance = dist
                closest_object = obj_name
        is_colliding = closest_object is not None
        return is_colliding, closest_object, min_distance

    def resolve_collision(self, hand_pos, max_iterations=3, exclude=None):
        """RECTIFIED: Resolve collisions, excluding specific objects as needed."""
        exclude = set(exclude) if exclude else set()
        adjusted_pos = list(hand_pos)
        self.collision_events = []
        for iteration in range(max_iterations):
            collision_found = False
            total_separation = [0.0, 0.0, 0.0]
            colliding_objects = []
            for obj_name, obj in self.collision_objects.items():
                if not obj.enabled or obj_name in exclude:
                    continue
                dist = obj.distance_to_point(adjusted_pos)
                if dist < self.hand_collision_radius:
                    collision_found = True
                    colliding_objects.append(obj_name)
                    sep = obj.get_separation_vector(adjusted_pos, self.hand_collision_radius)
                    for i in range(3):
                        total_separation[i] += sep[i]
            if not collision_found:
                break
            for i in range(3):
                adjusted_pos[i] += total_separation[i]
            if colliding_objects:
                self.collision_events.append({
                    'iteration': iteration,
                    'objects': colliding_objects,
                    'original_pos': hand_pos,
                    'adjusted_pos': list(adjusted_pos)
                })
                if self.debug:
                    logging.debug(f"Collision iteration {iteration}: {colliding_objects}")
        return adjusted_pos

    def get_closest_safe_point(self, target_pos, max_distance=1.0):
        is_colliding, _, _ = self.check_collision(target_pos)
        if not is_colliding:
            return list(target_pos)
        safe_pos = self.resolve_collision(target_pos)
        dist = math.sqrt(sum((safe_pos[i] - target_pos[i]) ** 2 for i in range(3)))
        if dist <= max_distance:
            return safe_pos
        if dist > 1e-6:
            factor = max_distance / dist
            return [target_pos[i] + (safe_pos[i] - target_pos[i]) * factor for i in range(3)]
        return list(target_pos)

    def get_collision_info(self):
        return list(self.collision_events)