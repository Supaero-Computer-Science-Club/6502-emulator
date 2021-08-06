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
M65C02_BRK_IRQ   = (1<<0)
M65C02_BRK_NMI   = (1<<1)
M65C02_BRK_RESET = (1<<2)

