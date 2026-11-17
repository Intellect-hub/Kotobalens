
import json
import urllib.request


ANKI_URL = "http://127.0.0.1:8765"

DECK_NAME = "Japanese Subtitle Helper"
MODEL_NAME = "Japanese Subtitle Vocabulary"


def anki_request(action, params=None):
    payload = {
        "action": action,
        "version": 6,
        "params": params or {},
    }

    request = urllib.request.Request(
        ANKI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(
        request,
        timeout=5,
    ) as response:
        data = json.load(response)

    if data.get("error"):
        raise RuntimeError(data["error"])

    return data.get("result")


def main():
    print("Setting up Japanese Subtitle Helper in Anki...\n")

    # Create a separate deck.
    deck_id = anki_request(
        "createDeck",
        {"deck": DECK_NAME},
    )

    print(f"Deck ready: {DECK_NAME}")
    print(f"Deck ID: {deck_id}")

    # Avoid creating the same note type twice.
    existing_models = anki_request("modelNames")

    if MODEL_NAME in existing_models:
        print(f"Note type already exists: {MODEL_NAME}")
        print("\nSetup complete!")
        return

    # Create a custom vocabulary note type.
    anki_request(
        "createModel",
        {
            "modelName": MODEL_NAME,
            "inOrderFields": [
                "Japanese",
                "Reading",
                "Meaning",
                "AI Explanation",
                "Japanese Sentence",
                "English Translation",
            ],
            "css": """
.card {
    font-family: Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #222;
    background-color: #fafafa;
}

.japanese {
    font-size: 36px;
    margin-bottom: 12px;
}

.reading {
    font-size: 22px;
    color: #666;
}

.sentence {
    font-size: 21px;
    margin-top: 15px;
}

.explanation {
    font-size: 17px;
    text-align: left;
    line-height: 1.6;
}
""",
            "cardTemplates": [
                {
                    "Name": "Japanese Vocabulary",
                    "Front": """
<div class="japanese">{{Japanese}}</div>
<div class="sentence">{{Japanese Sentence}}</div>
""",
                    "Back": """
{{FrontSide}}
<hr id="answer">

<div class="reading">{{Reading}}</div>

<h3>{{Meaning}}</h3>

<div class="explanation">
{{AI Explanation}}
</div>

<hr>

<div class="sentence">
{{English Translation}}
</div>
""",
                }
            ],
        },
    )

    print(f"Note type created: {MODEL_NAME}")
    print("\nSetup complete!")


if __name__ == "__main__":
    main()
