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

## Adding the feature to your fonts

### Install

This tool requires following packages.

* Python3
* [fonttools]
* [hb-shape]

Installation for Linux:
```sh
% sudo apt get libharfbuzz-bin
```
Installation for Mac:
```sh
% brew install harfbuzz
```
Then you can use your favorite package manager to install required Python packages.
If you use [poetry]:
```sh
% poetry install --no-dev
```
If you prefer using the most basic `pip3`:
```sh
% pip3 install fonttools
```

[fonttools]: https://pypi.org/project/fonttools/
[hb-shape]: https://command-not-found.com/hb-shape
[poetry]: https://github.com/python-poetry/poetry

### Usage

The following example adds the feature table to `input-font-file`
and saves it to the `build` directory.
```sh
% python3 Builder.py -o build input-font-file
```
Please use the `--help` option
to see the full list of options.

### Languages

Because glyphs of a code point differ by languages,
this tool need to generate different tables for different languages.

When the font supports multiple East Asian languages,
this tool can detect the languages automatically in most cases.

When the language can't be detected, this tool shows an error.
You need to specify the [OpenType language system tag] of the font.

The following example specifies that the font is a Japanese font.
```sh
% python3 Builder.py --language=JAN input-font-file
```

[OpenType language system tag]: https://docs.microsoft.com/en-us/typography/opentype/spec/languagetags

### TrueType Collection (TTC)

When the `input-font-file` is a TrueType Collection,
this tool adds the feature table to all fonts in the collection by default.

If you don't want to add the feature table to all fonts in the collection,
you can specify a comma-separated list of font indexes.

The following example adds the table to font index 0 and 1, but not to other fonts.
```sh
% python3 Builder.py --index=0,1 input-font-file.ttc
```

The language option applies to all fonts in the collection by default.
When you want to specify different languages to each font in the collection,
it accepts a comma-separated list.
The following example specifies
Korean for the font index 1,
Simplified Chinese for the font index 2,
and automatic for all other fonts.
```sh
% python3 Builder.py --language=,KOR,ZHS input-font-file.ttc
```

You can combine these two options.
The following example applies
`JAN` to the index 2,
and `ZHS` to the index 3.
Other fonts are not changed.
```sh
% python3 Builder.py --index=2,3 --language=JAN,ZHS input-font-file.ttc
```

### Noto CJK

For [Noto CJK] fonts,
`NotoCJKBuilder.py` can determine the font indices and the languages automatically.
It is equivalent to `Builder.py`, except that
a) it computes the appropriate language for each font, and
b) it skips `Mono` fonts,
both determined by the font name.
```sh
% python3 NotoCJKBuilder.py NotoSansCJK.ttc
```
You can also run it for a directory to find all font files recursively.
```sh
% python3 NotoCJKBuilder.py ~/googlefonts/noto-cjk
```

[Noto CJK]: https://www.google.com/get/noto/help/cjk/

## Testing

### Test HTML

A [test HTML] is available
to check the behavior on browsers.

[test HTML]: https://kojiishi.github.io/chws/test.html

### Dump and Diff

`Dump.py` can create various types of text dump files.
```sh
% python3 Dump.py build/NotoSansCJK-Regular.ttc
```

It can also create text dump files of two fonts, and
create diff files between the two sets of dump files.
This helps visualizing changes in the font files you created.
```sh
% python3 Dump.py -o build/dump --diff fonts build/NotoSansCJK.ttc
```

`diff-ref.sh` can create diff files between two sets of diff files.
By placing once-reviewed diff files into the `reference` directory,
this tool can visualize differences in subsequent builds.

### Shape Tests

`Tester.py` can test fonts by shaping several strings
and by checking whether the contextual spacing is applied or not.

`Builder.py` and `NotoCJKBuilder.py` call it automtically
for all fonts they built.

## Appendix

### Data Comparisons and Analysis

The [data comparison report]
of [CSS Text 4] and
[feature file] at [Adobe CJK Type blog article].

[data comparison report]: https://colab.research.google.com/github/kojiishi/contextual-spacing/blob/master/contextual_spacing_analysis.ipynb
[Adobe CJK Type blog article]: https://blogs.adobe.com/CCJKType/2018/04/contextual-spacing.html
[CSS Text 4]: https://drafts.csswg.org/css-text-4/#text-spacing-classes
[feature file]: http://blogs.adobe.com/CCJKType/files/2018/04/features.txt
