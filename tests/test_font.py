from east_asian_spacing import Font


def test_is_font_extension():
    assert not Font.is_font_extension('.xyz')
    assert Font.is_font_extension('.otf')
    assert Font.is_font_extension('.ttc')
    assert Font.is_font_extension('.ttf')
    assert Font.is_font_extension('.OTF')
    assert Font.is_font_extension('.TTC')
    assert Font.is_font_extension('.TTF')


def test_vertical_font(test_font_path):
    font = Font.load(test_font_path)
    assert font.is_root
    assert font.root_or_self == font
    assert list(font.self_and_derived_fonts(create=False)) == [font]

    vertical_font = font.vertical_font
    assert not vertical_font.is_root
    assert vertical_font.root_or_self == font

    assert list(font.self_and_derived_fonts()) == [font, vertical_font]
