from pathlib import Path

from kukanilea.guards import detect_prompt_injection


def test_prompt_injection_corpus():
    corpus = Path(__file__).parent / "data" / "prompt_injection_corpus.txt"
    lines = [
        line.strip()
        for line in corpus.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for line in lines:
        blocked, _ = detect_prompt_injection(line)
        assert blocked, f"Expected injection to be blocked: {line}"
