import re

STOPWORDS = {
    "estate", "of", "the", "trust", "late",
    "mr", "mrs", "miss", "dr", "chief",
    "sir", "madam"
}

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower())


def name_match_score(a, b):
    """
    Strict name matching score.

    Rules:
    - Remove boilerplate / legal words
    - Require >= 2 matching tokens
    - Require at least one meaningful token (len >= 5)
    """

    a_tokens = {
        t for t in normalize(a).split()
        if t and t not in STOPWORDS
    }

    b_tokens = {
        t for t in normalize(b).split()
        if t and t not in STOPWORDS
    }

    common = a_tokens & b_tokens

    # 🚫 No overlap
    if len(common) < 2:
        return 0

    # 🚫 Prevent generic matches (estate, of, etc.)
    if not any(len(token) >= 5 for token in common):
        return 0

    return len(common)
