from utils import to_bin

import numpy as np
_RD = lambda bits: np.random.randint(1<<bits)

# define all the pins of the MOS 65c02 chip.
# control lines.
M65C02_VPB   = (1<<0)
M65C02_RDY   = (1<<1)
M65C02_PHI1O = (1<<2)
M65C02_IRQB  = (1<<3)
M65C02_MLB   = (1<<4)
M65C02_NMIB  = (1<<5)
M65C02_SYNC  = (1<<6)
# address lines.
M65C02_A0    = (1<<7)
M65C02_A1    = (1<<8)
M65C02_A2    = (1<<9)
M65C02_A3    = (1<<10)
M65C02_A4    = (1<<11)
M65C02_A5    = (1<<12)
M65C02_A6    = (1<<13)
M65C02_A7    = (1<<14)
M65C02_A8    = (1<<15)
M65C02_A9    = (1<<16)
M65C02_A10   = (1<<17)
M65C02_A11   = (1<<18)
M65C02_A12   = (1<<19)
M65C02_A13   = (1<<20)
M65C02_A14   = (1<<21)
M65C02_A15   = (1<<22)
# data lines.
M65C02_D0    = (1<<23)
M65C02_D1    = (1<<24)
M65C02_D2    = (1<<25)
M65C02_D3    = (1<<26)
M65C02_D4    = (1<<27)
M65C02_D5    = (1<<28)
M65C02_D6    = (1<<29)
M65C02_D7    = (1<<30)
# control lines.
M65C02_RWB   = (1<<31)
M65C02_NC    = (1<<32)
M65C02_BE    = (1<<33)
M65C02_PHI2  = (1<<34)
M65C02_SOB   = (1<<35)
M65C02_PHI2O = (1<<36)
M65C02_RESB  = (1<<37)
# power.
M65C02_VCC   = (1<<38)
M65C02_GND   = (1<<39)

# pin mask for all the pins of the 65c02 chip.
M65C02_PIN_MASK = ((1<<40)-1)

# internal status register bits.
M65C02_CF = (1<<0)
M65C02_ZF = (1<<1)
M65C02_IF = (1<<2)
M65C02_DF = (1<<3)
M65C02_BF = (1<<4)
M65C02_XF = (1<<5)
M65C02_VF = (1<<6)
M65C02_NF = (1<<7)

# internal BRK vector.
M65C02_IRQ   = (1<<0)
M65C02_NMI   = (1<<1)
M65C02_RESET = (1<<2)


class M65C02:
    def __init__(self, pins):
        # all internal, and thus private, fields are marked with '_'.
        self._IR_   = 0x00   # instruction register.
        self._PC_   = 0x00   # program counter.
        self._AD_   = 0x0000 # address register.
        self._A_    = 0x00   # accumulator.
        self._X_    = 0x00   # X register.
        self._Y_    = 0x00   # Y register.
        self._S_    = 0x00   # stack pointer.
        self._P_    = 0x00   # status register.
        self._PINS_ = pins   # last pins.

        self._state = ["code", 0]

    def tick(self, pins):
        next_pins = pins
        if ((pins & M65C02_PHI2) & ((M65C02_PHI2 & self._PINS_) ^ ((1<< 40) - 1))):
            bin_pins = to_bin(pins, 40)
            print(' '.join([bin_pins[:9], bin_pins[9:17], bin_pins[17:33], bin_pins[33:]]))

            if (pins & (M65C02_SYNC|M65C02_IRQB|M65C02_NMIB|M65C02_RDY|M65C02_RESB)):
                # NMIB: low-edge-transition triggered.
                if pins & (pins ^ self._PINS_) & M65C02_NMIB:
                    print("NMIB")

                # IRQB: low-level triggered.
                if (pins & M65C02_IRQB) & (not (self._P_ & M65C02_IF)):
                    print("IRQB")

            # reset the CPU:
            if pins & M65C02_RESB == 0:
                self._A_ = 0x00
                self._X_ = 0x00
                self._Y_ = 0x00
                self._S_ = 0x0124

                self._state = ["reset", 9]
                next_pins &= (M65C02_RESB ^ ((1<<40) - 1))
                self._PINS_ = pins
                return next_pins

            if self._state[0] == "reset":
                if self._state[1] == 2:
                    self.__AD__ = 0xfffc
                    next_pins &= ((1<<40) - 1) & (self.__AD__<<7)
                    next_pins |= M65C02_RWB
                    print("\rNEXT2:")
                    print(f"\r{to_bin(((1<<40) - 1) & (self.__AD__<<7), 40)}")
                    print(f"\r{to_bin(next_pins, 40)}")
                    self._PC_ = pins & ((M65C02_D7 - 1) - (M65C02_D0 - 1))
                elif self._state[1] == 1:
                    self.__AD__ += 1
                    next_pins &= (((1<<40) - 1) & (self.__AD__<<7))
                    next_pins |= (M65C02_RWB)
                    print("NEXT1:", next_pins)
                    self._PC_ += ((pins & ((M65C02_D7 - 1) - (M65C02_D0 - 1)))<<8)
                else:
                    next_pins ^= (_RD(16)<<7)
                self._state[1] -= 1
                if not self._state[1]:
                    self._state[0] = "fetch"

            elif self._state[0] == "fetch":
                print("FETCH")
                self.addr = self._PC
                self.RWB = 1
                self.data = self.memory[self.addr]

                self._IR = self.data
                instr, addr_mode, nb_ucodes = opcodes[self._IR]

            elif self._state[0] == "decode":
                print("DECODE")
            elif self._state[0] == "execute":
                print("EXECUTE")

                self._PC = (self._PC + 1) % 65536

#            print(f"\r{self}")

        self._PINS_ = pins
        return next_pins


