"""Exercise all nine real lab adapters without activating the microphone."""

import hashlib
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from webapp.server import create_app
from webapp.workspace import ROOT, write_json


def main() -> None:
    original = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "lab5_7/data/raw").glob("*.wav")
    }
    folder = ROOT / "webapp/work/verification" / uuid4().hex
    results = []
    with TestClient(create_app(folder)) as client:
        cases = [
            (1, {"action": "demo"}),
            (1, {"action": "search", "query": "python programming"}),
            (1, {"action": "evaluate"}),
            (2, {"demo": True, "settings": {"repetitions": 1}}),
            (3, {"demo": True, "sentences": 3, "keywords": 5}),
            (
                4,
                {
                    "text": "Art connects people. Literature preserves cultural memory.",
                    "domain": "art",
                },
            ),
            (5, {"action": "crop", "source": "vowels", "start": 3.0125, "end": 3.2525}),
            (6, {"action": "permutations", "prefix": "word"}),
            (
                6,
                {
                    "source": "student",
                    "segment": "student_phrase",
                    "method": "psola",
                    "controls": {"pitch_points": [[0, 100], [2.08, 130]]},
                },
            ),
            (7, {"recipe": "ref3_syllables", "crossfade_ms": 0}),
            (
                8,
                {
                    "text": "Bonjour. La littérature nous aide à comprendre le monde.",
                    "voice": "siwis",
                },
            ),
            (9, {"language": "fr"}),
        ]
        for lab, body in cases:
            print("RUN", lab, body.get("action", "experiment"), flush=True)
            response = client.post(
                f"/api/labs/{lab}/run", headers={"X-Eyazis": "local"}, json=body
            )
            response.raise_for_status()
            ident = response.json()["id"]
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                state = client.get("/api/jobs/" + ident).json()
                if state["status"] not in {"queued", "running", "cancelling"}:
                    break
                time.sleep(0.1)
            assert state["status"] == "completed", state
            result = state["result"]
            assert client.get(result["json"]).status_code == 200
            if result.get("report"):
                assert client.get(result["report"]).status_code == 200
            if result.get("audio"):
                audio = client.get(result["audio"])
                assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
            assert client.get("/api/jobs/" + ident + "/archive").status_code == 200
            results.append(
                {"lab": lab, "job": ident, "kind": result["kind"], "status": "PASS"}
            )
            print("PASS", lab, result["kind"], flush=True)
        assert not client.get("/api/live").json()["active"]
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == digest
        for p, digest in original.items()
    )
    write_json(
        folder / "verification.json",
        {
            "checks": results,
            "source_recordings_unchanged": len(original),
            "microphone_activated": False,
        },
    )
    print(
        "All nine labs verified; source recordings unchanged:",
        len(original),
        flush=True,
    )
    print(folder)


if __name__ == "__main__":
    main()
