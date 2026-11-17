
import gzip
import os
import xml.etree.ElementTree as ET


DICTIONARY_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "JMdict_e.gz"
)

# Store dictionary entries in memory
japanese_dictionary = {}


def load_dictionary():
    """Load Japanese-English meanings from JMdict."""
    global japanese_dictionary

    if japanese_dictionary:
        return

    if not os.path.exists(DICTIONARY_PATH):
        raise FileNotFoundError(
            f"Dictionary file not found: {DICTIONARY_PATH}"
        )

    print("Loading Japanese-English dictionary...")

    with gzip.open(DICTIONARY_PATH, "rb") as file:
        for event, element in ET.iterparse(
            file,
            events=("end",)
        ):
            if element.tag != "entry":
                continue

            # Japanese written forms
            written_forms = [
                node.text
                for node in element.findall("k_ele/keb")
                if node.text
            ]

            # Japanese readings
            readings = [
                node.text
                for node in element.findall("r_ele/reb")
                if node.text
            ]

            # English definitions
            meanings = []

            for sense in element.findall("sense"):
                for gloss in sense.findall("gloss"):
                    if gloss.text:
                        language = gloss.get(
                            "{http://www.w3.org/XML/1998/namespace}lang",
                            "eng"
                        )

                        if language in ("eng", "en"):
                            meanings.append(gloss.text)

            if meanings:
                entry = {
                    "reading": readings[0] if readings else "",
                    "meanings": meanings[:5]
                }

                for word in written_forms + readings:
                    if word not in japanese_dictionary:
                        japanese_dictionary[word] = entry

            element.clear()

    print(
        f"Dictionary loaded: "
        f"{len(japanese_dictionary)} searchable forms."
    )


def lookup_word(word):
    """Return a Japanese word's dictionary information."""
    load_dictionary()

    result = japanese_dictionary.get(word)

    if result is None:
        return {
            "word": word,
            "reading": "",
            "meanings": ["Meaning not found."]
        }

    return {
        "word": word,
        "reading": result["reading"],
        "meanings": result["meanings"]
    }


if __name__ == "__main__":
    load_dictionary()

    test_words = [
        "勉強",
        "日本語",
        "今日",
        "利益"
    ]

    print("\n--- DICTIONARY TEST ---\n")

    for word in test_words:
        result = lookup_word(word)

        print(f"Word: {result['word']}")
        print(f"Reading: {result['reading']}")
        print(
            "Meanings: "
            + "; ".join(result["meanings"])
        )
        print()
