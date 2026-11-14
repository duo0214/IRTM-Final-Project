"""B's implementation slot. Do not relabel the reference scanner as PAT-tree."""
class PATTreeIndex:
    backend = 'pat_tree'

    def __init__(self, documents):
        raise NotImplementedError('B: implement PAT-tree, then swap factory in src/services.py')

    def lookup(self, phrase):
        """Match ReferencePhraseIndex.lookup response; original-text Unicode offsets."""
        raise NotImplementedError
