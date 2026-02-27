from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    source: str
    trust: str


def untrusted_chunk(text: str, source: str) -> TextChunk:
    return TextChunk(text=text or "", source=source, trust="untrusted")


def render_chunk(chunk: TextChunk) -> str:
    return f"[source:{chunk.source} trust:{chunk.trust}]\n{chunk.text}"
