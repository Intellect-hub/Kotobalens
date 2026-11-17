import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

ANKI_URL = "http://127.0.0.1:8765"
DECK_NAME = "Japanese Subtitle Helper"
WORD_MODEL = "Japanese Subtitle Vocabulary"
SENTENCE_MODEL = "Japanese Subtitle Sentence"


def _send_anki_request(action, params=None, timeout=3):
    payload = {"action": action, "version": 6, "params": params or {}}
    request = urllib.request.Request(
        ANKI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data.get("result")


def _find_anki_executable():
    """Find a Windows Anki installation without relying on the current directory."""
    candidates = []
    for name in ("anki.exe", "anki"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for env_name in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        root = os.environ.get(env_name)
        if root:
            candidates.append(Path(root) / "Programs" / "Anki" / "anki.exe")
            candidates.append(Path(root) / "Anki" / "anki.exe")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def ensure_anki_running():
    """Start Anki if needed, then wait for AnkiConnect to become available."""
    try:
        _send_anki_request("version", timeout=2)
        return
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        pass

    executable = _find_anki_executable()
    if executable is None:
        raise RuntimeError(
            "Cannot connect to AnkiConnect, and Anki could not be found. "
            "Install Anki and the AnkiConnect add-on (code 2055492159), "
            "then try again. If Anki is installed in a custom folder, "
            "open it manually once."
        )

    try:
        subprocess.Popen(
            [str(executable)],
            cwd=str(executable.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        raise RuntimeError(f"Could not launch Anki: {error}") from error

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            _send_anki_request("version", timeout=2)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(1)

    raise RuntimeError(
        "Anki was launched, but AnkiConnect did not become available within 60 seconds. "
        "Check that Anki has finished opening, a profile is selected, "
        "and AnkiConnect (add-on code 2055492159) is enabled."
    )


def anki_request(action, params=None):
    ensure_anki_running()
    return _send_anki_request(action, params, timeout=5)


def safe(value):
    return html.escape(str(value or "")).replace("\n", "<br>")


def setup_word_template():
    """Update the existing word card template."""
    templates = anki_request("modelTemplates", {"modelName": WORD_MODEL})
    template_name = next(iter(templates))
    anki_request(
        "updateModelTemplates",
        {"model": {"name": WORD_MODEL, "templates": {template_name: {
            "Front": '''
<div style="font-size: 38px;">
{{Japanese}}
</div>
''',
            "Back": '''
{{FrontSide}}
<hr id="answer">
<div style="font-size: 25px;">
{{Reading}}
</div>
<div style="font-size: 23px; margin-top: 15px;">
{{Meaning}}
</div>
''',
        }}}},
    )


def setup_sentence_model():
    """Create the sentence note type if needed."""
    anki_request("createDeck", {"deck": DECK_NAME})
    models = anki_request("modelNames")
    if SENTENCE_MODEL in models:
        return
    anki_request(
        "createModel",
        {
            "modelName": SENTENCE_MODEL,
            "inOrderFields": ["Japanese Sentence", "English Translation"],
            "css": '''
.card {
    font-family: Arial, sans-serif;
    font-size: 22px;
    text-align: center;
    line-height: 1.7;
}
''',
            "cardTemplates": [{
                "Name": "Sentence Reading",
                "Front": '''
<div style="font-size: 30px;">
{{Japanese Sentence}}
</div>
''',
                "Back": '''
{{FrontSide}}
<hr id="answer">
<div style="font-size: 23px;">
{{English Translation}}
</div>
''',
            }],
        },
    )


def save_word(word, reading, meaning, explanation, japanese_sentence, english_translation):
    """Save only the word, reading, and English meaning."""
    setup_word_template()
    note = {
        "deckName": DECK_NAME,
        "modelName": WORD_MODEL,
        "fields": {
            "Japanese": safe(word),
            "Reading": safe(reading),
            "Meaning": safe(meaning),
            "AI Explanation": "",
            "Japanese Sentence": "",
            "English Translation": "",
        },
        "options": {"allowDuplicate": False, "duplicateScope": "deck"},
        "tags": ["JapaneseSubtitleHelper", "Vocabulary"],
    }
    return anki_request("addNote", {"note": note})


def save_sentence(japanese_sentence, english_translation):
    """Save a complete Japanese sentence."""
    setup_sentence_model()
    note = {
        "deckName": DECK_NAME,
        "modelName": SENTENCE_MODEL,
        "fields": {
            "Japanese Sentence": safe(japanese_sentence),
            "English Translation": safe(english_translation),
        },
        "options": {"allowDuplicate": False, "duplicateScope": "deck"},
        "tags": ["JapaneseSubtitleHelper", "Sentence"],
    }
    return anki_request("addNote", {"note": note})
