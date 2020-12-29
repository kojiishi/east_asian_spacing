# Contextual Spacing

This directory contains tools for
the OpenType [Contextual Half-width Spacing] feature
for Japanese/Chinese/Korean typography.
This feature enables the typography described in
[JLREQ 3.1.2 Positioning of Punctuation Marks (Commas, Periods and Brackets)
句読点や，括弧類などの基本的な配置方法](https://w3c.github.io/jlreq/#positioning_of_punctuation_marks).

[Contextual Half-width Spacing]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws

## Test HTML

View the [test HTML].

[test HTML]: https://kojiishi.github.io/chws/test.html

## Add the feature to your fonts

### Prerequisite

* Python3
* [fonttools]
* [hb-shape]

Installation on Linux:
```sh
% sudo pip3 install fonttools
% sudo apt get libharfbuzz-bin
```

[fonttools]: https://pypi.org/project/fonttools/
[hb-shape]: https://command-not-found.com/hb-shape

### Usage

```sh
% python3 FontBuilder.py input-font-file -o output-font-file -v
```

## Data Comparisons

The [data comparison report]
of [CSS Text 4] and
[feature file] at [Adobe CJK Type blog article].

[data comparison report]: https://colab.research.google.com/github/kojiishi/contextual-spacing/blob/master/contextual_spacing_analysis.ipynb
[Adobe CJK Type blog article]: https://blogs.adobe.com/CCJKType/2018/04/contextual-spacing.html
[CSS Text 4]: https://drafts.csswg.org/css-text-4/#text-spacing-classes
[feature file]:http://blogs.adobe.com/CCJKType/files/2018/04/features.txt
