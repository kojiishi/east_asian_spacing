import pytest

from east_asian_spacing import Builder
from east_asian_spacing import CollectionConfig
from east_asian_spacing import Config
from east_asian_spacing import EastAsianSpacingTester


@pytest.mark.asyncio
async def test_config(test_font_path, tmp_path):

    class MyCustomConfig(Config):

        def __init__(self):
            super().__init__()
            self.cjk_opening = {0x3008}
            self.cjk_closing = {0x3009}

    config = MyCustomConfig()
    builder = Builder(test_font_path, config)
    await builder.build()
    builder.save(tmp_path)

    await builder.test()

    # U+300A should fail because `cjk_opning` is limited only to U+3008.
    fail_config = config.clone()
    fail_config.cjk_opening = {0x300A}
    with pytest.raises(AssertionError):
        await EastAsianSpacingTester(builder.font, fail_config).test()


def test_change_quotes_closing_to_opening():
    config = Config.default.clone()
    config.quotes_opening = {0x2018, 0x201C}
    config.quotes_closing = {0x2019, 0x201D}
    config.change_quotes_closing_to_opening(0x2019)
    assert config.quotes_opening == {0x2018, 0x201C, 0x2019}
    assert config.quotes_closing == {0x201D}
    config.change_quotes_closing_to_opening(0xFFFF)
    assert config.quotes_opening == {0x2018, 0x201C, 0x2019}
    assert config.quotes_closing == {0x201D}


def test_down_sample_to():

    def call(input, max):
        return Config._down_sample_to(input, max)

    assert call(list(range(8)), 3) == {0, 3, 6}
    assert call(list(range(9)), 3) == {0, 3, 6}
    assert call(list(range(10)), 3) == {0, 4, 8}


def test_calc_indices_and_languages():

    def call(num_fonts, indices, language):
        return list(
            CollectionConfig._calc_indices_and_languages(
                num_fonts, indices, language))

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


def test_config_for_font_name():
    config = Config.default

    # Unknown fonts should use the default config.
    assert config.for_font_name('never exists', False) is config


def test_config_for_language():
    config = Config.default
    assert config.use_ink_bounds
    assert not config.language

    # `for_language` should clone and set the langauge.
    jan = config.for_language('JAN')
    assert jan is not config
    assert jan.language == 'JAN'
    assert not jan.use_ink_bounds

    # The original `config` should not be modified.
    assert config.use_ink_bounds
    assert not config.language
