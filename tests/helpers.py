"""Plain helpers shared by the test modules.

Nothing here imports the repository code, so it is safe to import before the
stubs in ``conftest.py`` are in place.
"""

AUTH_HEADER = {"Authorization": "Bearer fake-token"}


class Blob:
    """Stand-in for a google.cloud.storage Blob."""

    def __init__(self, name, content_type="image/gif"):
        self.name = name
        self.content_type = content_type


class _Segment:
    def __init__(self, start, end):
        self.start_index = start
        self.end_index = end


class _TextAnchor:
    def __init__(self, segments):
        self.text_segments = segments


class _Layout:
    def __init__(self, segments):
        self.text_anchor = _TextAnchor(segments)


class _Cell:
    def __init__(self, layout):
        self.layout = layout


class _Row:
    def __init__(self, cells):
        self.cells = cells


class _Table:
    def __init__(self, header_rows, body_rows):
        self.header_rows = header_rows
        self.body_rows = body_rows


class _Page:
    def __init__(self, tables):
        self.tables = tables


class _Document:
    def __init__(self, text, pages):
        self.text = text
        self.pages = pages


def build_document(header_rows, body_rows):
    """Build a fake Document AI document.

    Cell values are appended to a shared text buffer and each cell records the
    real start/end offsets, so ``DocAI._get_text`` resolves them exactly as it
    would against the live API.
    """
    text_parts = []
    offset = 0

    def make_cell(value):
        nonlocal offset
        start = offset
        text_parts.append(value)
        offset += len(value)
        return _Cell(_Layout([_Segment(start, offset)]))

    headers = [_Row([make_cell(v) for v in row]) for row in header_rows]
    bodies = [_Row([make_cell(v) for v in row]) for row in body_rows]
    return _Document("".join(text_parts), [_Page([_Table(headers, bodies)])])
