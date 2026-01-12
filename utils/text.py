def clean_name(text):
    return (
        str(text)
        .upper()
        .replace(",", "")
        .replace(".", "")
        .strip()
    )


def name_match_score(a, b):
    a_tokens = set(clean_name(a).split())
    b_tokens = set(clean_name(b).split())
    return len(a_tokens & b_tokens)
