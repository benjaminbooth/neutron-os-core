"""Integration tests for the voice memo channel.

Tests the sense serve HTTP server with real file uploads:
  1. Upload a voice memo (.m4a) via HTTP — does it route correctly?
  2. Submit a text note — does it land in the inbox?
  3. Status endpoint — does it reflect the inbox state?

No external credentials needed — this tests the local HTTP server.
"""

import json
import threading
import urllib.request
import urllib.parse
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.voice]


@pytest.fixture
def inbox(tmp_path):
    inbox_dir = tmp_path / "inbox" / "raw"
    inbox_dir.mkdir(parents=True)
    return inbox_dir


@pytest.fixture
def server(inbox):
    from neutron_os.extensions.builtins.sense_agent.serve import create_server

    srv = create_server(host="127.0.0.1", port=0, inbox_root=inbox)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()


def _url(server, path="/"):
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


class TestVoiceMemoUpload:
    """Simulate uploading a voice memo from iPhone."""

    def test_upload_m4a(self, server, inbox):
        """Upload a .m4a file — should route to inbox/raw/voice/."""
        # Create a fake .m4a file (real transcription test needs whisper)
        fake_audio = b"\x00" * 1024  # Placeholder bytes

        _boundary = "----VoiceTest123"
        body = (
            "------VoiceTest123\r\n"
            'Content-Disposition: form-data; name="file"; filename="meeting_notes.m4a"\r\n'
            "Content-Type: audio/mp4\r\n"
            "\r\n"
        ).encode() + fake_audio + b"\r\n------VoiceTest123--\r\n"

        req = urllib.request.Request(
            _url(server, "/upload"),
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=----VoiceTest123"},
            method="POST",
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())

        assert "Saved" in result["message"]
        assert (inbox / "voice" / "meeting_notes.m4a").exists()
        print(f"  Voice memo routed: {result['message']}")


class TestQuickNote:
    """Simulate sending a quick note from a phone browser."""

    def test_note_via_browser(self, server, inbox):
        """POST a note via the /note endpoint — simulates the HTML form."""
        text = "Talked to Dr. Smith about the TRIGA thermal hydraulics model. Need to update the boundary conditions before the next review."
        data = urllib.parse.urlencode({"text": text}).encode()

        req = urllib.request.Request(
            _url(server, "/note"),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())

        assert "Note saved" in result["message"]

        # Verify it's a proper markdown note
        notes = list(inbox.glob("note_*.md"))
        assert len(notes) == 1
        content = notes[0].read_text()
        assert "TRIGA thermal hydraulics" in content
        assert "# Note" in content
        print(f"  Note saved: {notes[0].name}")

    def test_status_reflects_inbox(self, server, inbox):
        """After adding files, /status reflects the counts."""
        # Add a note
        data = urllib.parse.urlencode({"text": "Test note"}).encode()
        req = urllib.request.Request(
            _url(server, "/note"),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        urllib.request.urlopen(req)

        # Check status
        resp = urllib.request.urlopen(_url(server, "/status"))
        status = json.loads(resp.read())

        assert status["counts"].get("root", 0) >= 1
        print(f"  Status: {status['counts']}")


class TestUploadPage:
    """Verify the web UI is accessible for phone browsers."""

    def test_html_page_loads(self, server):
        """The upload page should work on a phone browser via LAN."""
        resp = urllib.request.urlopen(_url(server, "/"))
        html = resp.read().decode()

        assert "Neutron OS" in html
        assert "<html" in html
        print("  Upload page renders correctly")
