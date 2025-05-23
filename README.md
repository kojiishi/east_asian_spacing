[![CI](https://github.com/kojiishi/east_asian_spacing/actions/workflows/ci.yml/badge.svg)](https://github.com/kojiishi/east_asian_spacing/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/east-asian-spacing.svg)](https://pypi.org/project/east-asian-spacing/)
[![Dependencies](https://badgen.net/github/dependabot/kojiishi/east_asian_spacing)](https://github.com/kojiishi/east_asian_spacing/network/updates)

# East Asian Contextual Spacing

This directory contains tools for
the OpenType Contextual Half-width Spacing feature
for Japanese/Chinese/Korean typography.

This feature enables the typography described in
[JLREQ 3.1.2 Positioning of Punctuation Marks (Commas, Periods and Brackets)
<span lang="ja">句読点や，括弧類などの基本的な配置方法</span>](https://w3c.github.io/jlreq/#positioning_of_punctuation_marks)
for Japanese,
and [CLREQ 3.1.6.1 Punctuation Adjustment Space
<span lang="zh">标点符号的调整空间 標點符號的調整空間</span>](https://w3c.github.io/clreq/#h-punctuation_adjustment_space)
for Chinese.
Following is a figure from JLREQ:

<img src="https://w3c.github.io/jlreq/images/img2_13.png"
   title="East Asian contextual spacing examples">

An early discussion at [Adobe CJK Type blog article] and [Part II]
may help to understand the feature better.

[Adobe CJK Type blog article]: https://ccjktype.fonts.adobe.com/2018/04/contextual-spacing.html
[Part II]: https://ccjktype.fonts.adobe.com/2019/04/contextual-spacing-gpos-features-redux.html

### Demo

You can find [sample text here](http://kojiishi.github.io/chws/samples.html).
This sample page uses fonts built with this tool.

### OpenType Font Features

OpenType defines 4 feature tags
for fonts to support this feature:
* The "[`chws`]" feature tag,
and the "[`vchw`]" feature tag as its vertical flow counterpart.
* The "[`halt`]" feature tag,
and the "[`vhal`]" feature tag as its vertical flow counterpart.

All 4 features are desired,
as each feature is applied in different context.

This package adds these features to any OpenType/TrueType fonts
when they are missing,
by computing the feature tables from data
such as Unicode code points and glyph outlines.

[`chws`]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws
[`halt`]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_fj#tag-halt
[`vchw`]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_uz#tag-vchw
[`vhal`]: https://docs.microsoft.com/en-us/typography/opentype/spec/features_uz#tag-vhal

## Adding the features to your fonts

### Install
[install]: #install

You can install this tool by [pipx] or [uv].

```shell-session
pipx install east-asian-spacing
```
```shell-session
uv tool install east-asian-spacing
```

Using [pip] is also supported, but please be aware that,
if you install with [pip] in the global environment,
its dependencies may cause conflicts with other packages.
If all what you need is the command line tool,
[pipx] or [uv] can install it globally
while still isolating it in a virtual environment.
```shell-session
pip install east-asian-spacing
```

Please also see the [install package] section
if you want to use this package from your Python program,
or the [clone and install] section
if you want to diagnose fonts or the code in more details.

[development mode]: https://setuptools.readthedocs.io/en/latest/userguide/development_mode.html
[editable mode]: https://pip.pypa.io/en/stable/cli/pip_install/#install-editable
[fonttools]: https://pypi.org/project/fonttools/
[pip]: https://pip.pypa.io/en/latest/
[pip "`-e`" option]: https://pip.pypa.io/en/stable/cli/pip_install/#install-editable
[pipx]: https://pipxproject.github.io/pipx/
[pipenv]: https://github.com/pypa/pipenv
[poetry]: https://github.com/python-poetry/poetry
[uv]: https://docs.astral.sh/uv/

### Command Line Usages

The following example adds the feature to `input-font-file`
and saves it to the `build` directory.
```shell-session
east-asian-spacing -o build input-font-file
```

The [testing] section has resources for
[checking the differences] and
testing fonts you built.

For other options and usages,
the `--help` option can show the full list of options.

### Supported Fonts

The [algorithm] is applicable to any CJK fonts.
Following fonts are tested on each release:
* [Noto CJK]
* Meiryo
* BIZ UDGothic

CJK fonts at [fonts.google.com] are tested in the [chws_tool] package.
Several other fonts were also tested during the development.

When adding the features to your fonts,
the [test HTML] is a handy tool to check the results.
If you encounter any problems with your fonts,
please report to [issues].

Please also see the [Advanced Topics] below
if you want to customize the default behaviors for your fonts.

[chws_tool]: https://github.com/googlefonts/chws_tool
[fonts.google.com]: https://fonts.google.com
[issues]: https://github.com/kojiishi/east_asian_spacing/issues
[Noto CJK]: https://github.com/googlefonts/noto-cjk

### TrueType Collection (TTC)

When the input font file is a TrueType Collection (TTC),
this tool adds the feature to all fonts in the TTC by default.

If you want to add the feature to only some of fonts in the TTC,
you can specify a comma-separated list of font indices.
The following example adds the feature to the font index 0 and 1,
but not to other fonts in the TTC.
```shell-session
east-asian-spacing --index=0,1 input-font-file.ttc
```

## API


### Install Package
[install package]: #install-package

You can install this package
using your favorite package management tools
such as [uv], [poetry], [pipenv], or [pip].
```shell-session
pip install east-asian-spacing
```
```shell-session
pipenv install east-asian-spacing
```
```shell-session
poetry add east-asian-spacing
```
```shell-session
uv add east-asian-spacing
```

Please also see the [clone and install] section
if you want to diagnose fonts or the code in more details.


### Sample Code

The following example creates a font with the features
in the "`build`" directory if the features are applicable.
```python
import east_asian_spacing

async def main_async():
    builder = east_asian_spacing.Builder("fonts/input.otf")
    output_path = await builder.build_and_save("build")
    if output_path:
        print(f"Saved to {output_path}")
    else:
        print("Skipped")
```

## Testing
[testing]: #testing

### Test HTML
[test HTML]: #test-html

A [test HTML page] is available
to check the behavior of fonts on browsers.

It can test fonts you built locally.
1. Save the page to your local drive.
   The HTML is a single file, saving the HTML file should work.
2. Add your font files to the "`fonts`" list
   at the beginning of the `<script>` block.
3. Open it in your browser and choose your font.

Note, when you want to test a TTC (TrueType Collection)
but your browser can load only the first font in the TTC,
the following command extracts all OpenType fonts (.otf or .ttf)
from an OpenType Collection font file (.ttc or .otc).
```shell-session
east-asian-spacing ttc build/NotoSansCJK-Regular.ttc
```

[test HTML page]: https://kojiishi.github.io/chws/test.html

### Dump
[dump]: #dump

The `dump` sub-command can create various types of text dump files.

The most simple usage is to show a list of tables.
This is similar to the "`-l`" option of [TTX],
except for TrueType Collections (TTC),
this tool can show tables of all fonts in the TTC,
along with which tables are shared with which fonts.
```shell-session
east-asian-spacing dump build/NotoSansCJK-Regular.ttc
```

The "`-o`" option creates table list files in the specified directory:
```shell-session
east-asian-spacing dump -o build/dump build/*.ttc
```
The "`--ttx`" option creates [TTX] text dumps of all tables
in addition to the table list files.
This is similar to the "`-s`" option of [TTX],
except that it can dump all tables in TrueType Collections (TTC).
```shell-session
east-asian-spacing dump -o build/dump --ttx build/*.ttc
```

[TTX]: https://fonttools.readthedocs.io/en/latest/ttx.html

### Diff
[diff]: #diff
[checking the differences]: #diff

The `dump` sub-command can also create
[dump] files of two font files and compare them.
This helps visualizing differences in two fonts,
specifically, the font files you created from the original font files.
```shell-session
east-asian-spacing dump -o build/diff --diff source_fonts_dir build/NotoSansCJK.ttc
```
The example above
computes the differences between
`source_fonts_dir/NotoSansCJK.ttc` and `build/NotoSansCJK.ttc`
by creating following 3 sets of files:
1. The table list and TTX text dump files for `build/NotoSansCJK.ttc`
   in the `build/diff/dump` directory.
2. The table list and TTX text dump files for `source_fonts_dir/NotoSansCJK.ttc`
   in the `build/diff/src` directory.
3. Diff files of the two sets of dump files in the `build/diff` directory.

> Note:
The "`--diff`" option is more efficient than doing all these,
especially for large fonts,
because it skips creating TTX of tables when they are binary-equal.

The `-o` option is optional. When it is omitted,
the sub-command outputs the diff to `stdout`.
```shell-session
east-asian-spacing dump --diff source_fonts_dir build/NotoSansCJK.ttc | less
```

To create diff files for all fonts you built,
you can pipe the output as below:
```shell-session
east-asian-spacing -p *.otf | east-asian-spacing dump -o build/diff -
```
The "`-p`" option prints the input and output font paths to `stdout`
in the tab-separated-values format.
The `dump` sub-command with the "`-`" argument reads this list from `stdin`,
and creates their text dump and diff files in the `build/diff` directory.
The "`--diff`" option is not necessary in this case,
because the source font paths are provided from the pipe.

### References
[references]: #references

Once you reviewed the [diff] files created above,
or tested fonts you build,
you can copy the diff files into the `references` directory.
Then when you want to build them again,
such as when the fonts are updated or when the build environment is changed,
you can compare the diff files with the reference files
to know how new fonts are different from previous builds.

With the "`-r`" option, the `dump` sub-command
creates [diff] files between two font files,
and compare the diff files
with once-reviewed diff files in the `references` directory.

The typical usage of this option is as below:
```shell-session
east-asian-spacing -p -g=build/glyphs *.otf |
    east-asian-spacing dump -o=build/diff -r=references -
```
Please see the [Diff] section for the "`-p`" option and piping.

The `build*.sh` [scripts] include this option.

### Shape Test
[shape tests]: #shape-test

The shape testing shapes test strings
and checks whether the contextual spacing is applied or not.

The `--test` option sets the level of the shape testing.
```shell-session
east-asian-spacing --test 2 -v -o build input-font-file
```
The level 0 disables the shape testing.
The level 1 runs a smoke test using a small set of samples.
The level 2 runs the shape testing using a large set of test strings.
The default value is 1.

## Advanced Topics
[Advanced Topics]: #advanced-topics

### Algorithm
[Algorithm]: #algorithm

The algorithm is language agnostic and is applicable to any CJK fonts.

This package determines the glyph pairs to adjust spacings
by a set of Unicode code points
defined in the [`Config` class].

Then for each pair, it checks if the spacings are applicable
by examining glyph outlines and computing ink bounding boxes of glyphs.
For example, when glyphs are very thick,
glyphs may not have enough internal spacings,
and applying the spacings may cause glyphs to collide.
This package automatically detects such cases and
avoids applying spacings to such pairs.

This automatic behavior can be disabled
by specifying the [languages] below,
or by setting `Config.use_ink_bounds` to `False` in your Python program.

### Languages
[languages]: #languages

There are language-specific conventions
for where punctuation characters are placed in the glyph spaces.
For example,
U+3002 IDEOGRAPHIC FULL STOP
should be placed at the left-bottom corner of the glyph space in Japanese,
while it should be placed at the center in Traditional Chinese.

By default,
this package determines such differences from glyph outlines
as described in the [Algorithm] section above.
But you can specify the [OpenType language system tag]
to let this package follow the language convention
instead of using glyph outlines.
The following example
disables the automatic determination by glyph outlines,
and specifies that the font is a Japanese font.
```shell-session
east-asian-spacing --language=JAN input-font-file
```

For TrueType Collections (TTC),
the language option applies to all fonts in the TTC by default.
When you want to specify different languages to each font in the TTC,
it accepts a comma-separated list.
The following example specifies
Korean for the font index 1,
Simplified Chinese for the font index 2,
and automatic for all other fonts.
```shell-session
east-asian-spacing --language=,KOR,ZHS input-font-file.ttc
```

You can combine these two options.
The following example applies
`JAN` to the index 2,
and `ZHS` to the index 3.
Other fonts in the TTC are not changed.
```shell-session
east-asian-spacing --index=2,3 --language=JAN,ZHS input-font-file.ttc
```

[OpenType language system tag]: https://docs.microsoft.com/en-us/typography/opentype/spec/languagetags

### Character-Pairs

You may want to adjust which character-pairs should adjust spacings,
in cases such as when
your fonts may not have expected spacings for some characters.
Currently, this is possible only from Python programs.

For a simple example, please see the `test_config` function
in [`tests/config_test.py`].

The [chws_tool] project is an actual example of customizing this package.

[`Config` class]: https://github.com/kojiishi/east_asian_spacing/blob/main/east_asian_spacing/config.py
[`tests/config_test.py`]: https://github.com/kojiishi/east_asian_spacing/blob/main/tests/config_test.py

### HarfBuzz

This package uses the [HarfBuzz] shaping engine
by using a Cython bindings [uharfbuzz].

If you want to use a specific build of the [HarfBuzz],
this tool can invoke the external [hb-shape] command line tool instead
by setting the `SHAPER` environment variable.
```shell-session
export SHAPER=hb-shape
```

To install [hb-shape] for Linux:
```shell-session
sudo apt get libharfbuzz-bin
```
To install [hb-shape] for Mac with [homebrew]:
```shell-session
brew install harfbuzz
```
Instructions for other platforms may be available at
[command-not-found.com](https://command-not-found.com/hb-shape).

[HarfBuzz]: https://github.com/harfbuzz/harfbuzz
[hb-shape]: https://harfbuzz.github.io/utilities.html#utilities-command-line-hbshape
[homebrew]: https://brew.sh/
[uharfbuzz]: https://github.com/harfbuzz/uharfbuzz


### Clone and Install
[clone and install]: #clone-and-install

If you may need to diagnose fonts or the code,
cloning and installing using [uv] is recommended:
```shell-session
git clone https://github.com/kojiishi/east_asian_spacing
cd east_asian_spacing
uv sync
uv tool install -e .
. .venv/bin/activate
```
This method has following advantages:
* Installs the exact versions of dependencies.
* Installs in the editable mode
(i.e., [pip "`-e`" option] or `setuptools` "[development mode]").
* Installs testing tools too.
You can run [unit tests] to verify your installation if needed.
* Creates the virtual environment automatically.

You can also install the cloned directory using [pip] if you prefer:
```shell-session
git clone https://github.com/kojiishi/east_asian_spacing
cd east_asian_spacing
pip install .
```

### Unit Tests
[unit tests]: #unit-tests

This repository contains unit tests using [pytest].
The unit tests cover the basic functionalities
including [shape tests],
adding the feature to a test font,
and comparing it with [references].

If you followed the [clone and install] section,
tools for unit testing are already installed.
Before you run them first time,
you need to download fonts for testing:
```shell-session
./tests/download_fonts.py
```

You can then run the tests by:
```shell-session
pytest
```
or run them with multiple versions of Python using [tox]:
```shell-session
tox
```

[pytest]: https://pytest.org/
[tox]: https://tox.readthedocs.io/en/latest/index.html

### Scripts
[scripts]: #scripts

The `scripts` directory has some small shell scripts.

`build*.sh` scripts are useful to build fonts,
compute [diff] from source fonts,
and compare the diff files with [references].
Followings are example usages.
```shell-session
./scripts/build.sh input-font-file.otf -v
./scripts/build-noto-cjk.sh ~/fonts/noto-cjk -v
```
