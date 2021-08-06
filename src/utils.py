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


def print_pins(pins, args, end='\n'):
    bin_pins = to_bin(pins, 40)
    ctrl1, data, addr, ctrl2 = bin_pins[:9], bin_pins[9:17], bin_pins[17:33], bin_pins[33:]
    msg = f"{ctrl1} "\
          f"{data}-({to_hex(int('0b' + data, 2), 2)}) "\
          f"{addr}-({to_hex(int('0b' + addr, 2), 4)}) "\
          f"{ctrl2}"
    if len(args) > 0:
        msg += ' '
    for arg, l, s in args:
        msg += f" {to_bin(arg, l)}"
        if s: msg += f"-({s})"
    print('\r' + msg, end=end)
