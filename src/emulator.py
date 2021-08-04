import numpy as np


def to_hex(number, nb_chars=2):
    return hex(number)[2:][::-1].ljust(nb_chars, '0')[::-1]


class RAM:
    def __init__(self, bits):
        self._bytes = [0] * 2 ** bits

    def __len__(self):
        return len(self._bytes)

    def __getitem__(self, index):
        return self._bytes[index]

    def __setitem__(self, index, byte):
        self._bytes[index] = byte % 256

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


class ROM(RAM):
    def __init__(self, rom_file):
        self._bytes = tuple([0] * 2 ** 15)

    def __setitem__(self, index, byte):
        pass


def main():
    ram = RAM(bits=15)

    ram._bytes[0x00] = 0x4c
    ram._bytes[0x01] = 0x00
    ram._bytes[0x02] = 0x80

    for b in range(100):
        ram._bytes[b] = np.random.randint(0,256)

    ram._bytes[0x7ffc] = 0x00
    ram._bytes[0x7ffd] = 0x80

    print(len(ram))
    print(ram)
    print()
    ram[0x02] = 0x66
    print(ram)
    print()


    rom = ROM(None)
    print(rom)
    print()
    rom[0x02] = 0x02
    print(rom)
    print()


if __name__ == "__main__":
    main()
