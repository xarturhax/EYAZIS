import io
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient

from webapp.jobs import Jobs
from webapp.server import create_app

HEADERS = {"X-Eyazis": "local"}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.app = create_app(self.folder)
        self.client = TestClient(self.app).__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temporary.cleanup()

    def run_job(self, lab, body):
        response = self.client.post(f"/api/labs/{lab}/run", json=body, headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.text)
        ident = response.json()["id"]
        for _ in range(300):
            state = self.client.get("/api/jobs/" + ident).json()
            if state["status"] not in {"running", "queued", "cancelling"}:
                self.assertEqual(state["status"], "completed", state)
                return state
            time.sleep(0.02)
        self.fail("Job timeout")

    def test_health_and_catalog_do_not_open_microphone(self):
        with patch("sounddevice.RawInputStream") as microphone:
            self.assertEqual(self.client.get("/api/health").json()["app"], "eyazis-web")
            data = self.client.get("/api/catalog").json()
            self.assertEqual(len(data["materials"]), 9)
            self.assertEqual(len(data["recipes"]), 8)
            self.assertFalse(self.client.get("/api/live").json()["active"])
            microphone.assert_not_called()

    def test_search_evaluation_export_and_private_database(self):
        self.run_job(1, {"action": "demo"})
        state = self.run_job(1, {"action": "search", "query": "python programming"})
        self.assertTrue(state["result"]["rows"])
        self.assertTrue((self.folder / "search.sqlite3").is_file())
        self.assertEqual(self.client.get(state["result"]["json"]).status_code, 200)
        report = self.run_job(1, {"action": "evaluate"})
        self.assertTrue(report["result"]["data"]["averages"])
        self.assertEqual(self.client.get(report["result"]["report"]).status_code, 200)
        archive = self.client.get("/api/jobs/" + report["id"] + "/archive")
        with ZipFile(io.BytesIO(archive.content)) as stream:
            self.assertIn("report/report.html", stream.namelist())
            self.assertIn("request.json", stream.namelist())

    def test_collection_reads_and_worker_writes_do_not_race_schema_initialization(self):
        response = self.client.post(
            "/api/labs/1/run", json={"action": "demo"}, headers=HEADERS
        )
        ident = response.json()["id"]
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(lambda _: self.client.get("/api/lab1/data"), range(15))
            )
        self.assertTrue(all(result.status_code == 200 for result in results))
        for _ in range(100):
            state = self.client.get("/api/jobs/" + ident).json()
            if state["status"] != "queued" and state["status"] != "running":
                break
            time.sleep(0.02)
        self.assertEqual(state["status"], "completed", state)

    def test_upload_uses_opaque_id_and_rejects_empty_or_executable(self):
        response = self.client.post(
            "/api/uploads",
            files={"file": ("../../original.txt", b"example")},
            headers=HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        uploaded = response.json()
        self.assertEqual(
            self.app.state.workspace.upload(uploaded["id"]).read_bytes(), b"example"
        )
        self.assertEqual(self.client.get(uploaded["url"]).content, b"example")
        for name, data in [("evil.exe", b"bad"), ("empty.txt", b"")]:
            self.assertEqual(
                self.client.post(
                    "/api/uploads", files={"file": (name, data)}, headers=HEADERS
                ).status_code,
                400,
            )

    def test_file_traversal_database_and_external_origins_rejected(self):
        for path in [
            "/files/work/search.sqlite3",
            "/files/lab1/../requirements.txt",
            "/files/work/%2E%2E/%2E%2E/.env",
            "/files/unknown/a.txt",
        ]:
            self.assertNotEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(
            self.client.post("/api/labs/1/run", json={"action": "demo"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/labs/1/run",
                json={},
                headers={**HEADERS, "Origin": "https://outside.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/health", headers={"Host": "outside.example"}
            ).status_code,
            403,
        )

    def test_policy_validation_does_not_overwrite_good_configuration(self):
        previous = (self.folder / "commands.json").read_bytes()
        self.assertEqual(
            self.client.post(
                "/api/commands", json={"schema": 99}, headers=HEADERS
            ).status_code,
            400,
        )
        self.assertEqual((self.folder / "commands.json").read_bytes(), previous)
        policy = json.loads(previous)
        policy["threshold"] = 0.8
        self.assertEqual(
            self.client.post("/api/commands", json=policy, headers=HEADERS).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/commands").json()["threshold"], 0.8)

    def test_microphone_requires_explicit_start_and_stops_with_session(self):
        started = Event()

        def listen(engine, language, device, emit, progress, cancelled, paused):
            started.set()
            while not cancelled():
                time.sleep(0.01)

        with patch("lab9.infrastructure.recognizer.VoskEngine.listen", listen):
            self.assertFalse(started.is_set())
            response = self.client.post(
                "/api/live/start", json={"language": "fr"}, headers=HEADERS
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(started.wait(2))
            self.client.post(
                "/api/live/heartbeat", json={"paused": True}, headers=HEADERS
            )
            self.assertTrue(self.client.get("/api/live").json()["paused"])
            self.client.post("/api/live/stop", json={}, headers=HEADERS)
            self.assertFalse(self.client.get("/api/live").json()["active"])

    def test_uploaded_wav_crop_has_http_playback_and_exact_duration(self):
        import numpy as np
        import soundfile as sf

        data = io.BytesIO()
        samples = 0.1 * np.sin(2 * np.pi * 100 * np.arange(16000) / 16000)
        sf.write(data, samples, 16000, format="WAV", subtype="PCM_16")
        response = self.client.post(
            "/api/uploads",
            files={"file": ("tone.wav", data.getvalue())},
            headers=HEADERS,
        )
        state = self.run_job(
            5,
            {
                "action": "crop",
                "upload": response.json()["id"],
                "start": 0.2,
                "end": 0.44,
            },
        )
        self.assertAlmostEqual(state["result"]["data"]["duration"], 0.24, places=5)
        html = self.client.get(state["result"]["report"]).text
        self.assertNotIn("file:///", html)
        self.assertEqual(self.client.get(state["result"]["audio"]).content[:4], b"RIFF")

    def test_invalid_experiment_records_error_without_crashing_api(self):
        response = self.client.post(
            "/api/labs/7/run", json={"crossfade_ms": 500}, headers=HEADERS
        )
        ident = response.json()["id"]
        for _ in range(100):
            state = self.client.get("/api/jobs/" + ident).json()
            if state["status"] == "failed":
                break
            time.sleep(0.02)
        self.assertEqual(state["status"], "failed")
        self.assertTrue(state["error"])
        self.assertEqual(
            self.client.get("/api/jobs/" + ident + "/archive").status_code, 409
        )

    def test_journal_export_and_history_survive_new_app(self):
        job = self.run_job(
            9,
            {
                "action": "journal",
                "rows": [{"text": "<script>bad()</script>", "status": "UNKNOWN"}],
            },
        )
        page = self.client.get(job["result"]["report"]).text
        self.assertNotIn("<script>bad()", page)
        other = create_app(self.folder)
        try:
            with TestClient(other) as client:
                self.assertEqual(
                    client.get("/api/jobs/" + job["id"]).json()["status"], "completed"
                )
        finally:
            other.state.jobs.close()


class JobTests(unittest.TestCase):
    def test_cancellation_does_not_publish_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            jobs = Jobs(Path(temporary))
            started = Event()

            def work(job):
                started.set()
                job.cancel.wait(2)
                job.checkpoint()
                return {"should_not": "publish"}

            job = jobs.submit(1, "test", work)
            self.assertTrue(started.wait(2))
            jobs.items[job["id"]].cancel.set()
            jobs.close()
            result = jobs.get(job["id"])
            self.assertEqual(result["status"], "cancelled")
            self.assertIsNone(result["result"])

    def test_interrupted_jobs_are_visible_after_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            ident = "a" * 32
            (folder / ident).mkdir()
            (folder / ident / "state.json").write_text(
                json.dumps({"id": ident, "status": "running"}), encoding="utf-8"
            )
            jobs = Jobs(folder)
            self.assertEqual(jobs.get(ident)["status"], "interrupted")
            jobs.close()


if __name__ == "__main__":
    unittest.main()
