import argparse
import numpy as np
from pynput import keyboard
import traceback

from opcodes import opcodes
from mos65c02 import M65C02
from mos65c02 import *

from utils import print8
from utils import to_bin
from utils import to_hex


LOW  = 0
HIGH = 5

def cpu_wrapper(func, cpu, circuit):
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
            func(*args, cpu=cpu, circuit=circuit, **kwargs)
        except Exception as e:  # looking for real exceptions to handle, temporary.
            print(f"EXCEPTION of type {type(e)} SKIPPED:", e)
            print(traceback.format_exc())
    return wrapped_func


def on_press(key, cpu, circuit, prt=print):
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
            circuit.pins |= M65C02_PHI2
        elif key.char.lower() == 'r':
            circuit.pins &= (M65C02_RESB ^ ((1<<40) - 1))

    circuit.pins = cpu.tick(circuit.pins)


def on_release(key, cpu, circuit, prt=print):
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
            circuit.pins &= (M65C02_PHI2 ^ ((1<<40) - 1))
        elif key.char.lower() == 'r':
            circuit.pins |= M65C02_RESB

    circuit.pins = cpu.tick(circuit.pins)


class Circuit:
    def __init__(self, pins):
        self.pins = pins


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
    pins = 0b0000000000000000000000000000000000000000
    pins |= (M65C02_VCC|M65C02_RDY|M65C02_IRQB|M65C02_NMIB|M65C02_BE|M65C02_RESB|M65C02_SYNC)
    circuit = Circuit(pins)
    cpu = M65C02()

    # collect events until released.
    with keyboard.Listener(
            on_press=cpu_wrapper(on_press, cpu, circuit),
            on_release=cpu_wrapper(on_release, cpu, circuit)) as listener:
        listener.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("clean exit")
