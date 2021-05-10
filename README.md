# East Asian Contextual Spacing

This directory contains tools for
the OpenType [Contextual Half-width Spacing] feature
for Japanese/Chinese/Korean typography.
This feature enables the typography described in
[JLREQ 3.1.2 Positioning of Punctuation Marks (Commas, Periods and Brackets)
<span lang="ja">句読点や，括弧類などの基本的な配置方法</span>](https://w3c.github.io/jlreq/#positioning_of_punctuation_marks)
and [CLREQ 3.1.6.1 Punctuation Adjustment Space
<span lang="zh">标点符号的调整空间 標點符號的調整空間</span>](https://w3c.github.io/clreq/?lang=en#h-punctuation_adjustment_space).
Following is a figure from JLREQ:

<img src="https://w3c.github.io/jlreq/images/img2_13.png"
   title="East Asian contextual spacing examples">

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
Install [hb-shape] for Mac with [homebrew]:
```sh
% brew install harfbuzz
```

Then install Python packages.
If you may need to diagnose fonts or the code,
installing in the editable mode (i.e., setuptools “develop mode”)
using [poetry] is recommended:
```sh
% git clone https://github.com/kojiishi/east_asian_spacing
% cd east_asian_spacing
% poetry install
```
Otherwise, you can install with [pip].
It is still recommended to install into a separate virtual environment:
```sh
% git clone https://github.com/kojiishi/east_asian_spacing
% cd east_asian_spacing
% python3 -m venv venv
% source venv/bin/activate
% pip install .
```

[fonttools]: https://pypi.org/project/fonttools/
[hb-shape]: https://command-not-found.com/hb-shape
[homebrew]: https://brew.sh/
[pip]: https://pip.pypa.io/en/latest/
[pipenv]: https://github.com/pypa/pipenv
[poetry]: https://github.com/python-poetry/poetry

### Usage

The following example adds the feature table to `input-font-file`
and saves it to the `build` directory.
```sh
% east-asian-spacing -o build input-font-file
```
Please use the `--help` option
to see the full list of options.

### Languages

Because the glyph for a code point may differ by languages,
this tool need to generate different tables for different languages.

When the font supports multiple East Asian languages,
this tool can detect the languages automatically in most cases.
But when the language can't be detected, this tool shows an error.
You need to specify the [OpenType language system tag] of the font.

The following example specifies that the font is a Japanese font.
```sh
% east-asian-spacing --language=JAN input-font-file
```

[OpenType language system tag]: https://docs.microsoft.com/en-us/typography/opentype/spec/languagetags

### TrueType Collection (TTC)

When the `input-font-file` is a TrueType Collection,
this tool adds the feature table to all fonts in the collection by default.

If you want to add the feature table to only some of fonts in the collection,
you can specify a comma-separated list of font indexes.
The following example adds the table to the font index 0 and 1,
but not to other fonts in the collection.
```sh
% east-asian-spacing --index=0,1 input-font-file.ttc
```

The language option applies to all fonts in the collection by default.
When you want to specify different languages to each font in the collection,
it accepts a comma-separated list.
The following example specifies
Korean for the font index 1,
Simplified Chinese for the font index 2,
and automatic for all other fonts.
```sh
% east-asian-spacing --language=,KOR,ZHS input-font-file.ttc
```

You can combine these two options.
The following example applies
`JAN` to the index 2,
and `ZHS` to the index 3.
Other fonts are not changed.
```sh
% east-asian-spacing --index=2,3 --language=JAN,ZHS input-font-file.ttc
```

### Noto CJK

For [Noto CJK] fonts,
`east-asian-spacing` has a built-in support
to determine the font indices and the languages automatically.

When the first argument is `noto`, it
a) computes the appropriate language for each font, and
b) skips `Mono` fonts,
both determined by the font name.
```sh
% east-asian-spacing noto NotoSansCJK.ttc
```
You can also run it for a directory to find all font files recursively.
```sh
% east-asian-spacing noto ~/googlefonts/noto-cjk
```

[Noto CJK]: https://www.google.com/get/noto/help/cjk/

### Scripts
[scripts]: (#scripts)

Some small shell scripts are available in the `scripts` directory.

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

It can test fonts you built locally.
Download it to your local drive and
add your fonts to the "`fonts`" list
at the beginning of the `<script>` block.

[test HTML]: https://kojiishi.github.io/chws/test.html

### Dump and Diff
[Dump and Diff]: #dump-and-diff

The `dump` sub-command can create various types of text dump files.

The most simple usage is to show a list of tables.
This is similar to "`ttx -l`" in [fonttools],
except for TrueType Collections (TTC),
this tool can show which tables are shared with which fonts
in the TrueType Collection.
```sh
% east-asian-spacing dump build/NotoSansCJK-Regular.ttc
```

The "`-o`" option creates the table list file in the specified directory:
```sh
% east-asian-spacing dump -o build/dump build/*.ttc
```
The "`--ttx`" option creates TTX text dumps in addition to the table list:
```sh
% east-asian-spacing dump -o build/dump --ttx build/*.ttc
```

The `dump` sub-command can also create
table lists and TTX text dump files of two font files and compare them.
This helps visualizing differences in the font files you created
from the original font files.
```sh
% east-asian-spacing dump -o build/dump --diff source_fonts build/NotoSansCJK.ttc
```
The example above creates following 3 sets of files:
1. The table list and TTX text dump files for `build/NotoSansCJK.ttc`
   in the `build/dump` directory.
2. The table list and TTX text dump files for `source_fonts/NotoSansCJK.ttc`
   in the `build/dump/src` directory.
3. Diff files of the two sets of dump files in the `build/dump/diff` directory.

To create dump and diff files for all fonts you bulit,
you can pipe the output as below:
```sh
% east-asian-spacing -p *.otf | east-asian-spacing dump -o=build/dump -
```
The "`-p`" option prints the font paths to `stdout`
in the tab-separated-values format.
The `dump` sub-command with the "`-`" argument reads this list from `stdin`,
and creates text dump and diff files in the `build/dump` directory.
The "`--diff`" option is not necessary in this case,
because the path of source fonts are also provided from the pipe.

### References

Once you reviewed the diff files created above,
or tested fonts you build,
you can copy the diff files into the `references` directory.
Then when you want to build them again,
such as when the fonts are updated or when the build environment is changed,
you can compare the diff files with the reference files
to know how new fonts are different from previous builds.

With the "`-r`" option, the `dump` sub-command
creates diff files between two font files as explained in [dump and diff],
and compare them with once-reviewed diff files in the `references` directory.

The typical usage of this option is as below:
```sh
% east-asian-spacing -p -g=build/glyphs *.otf |
    east-asian-spacing dump -o=build/dump -r=references -
```
Please see the [dump and diff] section for the "`-p`" option and piping.

The `build*.sh` [scripts] include this option.

### Shape Tests

`tester.py` can test fonts by shaping several strings
and by checking whether the contextual spacing is applied or not.

`builder.py` and `noto_cjk_builder.py` call this automtically
for all fonts they built.
