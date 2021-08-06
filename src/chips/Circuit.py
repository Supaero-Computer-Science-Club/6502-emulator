from utils import to_hex
from utils import to_bin

from chips.memory import Memory64
from chips.pins import M65C02_RWB
from chips.pins import M65C02_PHI2


class Circuit:
    def __init__(self, pins, cpu, ram, rom):
        self.pins = pins
        self.prev_pins = 0
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

        if (not (self.prev_pins&M65C02_PHI2) and (self.pins&M65C02_PHI2)):
            line = ' '.join([to_hex(addr, 4), ('r' if RWB else 'W'), to_hex(data, 2)])
            self.lines.append(line)
            if len(self.lines) > stdscr.getmaxyx()[0]:
                self.lines.pop(0)

    def flip(self, stdscr):
        stdscr.erase()
        for row, line in enumerate(self.lines):
            stdscr.addstr(row, 0, line)

        self.cpu.flip(stdscr, 0, 10)
        self.ram.flip(stdscr, 23, 45)
        self.rom.flip(stdscr, 23, 125)
        stdscr.refresh()
