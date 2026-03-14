"""Custom exceptions for Swift UVOT Photometry."""


class FilterError(Exception):
    """Raised when no valid UVOT filter is recognized (e.g. invalid filter list)."""

    def __init__(self):
        super().__init__('No filter recognized.')


class ListError(Exception):
    """Raised when an input list file contains no usable file paths or ObsIDs."""

    def __init__(self, file):
        super().__init__('No usable file found in {}.'.format(file))


class FileNotFound(Exception):
    """Raised when the input file or ObsID cannot be interpreted or found."""

    def __init__(self):
        super().__init__('Cannot interpret input file.')
