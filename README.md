# East Asian Contextual Spacing

This directory contains tools for
the OpenType [Contextual Half-width Spacing] feature
for Japanese/Chinese/Korean typography.
This feature enables the typography described in
[JLREQ 3.1.2 Positioning of Punctuation Marks (Commas, Periods and Brackets)
句読点や，括弧類などの基本的な配置方法](https://w3c.github.io/jlreq/#positioning_of_punctuation_marks)
and [CLREQ 3.1.6.1 Punctuation Adjustment Space
标点符号的调整空间 標點符號的調整空間](https://w3c.github.io/clreq/?lang=en#h-punctuation_adjustment_space).

[Contextual Half-width Spacing]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws

## Test HTML

View the [test HTML].

[test HTML]: https://kojiishi.github.io/chws/test.html

## Adding the feature to your fonts

### Prerequisites

* Python3
* [fonttools]
* [hb-shape]

Installation for Linux:
```sh
% pip3 install fonttools
% sudo apt get libharfbuzz-bin
```
Installation for Mac:
```sh
% pip3 install fonttools
% brew install harfbuzz
```

[fonttools]: https://pypi.org/project/fonttools/
[hb-shape]: https://command-not-found.com/hb-shape

### Usage

```sh
% python3 Builder.py input-font-file -o output-font-file
```

### Languages

There are some different behaviors depends on the languages.
When the font supports multiple East Asian languages,
the font can detect the languages automatically in most cases.

When the language can't be detected, this tool shows an error.
You need to specify the [OpenType language system tag] of the font.

```sh
% python3 Builder.py input-font-file -l=JAN
```
specifies that the font is a Japanese font.

[OpenType language system tag]: https://docs.microsoft.com/en-us/typography/opentype/spec/languagetags

### TrueType Collection (TTC)

When the `input-font-file` is a TrueType Collection,
this tool adds the table to all fonts in the collection.

If you don't want to add the table to all fonts in the collection,
you can specify the comma-separated list of font indexes.

```sh
% python3 Builder.py input-font-file --face-index=0,1
```
adds the table to font index 0 and 1, but not to other fonts.

If you want to specify the language of each font in the collection,
```sh
% python3 Builder.py input-font-file --l=,KOR,ZHS
```
specifies Korean for the font index 1,
Simplified Chinese for the font index 2,
and automatic detection for the font index 0 and all other fonts.

## Appendix

### Data Comparisons and Analysis

The [data comparison report]
of [CSS Text 4] and
[feature file] at [Adobe CJK Type blog article].

[data comparison report]: https://colab.research.google.com/github/kojiishi/contextual-spacing/blob/master/contextual_spacing_analysis.ipynb
[Adobe CJK Type blog article]: https://blogs.adobe.com/CCJKType/2018/04/contextual-spacing.html
[CSS Text 4]: https://drafts.csswg.org/css-text-4/#text-spacing-classes
[feature file]: http://blogs.adobe.com/CCJKType/files/2018/04/features.txt
