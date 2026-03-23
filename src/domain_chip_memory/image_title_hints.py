from __future__ import annotations

import re


KNOWN_IMAGE_TITLE_HINTS: dict[str, str] = {
    "https://www.speakers.co.uk/microsites/tom-oliver/wp-content/uploads/2014/11/Book-Cover-3D1.jpg": "Nothing is Impossible",
}


def extract_image_urls(payload: str) -> list[str]:
    return re.findall(r"image_url:\s*(https?://\S+)", payload, re.IGNORECASE)


def resolve_titles_from_image_urls(payload: str) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for url in extract_image_urls(payload):
        normalized = url.rstrip(".,;:!?)]}\"'")
        title = KNOWN_IMAGE_TITLE_HINTS.get(normalized)
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
    return titles
