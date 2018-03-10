# -*- coding: utf-8 -*-
from collections import defaultdict
import json
from itertools import product
import os

try:
    xrange
except NameError:
    # python3
    pass
else:
    # python2
    range = xrange  # noQA
    chr = unichr    # noQA


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Actions if char not in alphabet
STRATEGY_LOAD = 1       # load category for this char
STRATEGY_IGNORE = 2     # add char to result
STRATEGY_REMOVE = 3     # remove char from result


class Categories(object):
    """
    Work with aliases from ISO 15924.
    https://en.wikipedia.org/wiki/ISO_15924#List_of_codes
    """
    fpath = os.path.join(CURRENT_DIR, 'categories.json')

    @classmethod
    def _get_ranges(cls, categories):
        """
        :return: iter: (start code, end code)
        :rtype: list
        """
        with open(cls.fpath) as f:
            data = json.load(f)
        indexes = []
        for category in categories:
            try:
                indexes.append(data['iso_15924_aliases'].index(category))
            except ValueError:
                raise ValueError('Invalid category: {}'.format(category))
        for point in data['code_points_ranges']:
            if point[2] in indexes:
                yield point[:2]

    @classmethod
    def get_alphabet(cls, categories):
        """
        :return: set of chars in alphabet by categories list
        :rtype: set
        """
        alphabet = set()
        for start, end in cls._get_ranges(categories):
            chars = (chr(code) for code in range(start, end))
            alphabet.update(set(chars))
        return set(alphabet)

    @classmethod
    def detect(cls, char):
        """
        :return: category
        :rtype: str
        """
        with open(cls.fpath) as f:
            data = json.load(f)
        code = ord(char)
        for point in data['code_points_ranges']:
            if point[0] <= code <= point[1]:
                return data['iso_15924_aliases'][point[2]]


class Languages(object):
    fpath = os.path.join(CURRENT_DIR, 'languages.json')

    @classmethod
    def get_alphabet(cls, languages):
        """
        :return: set of chars in alphabet by languages list
        :rtype: set
        """
        with open(cls.fpath) as f:
            data = json.load(f)
        alphabet = set()
        for lang in languages:
            if lang not in data:
                raise ValueError('Invalid language code: {}'.format(lang))
            alphabet.update(data[lang])
        return alphabet

    @classmethod
    def detect(cls, char):
        """
        :return: set of languages which alphabet contains passed char.
        :rtype: set
        """
        with open(cls.fpath) as f:
            data = json.load(f)
        languages = set()
        for lang, alphabet in data.items():
            if char in alphabet:
                languages.add(lang)
        return languages


class Homoglyphs(object):
    def __init__(self, categories=('LATIN', 'COMMON'), languages=None, alphabet=None,
                 strategy=STRATEGY_IGNORE, ascii_strategy=STRATEGY_IGNORE):
        # strategies
        if strategy not in (STRATEGY_LOAD, STRATEGY_IGNORE, STRATEGY_REMOVE):
            raise ValueError('Invalid strategy')
        self.strategy = strategy
        self.ascii_strategy = ascii_strategy

        # cats and langs
        self.categories = set(categories or [])
        self.languages = set(languages or [])

        # alphabet
        self.alphabet = set(alphabet or [])
        if self.categories:
            alphabet = Categories.get_alphabet(self.categories)
            self.alphabet.update(alphabet)
        if self.languages:
            alphabet = Languages.get_alphabet(self.languages)
            self.alphabet.update(alphabet)
        self.table = self.get_table(self.alphabet)

    @staticmethod
    def get_table(alphabet):
        table = defaultdict(list)
        with open(os.path.join(CURRENT_DIR, 'confusables.json')) as f:
            data = json.load(f)
        for char in alphabet:
            if char in data:
                for homoglyph in data[char]:
                    if homoglyph['c'] in alphabet:
                        table[char].append(homoglyph['c'])
        return table

    @staticmethod
    def uniq_and_sort(data):
        result = list(set(data))
        result.sort(key=lambda x: (-len(x), x))
        return result

    def _update_alphabet(self, char):
        # try detect languages
        langs = Languages.detect(char)
        if langs:
            self.languages.update(langs)
            alphabet = Languages.get_alphabet(langs)
            self.alphabet.update(alphabet)
        else:
            # try detect categories
            category = Categories.detect(char)
            if category is None:
                return False
            self.categories.add(category)
            alphabet = Categories.get_alphabet([category])
            self.alphabet.update(alphabet)
        # update table for new alphabet
        self.table = self.get_table(self.alphabet)
        return True

    def _get_char_variants(self, char):
        if char not in self.alphabet:
            if self.strategy == STRATEGY_LOAD:
                if not self._update_alphabet(char):
                    return []
            elif self.strategy == STRATEGY_IGNORE:
                return [char]
            elif self.strategy == STRATEGY_REMOVE:
                return []

        # find alternative chars for current char
        alt_chars = self.table.get(char, [])
        if alt_chars:
            # find alternative chars for alternative chars for current char
            alt_chars2 = [self.table.get(alt_char, []) for alt_char in alt_chars]
            # combine all alternatives
            alt_chars.extend(sum(alt_chars2, []))
        # add current char to alternatives
        alt_chars.append(char)

        if self.ascii_strategy == STRATEGY_REMOVE:
            alt_chars = [char for char in alt_chars if ord(char) < 256]

        # uniq, sort and return
        return self.uniq_and_sort(alt_chars)

    def _get_combinations(self, text):
        variations = []
        for char in text:
            alt_chars = self._get_char_variants(char)
            if alt_chars:
                variations.append(alt_chars)
        for variant in product(*variations):
            yield ''.join(variant)

    def get_combinations(self, text):
        return list(self._get_combinations(text))

    def _to_ascii(self, text):
        for variant in self._get_combinations(text):
            if max(map(ord, variant)) < 256:
                yield variant

    def to_ascii(self, text):
        return self.uniq_and_sort(self._to_ascii(text))