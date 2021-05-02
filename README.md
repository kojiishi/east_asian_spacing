# East Asian Contextual Spacing

This directory contains tools for
the OpenType [Contextual Half-width Spacing] feature
for Japanese/Chinese/Korean typography.
This feature enables the typography described in
[JLREQ 3.1.2 Positioning of Punctuation Marks (Commas, Periods and Brackets)
<span lang="ja">句読点や，括弧類などの基本的な配置方法</span>](https://w3c.github.io/jlreq/#positioning_of_punctuation_marks)
and [CLREQ 3.1.6.1 Punctuation Adjustment Space
<span lang="zh">标点符号的调整空间 標點符號的調整空間</span>](https://w3c.github.io/clreq/?lang=en#h-punctuation_adjustment_space).

You can find [sample text here](http://kojiishi.github.io/chws/samples.html).

[Contextual Half-width Spacing]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws

## Adding the feature to your fonts

### Install

This tool requires following packages.

* [hb-shape]
* Python 3.8 or later
* [fonttools]

Install [hb-shape] for Linux:
```sh
% sudo apt get libharfbuzz-bin
```
Install [hb-shape] for Mac:
```sh
% brew install harfbuzz
```

Then install required Python packages.
The use of [pipenv] is recommended:
```sh
% pipenv shell
% pipenv sync -d
% pip install -e .
```

[fonttools]: https://pypi.org/project/fonttools/
[hb-shape]: https://command-not-found.com/hb-shape
[pipenv]: https://github.com/pypa/pipenv
[poetry]: https://github.com/python-poetry/poetry

### Usage

The following example adds the feature table to `input-font-file`
and saves it to the `build` directory.
```sh
% python3 builder.py -o build input-font-file
```
Please use the `--help` option
to see the full list of options.

Also there are some [scripts](#scripts) that can help using the tools
in the `scripts` directory.

### Languages

Because glyphs of a code point differ by languages,
this tool need to generate different tables for different languages.

When the font supports multiple East Asian languages,
this tool can detect the languages automatically in most cases.

When the language can't be detected, this tool shows an error.
You need to specify the [OpenType language system tag] of the font.

The following example specifies that the font is a Japanese font.
```sh
% python3 builder.py --language=JAN input-font-file
```

[OpenType language system tag]: https://docs.microsoft.com/en-us/typography/opentype/spec/languagetags

### TrueType Collection (TTC)

When the `input-font-file` is a TrueType Collection,
this tool adds the feature table to all fonts in the collection by default.

If you don't want to add the feature table to all fonts in the collection,
you can specify a comma-separated list of font indexes.

The following example adds the table to font index 0 and 1, but not to other fonts.
```sh
% python3 builder.py --index=0,1 input-font-file.ttc
```

The language option applies to all fonts in the collection by default.
When you want to specify different languages to each font in the collection,
it accepts a comma-separated list.
The following example specifies
Korean for the font index 1,
Simplified Chinese for the font index 2,
and automatic for all other fonts.
```sh
% python3 builder.py --language=,KOR,ZHS input-font-file.ttc
```

You can combine these two options.
The following example applies
`JAN` to the index 2,
and `ZHS` to the index 3.
Other fonts are not changed.
```sh
% python3 builder.py --index=2,3 --language=JAN,ZHS input-font-file.ttc
```

### Noto CJK

For [Noto CJK] fonts,
`noto_cjk_builder.py` can determine the font indices and the languages automatically.
It is equivalent to `builder.py`, except that
a) it computes the appropriate language for each font, and
b) it skips `Mono` fonts,
both determined by the font name.
```sh
% python3 noto_cjk_builder.py NotoSansCJK.ttc
```
You can also run it for a directory to find all font files recursively.
```sh
% python3 noto_cjk_builder.py ~/googlefonts/noto-cjk
```

[Noto CJK]: https://www.google.com/get/noto/help/cjk/

### Scripts

Small shell scripts are available in the `scripts` directory.

`build*.sh` scripts are useful to build fonts, dump them, and
compare the dump files with reference files (see [Dump and Diff] below).
Followings are example usages.
```sh
% ./scripts/build.sh input-font-file.otf -v
% ./scripts/build-noto-cjk.sh ~/fonts/noto-cjk -v
```

## Testing

### Test HTML

A [test HTML] is available
to check the behavior of fonts on browsers.

[test HTML]: https://kojiishi.github.io/chws/test.html

### Dump and Diff
[Dump and Diff]: #dump-and-diff

`dump.py` can create various types of text dump files.
The following example creates dump files in the `build/dump` directory.
```sh
% python3 dump.py -o build/dump build/NotoSansCJK-Regular.ttc
```

`dump.py` can also create text dump files of two font files and compare them.
This helps visualizing changes in the font files you created.
```sh
% python3 dump.py -o build/dump --diff fonts build/NotoSansCJK.ttc
```
This example creates following 3 sets of files:
1. Dump files for `build/NotoSansCJK.ttc` in the `build/dump` directory.
2. Dump files for `fonts/NotoSansCJK.ttc` in the `build/dump/src` directory.
3. Diff files of the two sets of dump files in the `build/dump/diff` directory.

### References

Once you reviewed the diff files created above,
or tested fonts you build,
you can copy the diff files into the `references` directory.

`diff-ref.sh` creates diff files between two font files using `dump.py`,
and compare them with once-reviewed diff files in the `references` directory.
This tool can visualize differences from previous builds if any,
such as when the source fonts were updated,
this tool was updated,
or when the build environment changed.

`scripts/build.sh` automatically invokes this script.

### Shape Tests

`tester.py` can test fonts by shaping several strings
and by checking whether the contextual spacing is applied or not.

`builder.py` and `noto_cjk_builder.py` call this automtically
for all fonts they built.
