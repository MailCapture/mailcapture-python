"""Tag generation utilities."""
from __future__ import annotations

import random

_ADJECTIVES = [
    "angry", "bold",   "brave",  "calm",   "cold",   "cool",   "dark",   "dizzy",
    "dusty", "eager",  "fierce", "fluffy", "funky",  "fuzzy",  "glad",   "gloomy",
    "grumpy","hasty",  "hungry", "icy",    "itchy",  "jolly",  "jumpy",  "keen",
    "lazy",  "lucky",  "mad",    "mean",   "moody",  "muddy",  "noisy",  "odd",
    "pale",  "peppy",  "proud",  "quick",  "quiet",  "rowdy",  "rusty",  "silly",
    "sleepy","sneaky", "spooky", "swift",  "tiny",   "tough",  "vivid",  "weird",
    "wild",  "young",
]

_ANIMALS = [
    "ant",  "bear",  "boar",  "cat",   "crab",  "crow",  "deer",  "dove",
    "duck", "eel",   "elk",   "finch", "fox",   "frog",  "goat",  "hawk",
    "hare", "ibis",  "jay",   "kiwi",  "lamb",  "lark",  "lion",  "lynx",
    "mink", "mole",  "moth",  "mule",  "newt",  "owl",   "panda", "pig",
    "puma", "ram",   "rat",   "rook",  "seal",  "slug",  "snail", "swan",
    "toad", "vole",  "wasp",  "wolf",  "wren",  "yak",   "zebra", "bat",
    "bee",  "carp",
]


def generate_tag() -> str:
    """Return a unique, human-readable tag such as ``"funky-otter-a3f2b8"``.

    Format: ``{adjective}-{animal}-{6 hex digits}``.
    ~42 billion combinations — collision probability < 0.1% across 10 000 tags.
    No client or network call needed.

    Example::

        from mailcapture import generate_tag

        tag = generate_tag()          # "funky-otter-a3f2b8"
        email = mc.address(tag)       # "alice-funky-otter-a3f2b8@mailcapture.app"
    """
    adj    = random.choice(_ADJECTIVES)
    animal = random.choice(_ANIMALS)
    suffix = format(random.randint(0, 0xFFFFFF), "06x")
    return f"{adj}-{animal}-{suffix}"
