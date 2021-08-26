class BidirectionalIterator:
    __slots__ = {"collection", "index"}

    def __init__(self, collection):
        self.collection = collection
        self.index = -1

    def next(self):
        self.index += 1
        if self.index + 1 > len(self.collection):
            raise StopIteration
        return self.collection[self.index]

    def prev(self):
        self.index -= 1
        if self.index < 0:
            raise StopIteration
        return self.collection[self.index]

    def __len__(self):
        return len(self.collection)
