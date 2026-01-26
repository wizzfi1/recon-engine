import re

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower())

def name_match_score(a, b):
    a_tokens = set(normalize(a).split())
    b_tokens = set(normalize(b).split())
    return len(a_tokens & b_tokens)
