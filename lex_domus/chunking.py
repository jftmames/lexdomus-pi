"""Lossless text windows with offsets into the newline-normalized source."""

from bisect import bisect_left


def normalize_text(raw: str) -> str:
    """Normalize CRLF and CR to LF, preserving every other character.

    In particular, leading/trailing whitespace, blank lines and a Unicode BOM
    remain part of the source and therefore part of its citation coordinates.
    """
    if not isinstance(raw, str):
        raise TypeError("raw must be a string")
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def split_text(
    text: str, *, max_chars: int = 1000, overlap_chars: int = 120
) -> list[dict]:
    """Return deterministic, overlapping windows covering all normalized text.

    Character offsets are zero-based, half-open Unicode string indices into
    ``normalize_text(text)``. Line numbers are one-based and inclusive: a LF
    belongs to the line it terminates, including when it ends a window.

    Windows contain at most ``max_chars`` code points, and every consecutive
    pair shares exactly ``overlap_chars`` code points. No content is stripped
    or discarded to find a preferred boundary. Empty input produces no windows.
    """
    for name, value in (("max_chars", max_chars), ("overlap_chars", overlap_chars)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if not 0 <= overlap_chars < max_chars:
        raise ValueError("overlap_chars must be between zero and max_chars - 1")

    normalized = normalize_text(text)
    newline_positions = [index for index, char in enumerate(normalized) if char == "\n"]
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        chunks.append(
            {
                "text": normalized[start:end],
                "char_start": start,
                "char_end": end,
                "line_start": bisect_left(newline_positions, start) + 1,
                "line_end": bisect_left(newline_positions, end - 1) + 1,
            }
        )
        if end == len(normalized):
            break
        start = end - overlap_chars
    return chunks
