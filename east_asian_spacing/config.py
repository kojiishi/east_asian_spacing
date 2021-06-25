import contextlib
import copy
import itertools
import math


class Config(object):
    def __init__(self):
        self.cjk_opening = {
            0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014, 0x3016, 0x3018,
            0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F
        }
        self.cjk_closing = {
            0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019,
            0x301B, 0x301E, 0x301F, 0xFF09, 0xFF3D, 0xFF5D, 0xFF60
        }
        self.quotes_opening = {0x2018, 0x201C}
        self.quotes_closing = {0x2019, 0x201D}
        self.cjk_middle = {0x3000, 0x30FB}
        self.cjk_period_comma = {0x3001, 0x3002, 0xFF0C, 0xFF0E}
        self.cjk_column_semicolon = {0xFF1A, 0xFF1B}
        self.cjk_exclam_question = {0xFF01, 0xFF1F}
        self.language = None

    default = None  # This will be set later in this file.

    @staticmethod
    def for_collection(font, **kwargs):
        return CollectionConfig(font, **kwargs)

    @property
    def _sets(self):
        yield self.cjk_opening
        yield self.cjk_closing
        yield self.quotes_opening
        yield self.quotes_closing
        yield self.cjk_middle
        yield self.cjk_period_comma
        yield self.cjk_column_semicolon
        yield self.cjk_exclam_question

    def clear(self):
        for set in self._sets:
            set.clear()

    def clone(self):
        return copy.deepcopy(self)

    def for_font(self, font):
        """Returns a tweaked copy if the `font` needs special treatments.
        Otherwise returns `self`."""
        return self

    def for_language(self, language):
        """Returns a copy with the specified language."""
        if language == self.language:
            return self
        clone = self.clone()
        clone.language = language
        return clone

    def for_smoke_testing(self):
        """Returns a copy with the number of code points reduced for testing."""
        clone = self.clone()
        clone.cjk_opening = self._down_sample_to(clone.cjk_opening, 3)
        clone.cjk_closing = self._down_sample_to(clone.cjk_closing, 3)
        return clone

    def remove(self, *codes):
        for code in codes:
            for set in self._sets:
                set.discard(code)

    def change_quotes_closing_to_opening(self, *codes):
        """Changes the `code` from `quotes_closing` to `quotes_opening`.
        Does nothing if the `code` is not in `quotes_closing`."""
        for code in codes:
            with contextlib.suppress(KeyError):
                self.quotes_closing.remove(code)
                self.quotes_opening.add(code)

    @staticmethod
    def _down_sample_to(input, max):
        if len(input) <= max:
            return input
        interval = math.ceil(len(input) / max)
        return set(itertools.islice(input, 0, None, interval))


class DefaultConfig(Config):
    def for_font(self, font):
        name = font.debug_name(1)
        if not name:
            return self
        if name.startswith("Meiryo"):
            config = self.for_language('JAN')
            if font.is_vertical:
                if config is self:
                    config = config.clone()
                config.change_quotes_closing_to_opening(0x2019)
                config.remove(0xFF0C, 0xFF0E)
            return config
        if name.startswith("Microsoft JhengHei"):
            config = self.for_language('ZHT')
            if config is self:
                config = config.clone()
            config.remove(0xFF08, 0xFF09, 0xFF3B, 0xFF3D, 0xFF5B, 0xFF5D,
                          0xFF5F, 0xFF60)
            if font.is_vertical:
                config.change_quotes_closing_to_opening(0x2019, 0x201D)
            return config
        if name.startswith("Microsoft YaHei"):
            config = self.for_language('ZHS')
            if font.is_vertical:
                if config is self:
                    config = config.clone()
                config.remove(0x3001, 0x3002, 0x3018, 0x3019, 0x301A, 0x301B,
                              0xFF08, 0xFF09, 0xFF0C, 0xFF0E)
            return config
        return self


class CollectionConfig(DefaultConfig):
    def __init__(self, font, languages=None, indices=None):
        assert font.is_collection
        super().__init__()
        indices_and_languages = self._calc_indices_and_languages(
            len(font.fonts_in_collection), indices, languages)
        self._language_by_index = dict(indices_and_languages)

    def for_font(self, font):
        assert font.font_index is not None
        language = self._language_by_index.get(font.font_index, 0)
        if language == 0:
            return None
        config = super().for_font(font)
        if language and not config.language:
            return config.for_language(language)
        return config

    @staticmethod
    def _calc_indices_and_languages(num_fonts, indices, languages):
        assert num_fonts >= 2
        if indices is None:
            indices = range(num_fonts)
        elif isinstance(indices, str):
            indices = (int(i) for i in indices.split(","))
        if languages:
            if isinstance(languages, str):
                languages = languages.split(',')
            if len(languages) == 1:
                return itertools.zip_longest(indices, (),
                                             fillvalue=languages[0])
            return itertools.zip_longest(indices, languages)
        return itertools.zip_longest(indices, ())


Config.default = DefaultConfig()
