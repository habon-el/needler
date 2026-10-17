"""Cited legacy guidance. Moving text here must not change algorithm values."""
from functools import lru_cache
from .knowledge_store import load_knowledge


@lru_cache(maxsize=1)
def messages():
    book=load_knowledge()['legacy.json']
    return {row['id']:dict(row,version=book['version']) for row in book['rows']}


def message(ident, **values):
    row=messages()[ident]
    text=row['text'].format(**values)
    return text+f" [legacy.json#{ident} v{row['version']}; recorded code assumption, not shop-verified]"
