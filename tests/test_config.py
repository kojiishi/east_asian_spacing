import pytest

from east_asian_spacing import Builder
from east_asian_spacing import EastAsianSpacingConfig
from east_asian_spacing import EastAsianSpacingTester


@pytest.mark.asyncio
async def test_config(test_font_path, tmp_path):
    class MyCustomConfig(EastAsianSpacingConfig):
        def __init__(self):
            super().__init__()
            self.cjk_opening = {0x3008}
            self.cjk_closing = {0x3009}

        def tweaked_for(self, font):
            # No need to call `super` if the default tweaking is not needed.
            # `EastAsianSpacingConfig` has tweaks for some known fonts.
            return self

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
