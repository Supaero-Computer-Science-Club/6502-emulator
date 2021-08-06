import argparse
from pynput import keyboard
import curses

from chips.mos65c02 import M65C02
from chips.mos65c02 import *

from chips.memory import RAM
from chips.memory import ROM
from chips.Circuit import Circuit

from utils import cpu_wrapper
from utils import on_press
from utils import on_release
from utils import curses_wrapper


@curses_wrapper
def main(stdscr):
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
    cpu = M65C02()
    pins = 0b0000000000000000000000000000000000000000
    pins |= (M65C02_VCC|M65C02_RDY|M65C02_IRQB|M65C02_NMIB|M65C02_BE|M65C02_RESB|M65C02_SYNC)
    circuit = Circuit(pins, cpu, ram, rom)
    cpu.attach_circuit(circuit)

    curses.curs_set(0)
    stdscr.nodelay(1)

    circuit.flip(stdscr)

    # collect events until released.
    with keyboard.Listener(
            on_press=cpu_wrapper(on_press, stdscr, circuit),
            on_release=cpu_wrapper(on_release, stdscr, circuit)) as listener:
        listener.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("clean exit")
