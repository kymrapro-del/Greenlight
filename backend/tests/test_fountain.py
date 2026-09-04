from greenlight.ingest.fountain import parse_file, parse_fountain


def test_parses_title_page(sample_script):
    draft = parse_file(sample_script)
    assert draft.title == "SEVENTEEN MINUTES"
    assert draft.fmt == "fountain"


def test_scene_count_and_order(sample_script):
    draft = parse_file(sample_script)
    assert len(draft.scenes) == 14
    # La numérotation suit l'ordre du script, sans trou : c'est elle que le
    # rapport cite pour renvoyer le scénariste à la bonne page.
    assert [s.number for s in draft.scenes] == list(range(1, 15))


def test_heading_decomposition(sample_script):
    first = parse_file(sample_script).scenes[0]
    assert first.int_ext == "INT"
    assert first.location == "THE BLACK CAT TAVERN"
    assert first.time_of_day == "NIGHT"


def test_transitions_do_not_create_scenes():
    """FADE IN: ouvrait une scène fantôme avant correction."""
    draft = parse_fountain("FADE IN:\n\nINT. ROOM - DAY\n\nA man waits.\n\nFADE OUT.\n")
    assert len(draft.scenes) == 1
    assert draft.scenes[0].heading == "INT. ROOM - DAY"


def test_characters_and_dialogue_are_separated(sample_script):
    scene = parse_file(sample_script).scenes[0]
    assert {"DANIEL", "MARCUS"} <= set(scene.characters)
    assert any(line.startswith("MARCUS:") for line in scene.dialogue)
    # Le dialogue ne doit pas fuiter dans l'action.
    assert "You're late." not in scene.action


def test_character_extensions_are_stripped(sample_script):
    """DANIEL (V.O.) doit être normalisé en DANIEL."""
    draft = parse_file(sample_script)
    all_characters = {c for s in draft.scenes for c in s.characters}
    assert "DANIEL" in all_characters
    assert not any("(" in c for c in all_characters)


def test_page_numbers_increase(sample_script):
    pages = [s.page_start for s in parse_file(sample_script).scenes]
    assert pages == sorted(pages)
    assert pages[0] >= 1.0
