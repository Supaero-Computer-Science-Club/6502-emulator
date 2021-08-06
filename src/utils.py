import os
import curses
import traceback
from pynput import keyboard

from chips.pins import M65C02_PHI2
from chips.pins import M65C02_RESB

# directories initializations.
_root = os.path.dirname(os.path.realpath(__file__)) + "/.."
_log = os.path.join(_root, ".log")
if not os.path.exists(_log):
    os.makedirs(_log)
_log = os.path.join(_log, "log")


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


def string_pins(pins):
    bin_pins = to_bin(pins, 40)
    ctrl1, data, addr, ctrl2 = bin_pins[:9], bin_pins[9:17], bin_pins[17:33], bin_pins[33:]
    msg = f"{ctrl1} "\
          f"{data}-({to_hex(int('0b' + data, 2), 2)}) "\
          f"{addr}-({to_hex(int('0b' + addr, 2), 4)}) "\
          f"{ctrl2}"
    return msg


def print_pins(pins, end='\n'):
    print('\r' + string_pins(pins), end=end)


def log(*args, sep=' ', end='\n'):
    """
        Logs a list of elements inside the './.log/log' file.

        Args
        ----
        args : list of anything with a str method
            all the elements to log into 'log.log'
        sep : str
            the separator between each element.
        end : str
            the end of the final string that will be logged.

        Returns
        -------
        None
    """
    with open(_log, 'a') as file:
        file.write(sep.join(map(str, args)) + end)

def curses_wrapper(func):
    def wrapper(*args, **kwargs):
        log("init")
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        curses.start_color()
        try:
            log("main")
            func(stdscr=stdscr, *args, **kwargs)
        finally:
            log("quit")
            curses.nocbreak()
            stdscr.keypad(False)
            curses.echo()
            curses.endwin()

    return wrapper

def cpu_wrapper(func, stdscr, circuit):
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
            func(*args, stdscr=stdscr, circuit=circuit, **kwargs)
        except Exception as e:  # looking for real exceptions to handle, temporary.
            print(f"EXCEPTION of type {type(e)} SKIPPED:", e)
            print(traceback.format_exc())
    return wrapped_func


def on_press(key, stdscr, circuit, prt=print):
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

    circuit.update(stdscr)
    circuit.flip(stdscr)


def on_release(key, stdscr, circuit, prt=print):
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

    circuit.update(stdscr)
    circuit.flip(stdscr)
