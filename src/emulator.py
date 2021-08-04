from pynput import keyboard


LOW  = 0
HIGH = 5

def cpu_wrapper(func, cpu):
    """
#        A wrapper that takes care of all possible expections, expecially I/O ones.
#        This wrapper has two main purposes:
#            - avoiding the laptop<->arduino communication to stop because of bugs.
#            - looking for exact expections origin to correct them and make the 
#            communication more robust.
#
#        Args
#        ----
#        func : function
#            the function to wrap, namely on_press or on_release, which read the
#            keyboard strokes.
#        device : serial.serialposix.Serial
#            the device to communicate with, namely an arduino board.
#        scancodes : dict
#            a dictionary of scancodes used by the communication protocol.
#
#        Returns
#        -------
#        wrapped_func : function
#            the wrapped function, doing the same thing, with extra arguments and
#            expection handling to avoid communication protocol failures.
    """
    def wrapped_func(*args, **kwargs):
        try:
            func(*args, cpu=cpu, **kwargs)
        except Exception as e:  # looking for real exceptions to handle, temporary.
            print(f"EXCEPTION of type {type(e)} SKIPPED:", e)
    return wrapped_func


def on_press(key, cpu, prt=print):
    """

        Args
        ----
        key : keyboard._xorg.KeyCode or Key enum.
            a key object given by the pynput.keyboad module, whenever a key is pressed.
        prt : function, optional
            a print-like function. Might be void if no verbose.
    """
    if isinstance(key, keyboard._xorg.KeyCode):
        print('\r', end='')
        if key.char.lower() == 'c':
            cpu.PHI2 = HIGH
        elif key.char.lower() == 'r':
            cpu.RESB = LOW

    cpu.update()


def on_release(key, cpu, prt=print):
    """

        Args
        ----
        key : keyboard._xorg.KeyCode or Key enum.
            a key object given by the pynput.keyboad module, whenever a key is pressed.
        prt : function, optional
            a print-like function. Might be void if no verbose.
    """
    if isinstance(key, keyboard._xorg.KeyCode):
        if key.char.lower() == 'c':
            cpu.PHI2 = LOW
        elif key.char.lower() == 'r':
            cpu.RESB = HIGH

    cpu.update()

def print8(byte):
    print(to_hex(byte, nb_chars=2))

def to_bin(number, nb_bits=8):
    """
        Converts an integer to binary with a given number of bits.

        Args
        ----
        number : int
            the number to convert to binary.
        nb_bits  : int, optional
            the number of bits.

        Returns:
        bin : str
            the string binary representation of the number, with 'nb_bits' bits.
    """
    return bin(number)[2:][::-1].ljust(nb_bits,'0')[::-1]

def to_hex(number, nb_chars=2):
    return hex(number)[2:][::-1].ljust(nb_chars, '0')[::-1]


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


class RAM(Memory):
    def __init__(self, bits):
        self._bytes = bytearray([0] * 2 ** bits)
        self._org = 0x0000

    def __setitem__(self, index, byte):
        self._bytes[index - self._org] = byte % 256


class ROM(Memory):
    def __init__(self, rom_file):
        with open(rom_file, "rb") as file:
            self._bytes = bytearray(file.read())
        self._org = 0x0000

    def __setitem__(self, index, byte):
        pass

class CPU:
    def __init__(self, ram, rom, via):
        # internals.
        self._A  = 0x00
        self._X  = 0x00
        self._Y  = 0x00
        self._SP = 0x00
        self._PC = 0x00

        self._ram = ram
        self._rom = rom
        self._via = via

        # external pins.
        self.VPB   = None
        self.RDY   = None
        self.PHI1O = None
        self.IRQB  = None
        self.MLB   = None
        self.NMIB  = None
        self.SYNC  = None
        self.addr  = 0x0000
        self.data  = 0x00
        self.RWB   = None
        self.BE    = None
        self.PHI2  = None
        self.SOB   = None
        self.PHI2O = None
        self.RESB  = None
        self._PHI2 = None

    def update(self):
        # reset the CPU:
        if self.RESB == LOW:
            self._A  = 0x00
            self._X  = 0x00
            self._Y  = 0x00
            self._SP = 0x0124
            self._PC = 0xfffc

            self.addr = self._PC

        if (self.PHI2) and (self.PHI2 != self._PHI2):
            print(self)

        self._PHI2 = self.PHI2

    def __str__(self):
        msg = to_bin(self.addr, 16) + ' ' + to_bin(self.data, 8) + ' ' + to_hex(self.addr, 4) + ' ' + ('r' if self.RWB else 'W') + ' ' + to_hex(self.data, 2)
        return msg


def main():
    # RAM tests.
    ram = RAM(bits=15)
    ram.set_org(0x0000)

    # ROM tests.
    rom = ROM("bin/a.out")
    rom.set_org(0x8000)

    # CPU tests.
    cpu = CPU(ram, rom, None)

    cpu.VPB   = None  # NC
    cpu.RDY   = HIGH
    cpu.PHI1O = None  # NC
    cpu.IRQB  = HIGH  # disabled for now.
    cpu.MLB   = None  # NC
    cpu.NMIB  = HIGH
    cpu.SYNC  = None  # NC
    cpu.BE    = HIGH
    cpu.PHI2  = None  # NC
    cpu.SOB   = None  # NC
    cpu.PHI2O = None  # NC
    cpu.RESB  = None

    # collect events until released.
    with keyboard.Listener(
            on_press=cpu_wrapper(on_press, cpu),
            on_release=cpu_wrapper(on_release, cpu)) as listener:
        listener.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("clean exit")
