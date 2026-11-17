import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# Keep the existing project .env for development, and support a separate
# per-user .env for installed copies of KotobaLens.
load_dotenv()
USER_ENV_PATH = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'KotobaLens' / '.env'
if USER_ENV_PATH.is_file():
    load_dotenv(dotenv_path=USER_ENV_PATH, override=True)

MODEL_NAME = 'qwen/qwen3.8-27b'
translation_cache = {}
explanation_cache = {}


def _get_client():
    # Read at call time so a user can add their key without an import-time crash.
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        if USER_ENV_PATH.is_file():
            load_dotenv(dotenv_path=USER_ENV_PATH, override=True)
            api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise RuntimeError(
            'Groq API key not found. Create %LOCALAPPDATA%\\KotobaLens\\.env '
            'containing GROQ_API_KEY=your_key, then try again.'
        )
    return Groq(api_key=api_key, timeout=5.0, max_retries=0)


def translate_sentence(japanese_text):
    """Translate a Japanese sentence using Groq."""
    japanese_text = japanese_text.strip()
    if not japanese_text:
        return ''
    if japanese_text in translation_cache:
        print('Translation loaded from cache.')
        return translation_cache[japanese_text]
    start = time.perf_counter()
    response = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are an expert Japanese-to-English '
                    'translator. Translate Japanese subtitles '
                    'accurately and naturally. Preserve the '
                    'original meaning and tone. '
                    'Return only the English translation.'
                ),
            },
            {'role': 'user', 'content': japanese_text},
        ],
        temperature=0,
        max_completion_tokens=150,
    )
    translation = (response.choices[0].message.content or '').strip()
    print(f'Groq translation time: {time.perf_counter() - start:.2f}s')
    if not translation:
        raise RuntimeError('Empty translation response.')
    translation_cache[japanese_text] = translation
    return translation


def explain_word(japanese_sentence, word, reading, dictionary_form):
    """Explain a Japanese word in the context of its sentence."""
    cache_key = (japanese_sentence, word, dictionary_form)
    if cache_key in explanation_cache:
        print('AI explanation loaded from cache.')
        return explanation_cache[cache_key]
    start = time.perf_counter()
    response = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are a helpful Japanese language tutor '
                    'teaching an English-speaking beginner. '
                    'Explain the selected Japanese word or '
                    'grammar element specifically in the '
                    'context of the provided sentence. '
                    'Use clear, simple English. '
                    'Explain its contextual meaning and '
                    'relevant grammar. '
                    'If the word is a particle or verb ending, '
                    'explain its grammatical function. '
                    'Keep the answer concise, around 2-4 '
                    'sentences. Avoid unnecessary kanji.'
                ),
            },
            {
                'role': 'user',
                'content': (
                    f'Full Japanese sentence: {japanese_sentence}\n'
                    f'Selected word: {word}\n'
                    f'Reading: {reading}\n'
                    f'Dictionary form: {dictionary_form}\n\n'
                    'Explain the selected word in this context.'
                ),
            },
        ],
        temperature=0.2,
        max_completion_tokens=250,
    )
    explanation = (response.choices[0].message.content or '').strip()
    print(f'Groq explanation time: {time.perf_counter() - start:.2f}s')
    if not explanation:
        raise RuntimeError('Empty AI explanation.')
    explanation_cache[cache_key] = explanation
    return explanation
