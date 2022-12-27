
class Modifs:

    def __init__(self):
        self.control = False
        self.shift = False
        self.alt = False
        self.win = False

    def __repr__(self):
        return self.to_string()

    def to_string(self):
        s = ""
        if self.control:
            s += "^"
        if self.shift:
            s += "+"
        if self.alt:
            s += "%"
        if self.win:
            s += "w"

        return s

