import sys

sys.path.append('.')
from Builder import Builder

def calc_indices_and_languages(num_fonts, indices, language):
  return list(Builder.calc_indices_and_languages(num_fonts, indices, language))

def test_calc_indices_and_languages():
  assert calc_indices_and_languages(3, None, None) == [(0, None), (1, None), (2, None)]
  assert calc_indices_and_languages(3, None, 'JAN') == [(0, 'JAN'), (1, 'JAN'), (2, 'JAN')]
  assert calc_indices_and_languages(3, None, 'JAN,') == [(0, 'JAN'), (1, ''), (2, None)]
  assert calc_indices_and_languages(3, None, 'JAN,ZHS') == [(0, 'JAN'), (1, 'ZHS'), (2, None)]
  assert calc_indices_and_languages(3, None, ',JAN') == [(0, ''), (1, 'JAN'), (2, None)]

  assert calc_indices_and_languages(4, '0', None) == [(0, None)]
  assert calc_indices_and_languages(4, '0,2', None) == [(0, None), (2, None)]

  assert calc_indices_and_languages(4, '0', 'JAN') == [(0, 'JAN')]
  assert calc_indices_and_languages(4, '0,2', 'JAN') == [(0, 'JAN'), (2, 'JAN')]
  assert calc_indices_and_languages(4, '0,2', 'JAN,ZHS') == [(0, 'JAN'), (2, 'ZHS')]
  assert calc_indices_and_languages(6, '0,2,5', 'JAN,ZHS') == [(0, 'JAN'), (2, 'ZHS'), (5, None)]
  assert calc_indices_and_languages(6, '0,2,5', 'JAN,,ZHS') == [(0, 'JAN'), (2, ''), (5, 'ZHS')]
