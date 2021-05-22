from east_asian_spacing import Font


def test_is_font_extension():
    assert not Font.is_font_extension('.xyz')
    assert Font.is_font_extension('.otf')
    assert Font.is_font_extension('.ttc')
    assert Font.is_font_extension('.ttf')
    assert Font.is_font_extension('.OTF')
    assert Font.is_font_extension('.TTC')
    assert Font.is_font_extension('.TTF')
