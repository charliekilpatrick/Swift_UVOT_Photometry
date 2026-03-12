# -*- coding: utf-8 -*-
"""Unit tests for SwiftPhotom.errors."""

import pytest

from SwiftPhotom.errors import FileNotFound, FilterError, ListError


class TestFilterError:
    def test_message(self):
        e = FilterError()
        assert "filter" in str(e).lower()

    def test_is_exception(self):
        with pytest.raises(FilterError):
            raise FilterError()


class TestListError:
    def test_message_contains_file(self):
        e = ListError("mylist.lst")
        assert "mylist" in str(e) or "file" in str(e).lower()

    def test_is_exception(self):
        with pytest.raises(ListError):
            raise ListError("x.lst")


class TestFileNotFound:
    def test_message(self):
        e = FileNotFound()
        assert "interpret" in str(e).lower() or "input" in str(e).lower()

    def test_is_exception(self):
        with pytest.raises(FileNotFound):
            raise FileNotFound()
