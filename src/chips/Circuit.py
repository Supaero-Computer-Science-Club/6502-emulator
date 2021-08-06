from utils import string_pins
from utils import to_hex
from utils import to_bin

from chips.memory import Memory64
from chips.pins import M65C02_RWB
from chips.pins import M65C02_PHI2


class Circuit:
    def __init__(self, pins, cpu, ram, rom):
        self.pins = pins
        self.cpu = cpu
        self.ram = ram
        self.rom = rom
        self.memory = Memory64(ram, rom)

        self.lines = []

    def update(self, stdscr):
        addr = self.cpu._GA()
        data = self.cpu._GD()
        RWB = self.pins&M65C02_RWB

        if RWB:
            data = self.memory[addr]
            self.cpu._SD(data)
        else:
            self.memory[addr] = data

        self.pins = self.cpu.tick(self.pins)

        if ((self.pins & M65C02_PHI2)):
            line = string_pins(self.pins)
            line += ' '.join([to_hex(addr, 4), ('r' if RWB else 'W'), to_hex(data, 2)])
            self.lines.append(line)
            if len(self.lines) > stdscr.getmaxyx()[0]//2:
                self.lines.pop(0)

    def flip(self, stdscr):
        stdscr.erase()
        for row, line in enumerate(self.lines):
            stdscr.addstr(row, 0, line)

        y = stdscr.getmaxyx()[0]//2
        self.cpu.flip(stdscr, 0, 100)
        self.ram.flip(stdscr, y+1, 0)
        self.rom.flip(stdscr, y+1, 80)
        stdscr.refresh()
