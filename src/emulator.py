import argparse
import numpy as np
from pynput import keyboard
import traceback

from opcodes import opcodes


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
            print(traceback.format_exc())
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

    cpu.cycle()


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

    cpu.cycle()

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


class CPU:
    def __init__(self, ram, rom, via):
        # internals.
        self._A  = 0x00
        self._X  = 0x00
        self._Y  = 0x00
        self._SP = 0x00
        self._PC = np.random.randint(65536)

        self._ram = ram
        self._rom = rom
        self._via = via

        self.memory = Memory64(ram, rom)

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

        self._state = ["code", 0]

    def cycle(self):
        # reset the CPU:
        if self.RESB == LOW:
            self._A  = 0x00
            self._X  = 0x00
            self._Y  = 0x00
            self._SP = 0x0124

            self._state = ["reset", 9]


        if (self.PHI2) and (self.PHI2 != self._PHI2):
            if self._state[0] == "reset":
                if self._state[1] == 2:
                    self.addr = 0xfffc
                    self.data = self.memory[self.addr]
                    self.RWB = 1
                    self._PC = self.data
                elif self._state[1] == 1:
                    self.addr += 1
                    self.data = self.memory[self.addr]
                    self.RWB = 1
                    self._PC += (self.data << 8)
                else:
                    self.addr = np.random.randint(65536)
                self._state[1] -= 1
                if not self._state[1]:
                    self._state[0] = "fetch"

            elif self._state[0] == "fetch":
                self.addr = self._PC
                self.RWB = 1
                self.data = self.memory[self.addr]

                opcode = self.data
                instr, addr_mode, nb_ucodes = opcodes[opcode]

            elif self._state[0] == "decode":
                pass
            elif self._state[0] == "execute":
                pass

                self._PC = (self._PC + 1) % 65536

            print(f"\r{self}")

        self._PHI2 = self.PHI2

    def __str__(self):
        msg = to_bin(self.addr, 17) + ' ' + to_bin(self.data, 8) + ' ' 
        msg += to_hex(self.addr, 4) + ' ' + ('r' if self.RWB else 'W') + ' ' + to_hex(self.data, 2)
        return msg


def main():
    parser = argparse.ArgumentParser("parser to help the architecture of the 6502-based machine.")

    parser.add_argument("--ram-bits", "-rb", default=15,
                        help="the number of bits used by RAM (defaults to 15).")
    parser.add_argument("--ram-org", "-ao", default=0x0000,
                        help="the base address of RAM (defaults to $0000).")
    parser.add_argument("--rom-file", "-rf", default="bin/a.out",
                        help="the ROM file (defaults to'bin/a.out').")
    parser.add_argument("--rom-org", "-oo", default=0x8000,
                        help="the base address of ROM (defaults to $8000).")

    args = parser.parse_args()

    # put RAM in circuit.
    ram = RAM(bits=args.ram_bits)
    ram.set_org(args.ram_org)

    # put ROM in circuit.
    rom = ROM(args.rom_file)
    rom.set_org(args.rom_org)

    # put Versatile Interface Adapter in circuit.
    via = None

    # put CPU in the circuit.
    # wire it with RAM, ROM and Interface.
    cpu = CPU(ram, rom, via)

    # wire permanent pins of the CPU.
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
    cpu.RESB  = HIGH

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
