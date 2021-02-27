from Builder import Builder


def test_calc_indices_and_languages():
    def call(num_fonts, indices, language):
        return list(
            Builder.calc_indices_and_languages(num_fonts, indices, language))

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
