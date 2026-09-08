# task_state_manager.py
"""
RECTIFIED v4.0 - Task State Manager

Manages the complete VR task sequence:
Rest → Reach → Grasp → Lift → Transport → Placement → Release → Return

Full 8-phase task workflow with automatic state transitions, timing,
and real-time task logging for CSV data capture.
"""

import time
import math
import logging

logging.basicConfig(level=logging.INFO)


class TaskPhase:
    """Enum-like class for task phases"""
    REST = "REST"
    REACH = "REACH"
    GRASP = "GRASP"
    LIFT = "LIFT"
    TRANSPORT = "TRANSPORT"
    PLACEMENT = "PLACEMENT"
    RELEASE = "RELEASE"
    RETURN = "RETURN"
    DONE = "DONE"


class TaskStateManager:
    """
    Manages the 8-phase VR task sequence with automatic state transitions,
    timing thresholds, and real-time task phase logging.
    
    Phases:
    1. REST           - Hand idle at pickup position over Table 1 bottle
    2. REACH          - Hand moving toward bottle (within approach distance)
    3. GRASP          - Fingers closing on bottle (high flex, contacts registered)
    4. LIFT           - Bottle being lifted (detected via upward hand motion)
    5. TRANSPORT      - Bottle moving to Table2 (crossing boundary)
    6. PLACEMENT      - Hand positioned at Table2 drop zone
    7. RELEASE        - Fingers opening, bottle released and placed
    8. RETURN         - Hand returning to initial pickup pose
    9. DONE           - Task sequence complete
    """

    def __init__(self, table1_center, table2_center, bottle_radius=0.09,
                 bottle_height=0.45, pickup_radius=0.15, place_radius=0.18,
                 reach_distance=0.50, table_thickness=0.08):
        self.table1 = list(table1_center)
        self.table2 = list(table2_center)
        self.bottle_radius = bottle_radius
        self.bottle_height = bottle_height
        self.pickup_radius = pickup_radius
        self.place_radius = place_radius
        self.reach_distance = reach_distance
        self.table_thickness = table_thickness

        # State tracking
        self.phase = TaskPhase.REST
        self._phase_start_time = time.time()
        self._last_announced_phase = None
        self._phase_history = []

        # Grasp state
        self.is_grasping = False
        self.grasp_start_time = None
        self.grasp_threshold = 0.55
        self.release_threshold = 0.25
        self.min_finger_contacts = 2

        # Lift detection
        self._lift_start_y = None
        self._lift_threshold = 0.08  # 8cm upward motion required to trigger LIFT
        self._lift_detected = False

        # Transport detection
        self._transport_started = False
        self._transport_start_time = None

        logging.info(f"\n✓ TaskStateManager initialized")
        logging.info(f"  Table1 Center: {self.table1}")
        logging.info(f"  Table2 Center: {self.table2}")
        logging.info(f"  Pickup Radius: {self.pickup_radius}m")
        logging.info(f"  Place Radius: {self.place_radius}m")
        logging.info(f"  Reach Distance: {self.reach_distance}m\n")

    @staticmethod
    def _distance(a, b):
        """Compute Euclidean distance between two 3D points"""
        if not a or not b or len(a) < 3 or len(b) < 3:
            return float('inf')
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    @staticmethod
    def _horizontal_distance(a, b):
        """Compute horizontal (XZ) distance, ignoring Y"""
        if not a or not b or len(a) < 3 or len(b) < 3:
            return float('inf')
        return math.sqrt((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2)

    def get_bottle_rest_pos(self):
        """Position of bottle resting on Table1"""
        return [
            self.table1[0],
            self.table1[1] + self.table_thickness / 2.0 + self.bottle_height / 2.0,
            self.table1[2],
        ]

    def get_bottle_placed_pos(self):
        """Position of bottle resting on Table2"""
        return [
            self.table2[0],
            self.table2[1] + self.table_thickness / 2.0 + self.bottle_height / 2.0,
            self.table2[2],
        ]

    def get_phase(self):
        """Get current task phase"""
        return self.phase

    def get_phase_elapsed(self):
        """Get elapsed time in current phase (seconds)"""
        return time.time() - self._phase_start_time

    def get_phase_info(self):
        """Get human-readable phase info for HUD"""
        phase_messages = {
            TaskPhase.REST: "[1/8] REST - Hand idle, ready to approach bottle",
            TaskPhase.REACH: "[2/8] REACH - Move toward bottle on Table 1",
            TaskPhase.GRASP: "[3/8] GRASP - Squeeze glove to grip bottle",
            TaskPhase.LIFT: "[4/8] LIFT - Pull hand upward to lift bottle",
            TaskPhase.TRANSPORT: "[5/8] TRANSPORT - Carry bottle to Table 2",
            TaskPhase.PLACEMENT: "[6/8] PLACEMENT - Position over drop zone at Table 2",
            TaskPhase.RELEASE: "[7/8] RELEASE - Open hand to place bottle",
            TaskPhase.RETURN: "[8/8] RETURN - Hand returning to initial position",
            TaskPhase.DONE: "COMPLETE - Task cycle finished! Press C to restart.",
        }
        return phase_messages.get(self.phase, "UNKNOWN")

    def update(self, palm_pos, hand_pos, grasp_amt, contacts, bottle_pos, is_returning=False):
        """
        Update task state based on current hand/bottle positions and flex state.
        Should be called every frame (~50 Hz).

        Args:
            palm_pos: Current palm center position [x, y, z]
            hand_pos: Current hand/wrist position [x, y, z]
            grasp_amt: Grasp amount (0-1), weighted flex value
            contacts: Number of finger contacts on bottle
            bottle_pos: Current bottle position [x, y, z]
            is_returning: True if the hand is in scripted return animation
        """
        if not palm_pos or not hand_pos or not bottle_pos:
            return

        bottle_rest = self.get_bottle_rest_pos()
        dist_to_bottle = self._distance(palm_pos, bottle_rest)
        horiz_dist_table2 = self._horizontal_distance(hand_pos, self.table2)
        horiz_dist_table1 = self._horizontal_distance(hand_pos, self.table1)
        bottle_height = bottle_pos[1]
        table1_top_y = self.table1[1] + self.table_thickness / 2.0

        # State machine transitions
        if self.phase == TaskPhase.REST:
            # REST → REACH: Hand approaches bottle
            if dist_to_bottle < self.reach_distance:
                self._transition_to_phase(TaskPhase.REACH)

        elif self.phase == TaskPhase.REACH:
            # REACH → GRASP: Hand gets close enough and starts grasping
            if (dist_to_bottle < self.pickup_radius and 
                grasp_amt >= self.grasp_threshold and 
                contacts >= self.min_finger_contacts):
                self._transition_to_phase(TaskPhase.GRASP)
                self.is_grasping = True
                self.grasp_start_time = time.time()
                self._lift_start_y = hand_pos[1]  # Remember starting height
                self._lift_detected = False
            # REACH → REST: Hand moved away
            elif dist_to_bottle > self.reach_distance + 0.1:
                self._transition_to_phase(TaskPhase.REST)

        elif self.phase == TaskPhase.GRASP:
            # GRASP → LIFT: Bottle lifted (hand Y increased by threshold)
            if self._lift_start_y is not None:
                current_lift = hand_pos[1] - self._lift_start_y
                if current_lift > self._lift_threshold:
                    self._transition_to_phase(TaskPhase.LIFT)
                    self._lift_detected = True
                    self._transport_started = False
            # GRASP → REACH: Hand releases before lifting
            if grasp_amt < self.release_threshold:
                self._transition_to_phase(TaskPhase.REACH)
                self.is_grasping = False

        elif self.phase == TaskPhase.LIFT:
            # LIFT → TRANSPORT: Bottle crosses horizontal boundary toward Table2
            if horiz_dist_table2 < horiz_dist_table1 - 0.3:
                self._transition_to_phase(TaskPhase.TRANSPORT)
                self._transport_started = True
                self._transport_start_time = time.time()
            # LIFT → GRASP: Hand lowers bottle back down
            elif self._lift_start_y is not None and (hand_pos[1] - self._lift_start_y) < self._lift_threshold * 0.5:
                self._transition_to_phase(TaskPhase.GRASP)
            # LIFT → REACH: Hand releases
            if grasp_amt < self.release_threshold:
                self._transition_to_phase(TaskPhase.REACH)
                self.is_grasping = False

        elif self.phase == TaskPhase.TRANSPORT:
            # TRANSPORT → PLACEMENT: Hand approaches Table2 drop zone
            if horiz_dist_table2 < self.place_radius:
                self._transition_to_phase(TaskPhase.PLACEMENT)
            # TRANSPORT → LIFT: Hand moves back toward Table1
            elif horiz_dist_table2 > horiz_dist_table1:
                self._transition_to_phase(TaskPhase.LIFT)
            # TRANSPORT → REACH: Hand releases mid-transit
            if grasp_amt < self.release_threshold:
                self._transition_to_phase(TaskPhase.REACH)
                self.is_grasping = False

        elif self.phase == TaskPhase.PLACEMENT:
            # PLACEMENT → RELEASE: Hand opens (release detected)
            if grasp_amt < self.release_threshold:
                self._transition_to_phase(TaskPhase.RELEASE)
                self.is_grasping = False
            # PLACEMENT → TRANSPORT: Hand moves away
            elif horiz_dist_table2 > self.place_radius + 0.1:
                self._transition_to_phase(TaskPhase.TRANSPORT)

        elif self.phase == TaskPhase.RELEASE:
            # RELEASE → RETURN: Bottle released, hand starts returning home
            if is_returning:
                self._transition_to_phase(TaskPhase.RETURN)

        elif self.phase == TaskPhase.RETURN:
            # RETURN → DONE: Hand arrived back at pickup position
            if not is_returning:
                self._transition_to_phase(TaskPhase.DONE)

        elif self.phase == TaskPhase.DONE:
            # DONE → REST: Task cycle complete, ready for next cycle
            if time.time() - self._phase_start_time > 2.0:  # Show DONE for 2 seconds
                self._transition_to_phase(TaskPhase.REST)

    def _transition_to_phase(self, new_phase):
        """Transition to a new phase with logging"""
        if new_phase == self.phase:
            return  # Already in this phase

        elapsed = self.get_phase_elapsed()
        self._phase_history.append({
            'from': self.phase,
            'to': new_phase,
            'duration': elapsed,
            'timestamp': time.time(),
        })

        old_phase = self.phase
        self.phase = new_phase
        self._phase_start_time = time.time()

        msg = f"[TASK STATE] {old_phase:12s} → {new_phase:12s} (elapsed {elapsed:6.2f}s)"
        logging.info(msg)

    def can_grasp(self, palm_pos, bottle_pos):
        """Check if grasp is allowed at current position"""
        # Can only grasp in REST or REACH phases, near the bottle
        if self.phase not in (TaskPhase.REST, TaskPhase.REACH):
            return False
        dist = self._distance(palm_pos, bottle_pos)
        return dist <= self.pickup_radius

    def can_place(self, hand_pos):
        """Check if placement is valid at current position"""
        # Can only place in PLACEMENT phase, near Table2
        if self.phase not in (TaskPhase.PLACEMENT,):
            return False
        horiz_dist = self._horizontal_distance(hand_pos, self.table2)
        return horiz_dist <= self.place_radius

    def get_phase_history(self):
        """Get list of completed phases for logging"""
        return list(self._phase_history)