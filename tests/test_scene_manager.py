"""Run with: python -m unittest discover tests"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doubly_linked_list import DoublyLinkedList  # noqa: E402


class DoublyLinkedListTests(unittest.TestCase):
    def setUp(self):
        self.dll = DoublyLinkedList()
        for item in "ABC":
            self.dll.append(item)

    def test_append_sets_current_and_links(self):
        self.assertEqual(list(self.dll), ["A", "B", "C"])
        self.assertEqual(self.dll.current.data, "A")
        self.assertEqual(self.dll.tail.prev.data, "B")

    def test_navigation_bounds(self):
        with self.assertRaises(IndexError):
            self.dll.move_previous()
        self.dll.move_next()
        self.dll.move_next()
        with self.assertRaises(IndexError):
            self.dll.move_next()
        self.assertEqual(self.dll.move_previous(), "B")

    def test_insert_after_current_in_middle_and_tail(self):
        self.dll.insert_after_current("X")
        self.assertEqual(list(self.dll), ["A", "X", "B", "C"])
        self.assertIs(self.dll.head.next.next.prev, self.dll.head.next)
        for _ in range(3):
            self.dll.move_next()
        self.dll.insert_after_current("Z")
        self.assertEqual(self.dll.tail.data, "Z")

    def test_remove_current_head_middle_tail(self):
        self.assertEqual(self.dll.remove_current(), "A")
        self.assertEqual((self.dll.head.data, self.dll.current.data), ("B", "B"))
        self.dll.move_next()
        self.assertEqual(self.dll.remove_current(), "C")
        self.assertEqual((self.dll.tail.data, self.dll.current.data), ("B", "B"))
        self.dll.remove_current()
        self.assertTrue(self.dll.is_empty())
        self.assertIsNone(self.dll.current)
        with self.assertRaises(IndexError):
            self.dll.remove_current()


class ApiTests(unittest.TestCase):
    def setUp(self):
        import app as backend
        backend.scenes = DoublyLinkedList()
        backend.seed_scenes()
        self.client = backend.app.test_client()

    def test_full_flow(self):
        data = self.client.get("/api/scenes").get_json()
        self.assertEqual(data["size"], 5)
        self.assertEqual(self.client.post("/api/scenes/previous").status_code, 409)
        data = self.client.post("/api/scenes/next").get_json()
        self.assertTrue(data["scenes"][1]["is_live"])
        res = self.client.post("/api/scenes", json={"name": "Chat", "position": "after_current"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["next_name"], "Chat")
        self.assertEqual(self.client.post("/api/scenes", json={"name": " "}).status_code, 400)
        res = self.client.delete("/api/scenes/current")
        self.assertEqual(res.get_json()["size"], 5)

    def test_obs_api_controls_scenes_and_stream(self):
        import app as backend

        class FakeObsClient:
            def __init__(self):
                self.names = ["Intro", "Webcam"]
                self.current = "Intro"
                self.streaming = False

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def get_scene_list(self):
                return SimpleNamespace(
                    scenes=[{"sceneName": name} for name in self.names],
                    current_program_scene_name=self.current,
                )

            def set_current_program_scene(self, name):
                self.current = name

            def create_scene(self, name):
                self.names.append(name)

            def remove_scene(self, name):
                self.names.remove(name)
                if self.current == name:
                    self.current = self.names[0] if self.names else ""

            def get_version(self):
                return SimpleNamespace(obs_version="31.0")

            def get_stream_status(self):
                return SimpleNamespace(output_active=self.streaming)

            def start_stream(self):
                self.streaming = True

            def stop_stream(self):
                self.streaming = False

        fake_obs = FakeObsClient()
        with patch.dict(os.environ, {"OBS_HOST": "127.0.0.1"}), patch.object(
            backend, "create_obs_client", return_value=fake_obs
        ):
            data = self.client.get("/api/scenes").get_json()
            self.assertEqual(data["mode"], "obs")
            self.assertEqual(data["size"], 2)

            data = self.client.post("/api/scenes/next").get_json()
            self.assertEqual(data["scenes"][1]["name"], "Webcam")
            self.assertTrue(data["scenes"][1]["is_live"])

            res = self.client.post("/api/scenes", json={"name": "Chat"})
            self.assertEqual(res.status_code, 201)
            self.assertEqual(fake_obs.names[-1], "Chat")
            self.assertEqual(
                self.client.post("/api/scenes", json={"name": "Overlay", "position": "after_current"}).status_code,
                400,
            )

            self.assertTrue(self.client.post("/api/stream/start").get_json()["streaming"])
            self.assertTrue(self.client.get("/api/stream/status").get_json()["streaming"])
            self.assertFalse(self.client.post("/api/stream/stop").get_json()["streaming"])


if __name__ == "__main__":
    unittest.main()
