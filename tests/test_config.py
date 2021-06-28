import pytest

from east_asian_spacing import Builder
from east_asian_spacing import CollectionConfig
from east_asian_spacing import Config
from east_asian_spacing import EastAsianSpacingTester
from east_asian_spacing import NotoCJKConfig


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
        await EastAsianSpacingTester(builder.font).test(fail_config)


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

    meiryo = config.for_font_name('Meiryo', False)
    assert meiryo is not config
    assert meiryo.language == 'JAN'

    # Unknown fonts should use the default config.
    assert config.for_font_name('never exists', False) is config


def test_noto_cjk_config_for_font_name():
    config = NotoCJKConfig.default

    noto_cjk_jp = config.for_font_name('Noto Sans CJK JP', False)
    assert noto_cjk_jp is not config
    assert noto_cjk_jp.language == 'JAN'

    # 'Mono' fonts should be not applicable.
    assert config.for_font_name('Noto Sans Mono CJK JP', False) is None

    # `NotoCJKConfig` is only for Noto fonts.
    with pytest.raises(AssertionError):
        config.for_font_name('Meiryo', False)
