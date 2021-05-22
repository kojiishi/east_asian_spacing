from east_asian_spacing import EastAsianSpacingConfig


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
    config.quotes_opening = {0x2018, 0x201C}
    config.quotes_closing = {0x2019, 0x201D}
    config.change_quotes_closing_to_opening(0x2019)
    assert config.quotes_opening == {0x2018, 0x201C, 0x2019}
    assert config.quotes_closing == {0x201D}
    config.change_quotes_closing_to_opening(0xFFFF)
    assert config.quotes_opening == {0x2018, 0x201C, 0x2019}
    assert config.quotes_closing == {0x201D}
