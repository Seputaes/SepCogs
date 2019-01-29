class O(object):
    def __init__(self, i):
        self.i = i

    def __eq__(self, other):
        return other.i == self.i

    def __hash__(self):
        return self.i


one = O(1)
two = O(1)


s = {one}

s.add(two)

print(s)
