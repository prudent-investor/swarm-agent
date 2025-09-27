from app.utils.text import strip_portuguese_accents


def test_strip_portuguese_accents_replaces_common_characters() -> None:
    text = "Olá, coração! Informação, ação, lição, bênção, órgão, pingüim."
    expected = "Ola, coracao! Informacao, acao, licao, bencao, orgao, pinguim."

    assert strip_portuguese_accents(text) == expected



def test_strip_portuguese_accents_is_noop_for_empty_input() -> None:
    assert strip_portuguese_accents("") == ""
