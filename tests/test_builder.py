from pathlib import Path

from builder import Builder
from spacing import EastAsianSpacingConfig


def test_calc_indices_and_languages():
    def call(num_fonts, indices, language):
        return list(
            Builder.calc_indices_and_languages(num_fonts, indices, language))

    assert call(3, None, None) == [(0, None), (1, None), (2, None)]
    assert call(3, None, 'JAN') == [(0, 'JAN'), (1, 'JAN'), (2, 'JAN')]
    assert call(3, None, 'JAN,') == [(0, 'JAN'), (1, ''), (2, None)]
    assert call(3, None, 'JAN,ZHS') == [(0, 'JAN'), (1, 'ZHS'), (2, None)]
    assert call(3, None, ',JAN') == [(0, ''), (1, 'JAN'), (2, None)]

    assert call(4, '0', None) == [(0, None)]
    assert call(4, '0,2', None) == [(0, None), (2, None)]

    assert call(4, '0', 'JAN') == [(0, 'JAN')]
    assert call(4, '0,2', 'JAN') == [(0, 'JAN'), (2, 'JAN')]
    assert call(4, '0,2', 'JAN,ZHS') == [(0, 'JAN'), (2, 'ZHS')]
    assert call(6, '0,2,5', 'JAN,ZHS') == [(0, 'JAN'), (2, 'ZHS'), (5, None)]
    assert call(6, '0,2,5', 'JAN,,ZHS') == [(0, 'JAN'), (2, ''), (5, 'ZHS')]


def test_calc_output_path(data_dir):
    def call(input_path, output_path, stem_suffix=None):
        return Builder.calc_output_path(input_path, output_path, stem_suffix)

    assert call(Path('c.otf'), None) == Path('c.otf')
    assert call(Path('a/b/c.otf'), None) == Path('a/b/c.otf')

    assert call(Path('c.otf'), None, '-chws') == Path('c-chws.otf')
    assert call(Path('a/b/c.otf'), None, '-chws') == Path('a/b/c-chws.otf')

    assert call(Path('c.otf'), Path('build')) == Path('build/c.otf')
    assert call(Path('a/b/c.otf'), Path('build')) == Path('build/c.otf')

    assert call(Path('a/b/c.otf'), Path('build'),
                '-xyz') == Path('build/c-xyz.otf')


def test_down_sample_to():
    def call(list, max):
        config = EastAsianSpacingConfig()
        config.cjk_opening = list
        config.down_sample_to(max)
        return config.cjk_opening

    assert call(list(range(8)), 3) == [0, 3, 6]
    assert call(list(range(9)), 3) == [0, 3, 6]
    assert call(list(range(10)), 3) == [0, 4, 8]


def test_change_quotes_closing_to_opening():
    config = EastAsianSpacingConfig()
    config.quotes_opening = [0x2018, 0x201C]
    config.quotes_closing = [0x2019, 0x201D]
    config.change_quotes_closing_to_opening(0x2019)
    assert config.quotes_opening == [0x2018, 0x201C, 0x2019]
    assert config.quotes_closing == [0x201D]
    config.change_quotes_closing_to_opening(0xFFFF)
    assert config.quotes_opening == [0x2018, 0x201C, 0x2019]
    assert config.quotes_closing == [0x201D]
