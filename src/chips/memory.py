from utils import to_hex


class Memory:
    def __len__(self):
        return len(self._bytes)

    def __getitem__(self, index):
        return self._bytes[index - self._org]

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        lines = []
        _prev_line = ''
        _block_of_bytes = False
        for i in range(0, len(self._bytes), 16):
            line = ' '.join(map(str, [to_hex(self._bytes[i + j]) for j in range(16)]))
            if line != _prev_line:
                _prev_line = line
                ascii_chars = ''.join([chr(self._bytes[i + j]) if 32 <= self._bytes[i + j] <= 127 else '.' for j in range(16)])
                line = to_hex(i, 8) + "  " + line[:23] + "  " + line[24:] + "  " + '|' + ascii_chars + '|' 
                if _block_of_bytes:
                    lines.append('*')
                    _block_of_bytes = False
                lines.append(line)
            else:
                _block_of_bytes = True
        if _block_of_bytes:
            lines.append('*')
        lines.append(to_hex(i + 16, 8))
        return '\n'.join(lines)

    def set_org(self, org):
        self._org = org

    def flip(self, stdscr, y, x):
        for row, line in enumerate(self.__str__().split('\n')):
            stdscr.addstr(y + row, x, line)


class RAM(Memory):
    def __init__(self, bits):
        self._bytes = bytearray([0] * 2 ** bits)
        self._org = 0x0000

    def __setitem__(self, index, byte):
        self._bytes[index - self._org] = byte % 256

    def flip(self, stdscr, y, x):
        stdscr.addstr(y, x, "RAM")
        super().flip(stdscr, y+1, x)


class ROM(Memory):
    def __init__(self, rom_file):
        with open(rom_file, "rb") as file:
            self._bytes = bytearray(file.read())
        self._org = 0x0000

    def __setitem__(self, index, byte):
        pass

    def flip(self, stdscr, y, x):
        stdscr.addstr(y, x, "ROM")
        super().flip(stdscr, y+1, x)


class Memory64(Memory):
    def __init__(self, ram, rom):
        self._orgs = [(ram._org, ram._org + len(ram) - 1, ram),
                      (rom._org, rom._org + len(rom) - 1, rom)]
        self._orgs.sort()
        for i in range(len(self._orgs) - 1):
            if self._orgs[i][1] >= self._orgs[i + 1][0]:
                raise ValueError("wrong value encountered for memory map.")
        if self._orgs[-1][1] >= 65536:
            raise ValueError("memory map too big for 64k.")

    def __getitem__(self, index):
        for i in range(len(self._orgs)):
            if self._orgs[i][0] <= index <= self._orgs[i][1]:
                return self._orgs[i][-1][index]

    def __setitem__(self, index, byte):
        for i in range(len(self._orgs)):
            if self._orgs[i][0] <= index <= self._orgs[i][1]:
                self._orgs[i][-1][index] = byte % 256
                break

