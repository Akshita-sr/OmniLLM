"""Tests for omnillm.robotics.gesture_planner — GesturePlanner."""

from __future__ import annotations

import pytest

from omnillm.robotics.bridge import RobotAction
from omnillm.robotics.gesture_planner import GESTURE_LED_COLORS, GesturePlanner


class TestGesturePlanner:
    def setup_method(self):
        self.planner = GesturePlanner()

    # ── plan() ────────────────────────────────────────────────────────────────

    def test_plan_returns_tuple(self):
        gesture, led = self.planner.plan("info_retrieval", "The lab opens at 9 AM.")
        assert isinstance(gesture, str)
        assert isinstance(led, str)
        assert led.startswith("#")

    def test_plan_navigation_left(self):
        gesture, led = self.planner.plan("navigation", "Turn left at the end of the corridor.")
        assert gesture == "point_left"

    def test_plan_navigation_right(self):
        gesture, led = self.planner.plan("navigation", "The room is on your right.")
        assert gesture == "point_right"

    def test_plan_navigation_forward(self):
        gesture, led = self.planner.plan("navigation", "Go straight ahead to reach the cafeteria.")
        assert gesture == "point_forward"

    def test_plan_navigation_upstairs(self):
        gesture, led = self.planner.plan("navigation", "The seminar room is upstairs on floor 3.")
        assert gesture == "point_up"

    def test_plan_navigation_default_when_no_direction(self):
        gesture, led = self.planner.plan("navigation", "I will guide you to your destination.")
        assert gesture == "point_forward"

    def test_plan_greeting_wave(self):
        gesture, led = self.planner.plan("social_conversation", "Hello! Welcome to the lab.")
        assert gesture == "wave"

    def test_plan_goodbye_wave(self):
        gesture, led = self.planner.plan("social_conversation", "Goodbye, have a great day!")
        assert gesture == "wave_goodbye"

    def test_plan_show_tablet(self):
        gesture, led = self.planner.plan("navigation", "Please look at the map on the screen.")
        assert gesture == "show_tablet"

    def test_plan_thinking(self):
        gesture, led = self.planner.plan("info_retrieval", "Let me check that information.")
        assert gesture == "think"

    def test_plan_uncertain(self):
        gesture, led = self.planner.plan("info_retrieval", "I'm sorry, I don't know the answer.")
        assert gesture == "confused"

    def test_plan_nod_for_affirmation(self):
        gesture, led = self.planner.plan("info_retrieval", "Absolutely, the lab is open today.")
        assert gesture == "nod"

    def test_plan_social_default(self):
        gesture, led = self.planner.plan("social_conversation", "Tell me more about yourself.")
        assert gesture == "wave"

    def test_plan_info_default_is_nod(self):
        # No keyword triggers → default for info_retrieval is "nod"
        gesture, led = self.planner.plan("info_retrieval", "The schedule is available online.")
        assert gesture == "nod"

    def test_plan_led_colour_is_valid_hex(self):
        for task_type in ["info_retrieval", "navigation", "social_conversation", "multilingual"]:
            _, led = self.planner.plan(task_type, "Some response text here for testing.")
            assert led.startswith("#")
            assert len(led) == 7  # #RRGGBB

    # ── plan_action() ─────────────────────────────────────────────────────────

    def test_plan_action_returns_robot_action(self):
        action = self.planner.plan_action("navigation", "Turn left at the corridor.")
        assert isinstance(action, RobotAction)

    def test_plan_action_speech_matches_response(self):
        text = "The lab opens at 9 AM on weekdays."
        action = self.planner.plan_action("info_retrieval", text)
        assert action.speech == text

    def test_plan_action_gesture_set(self):
        action = self.planner.plan_action("navigation", "Turn right past the elevators.")
        assert action.gesture == "point_right"

    def test_plan_action_emotion_led_set(self):
        action = self.planner.plan_action("social_conversation", "Hello! Nice to meet you.")
        assert action.emotion_led is not None
        assert action.emotion_led.startswith("#")

    def test_plan_action_tablet_url_in_metadata(self):
        action = self.planner.plan_action(
            "navigation",
            "The room is on floor 3.",
            tablet_url="http://example.com/map.png",
        )
        assert action.metadata.get("tablet_url") == "http://example.com/map.png"

    def test_plan_action_task_type_in_metadata(self):
        action = self.planner.plan_action("info_retrieval", "Here is the information.")
        assert action.metadata.get("task_type") == "info_retrieval"

    # ── get_navigation_gesture() ──────────────────────────────────────────────

    def test_get_nav_gesture_left(self):
        assert self.planner.get_navigation_gesture("left") == "point_left"

    def test_get_nav_gesture_right(self):
        assert self.planner.get_navigation_gesture("right") == "point_right"

    def test_get_nav_gesture_upstairs(self):
        assert self.planner.get_navigation_gesture("upstairs") == "point_up"

    def test_get_nav_gesture_forward_default(self):
        assert self.planner.get_navigation_gesture("straight") == "point_forward"

    def test_get_nav_gesture_east(self):
        assert self.planner.get_navigation_gesture("east side") == "point_left"

    # ── list_gestures() ──────────────────────────────────────────────────────

    def test_list_gestures_returns_sorted_list(self):
        gestures = GesturePlanner.list_gestures()
        assert isinstance(gestures, list)
        assert len(gestures) > 5
        assert gestures == sorted(gestures)

    def test_list_gestures_includes_key_gestures(self):
        gestures = GesturePlanner.list_gestures()
        for expected in ["wave", "nod", "point_left", "point_right", "point_forward"]:
            assert expected in gestures


class TestGestureLedColors:
    def test_all_gestures_have_led_colors(self):
        for gesture in GesturePlanner.list_gestures():
            assert gesture in GESTURE_LED_COLORS

    def test_all_led_colors_are_hex(self):
        for gesture, color in GESTURE_LED_COLORS.items():
            assert color.startswith("#"), f"{gesture} has invalid LED color: {color}"
            assert len(color) == 7, f"{gesture} has invalid LED color length: {color}"
