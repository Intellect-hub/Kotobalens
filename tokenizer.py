
from sudachipy import dictionary, tokenizer
import unicodedata


# Load the Japanese dictionary once
japanese_tokenizer = dictionary.Dictionary().create()


def katakana_to_hiragana(text):
    """Convert katakana readings into hiragana."""
    result = ""

    for character in text:
        code = ord(character)

        if 0x30A1 <= code <= 0x30F6:
            result += chr(code - 0x60)
        else:
            result += character

    return result


def split_japanese(text):
    """Separate Japanese text into words and readings."""
    words = []

    morphemes = japanese_tokenizer.tokenize(
        text,
        tokenizer.Tokenizer.SplitMode.C
    )

    for morpheme in morphemes:
        original = morpheme.surface()
        reading = morpheme.reading_form()

        if reading == "*":
            reading = original

        words.append({
            "word": original,
            "reading": katakana_to_hiragana(reading),
            "dictionary_form": morpheme.dictionary_form()
        })

    return words


if __name__ == "__main__":
    sentence = "今日は日本語を勉強します。"

    print("\n--- JAPANESE WORDS ---\n")

    for item in split_japanese(sentence):
        print(
            f"{item['word']} → "
            f"{item['reading']} "
            f"(dictionary: {item['dictionary_form']})"
        )
