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
M65C02_BRK_IRQ   = (1<<0)
M65C02_BRK_NMI   = (1<<1)
M65C02_BRK_RESET = (1<<2)


class M65C02:
    def __init__(self):
        # all internal, and thus private, fields are marked with '_'.
        self._IR   = 0x00      # instruction register.
        self._PC   = 0x00      # program counter.
        self._AD   = 0x0000    # address register.
        self._A    = 0x00      # accumulator.
        self._X    = 0x00      # X register.
        self._Y    = 0x00      # Y register.
        self._S    = 0x00      # stack pointer.
        self._P    = M65C02_ZF # status register.
        self._PINS = 0         # last pins.

        self._irq_pip   = 0
        self._nmi_pip   = 0
        self._brk_flags = 0b000

        self._bcd_enabled = None

        self._state = ["code", 0]

    def _SA(pins, addr):
        """ set 16-bit address in 64-bit pin mask. """
        return (pins&(((1<<40)-1)&((((1<<16)-1)<<7)^((1<<40)-1))))|(addr<<7)

    def _GA(pins):
        """ extract 16-bit addess from pin mask. """
        return (pins&(((1<<16)-1)<<7))>>7

#define _SAD(addr,data) pins=(pins&~0xFFFFFF)|((((data)&0xFF)<<16)&0xFF0000ULL)|((addr)&0xFFFFULL)
    def _SAD(pins, addr, data):
        """ set 16-bit address and 8-bit data in 64-bit pin mask. """
        pins = M65C02._SA(pins, addr)
        return M65C02._SD(pins, data)

    def _FETCH(pins, c):
        """ fetch next opcode byte. """
        pins = M65C02._SA(pins, c._PC)
        return M65C02._ON(pins, M65C02_SYNC)

    def _SD(pins, data):
        """ set 8-bit data in 64-bit pin mask. """
        return (pins&(((1<<40)-1)&((((1<<8)-1)<<23)^((1<<40)-1))))|(data<<23)

    def _GD(pins):
        """ extract 8-bit data from 64-bit pin mask. """
        return (pins&(((1<<8)-1)<<23))>>23

    def _ON(pins, m):
        """ enable control pins. """
        return pins|m

    def _OFF(pins, m):
        """ disable control pins. """
        return pins&(m^((1<<40)-1))

    def _RD(pins):
        """ a memory read tick. """
        return M65C02._ON(pins, M65C02_RWB)

    def _WR(pins):
        """ a memory write tick. """
        return M65C02._OFF(pins, M65C02_RWB)

    def _NZ(c, v):
        """ set N and Z flags depending on value. """
        c._P=(c._P&((M65C02_NF|M65C02_ZF)^((1<<8)-1)))|((v&M65C02_NF) if (v&0xff) else (M65C02_ZF))

    def tick(self, pins):
        if (not (self._PINS & M65C02_PHI2) and (pins & M65C02_PHI2)) :  # ((pins & M65C02_PHI2) & ((M65C02_PHI2 & self._PINS) ^ ((1<< 40) - 1))):
            bin_pins = to_bin(pins, 40)
            print(' '.join([bin_pins[:9], bin_pins[9:17], bin_pins[17:33], bin_pins[33:]]))

            if ((pins & M65C02_SYNC) or not (pins & M65C02_IRQB) or not (pins & M65C02_NMIB) or (pins & M65C02_RDY) or not (pins & M65C02_RESB)):  # (pins & (M65C02_SYNC|M65C02_IRQB|M65C02_NMIB|M65C02_RDY|M65C02_RESB)):
                # NMIB: low-edge-transition triggered.
                if ((self._PINS & M65C02_NMIB) and not (pins & M65C02_NMIB)):  # (pins & ((pins ^ self._PINS) & M65C02_NMIB)):
                    print("NMIB")

                # IRQB: low-level triggered.
                if (not (pins & M65C02_IRQB) and not (self._P & M65C02_IF)):  # ((pins & M65C02_IRQB) and (not (self._P & M65C02_IF))):
                    print("IRQB")

                # check RDY during read cycles.
                if ((pins & (M65C02_RWB|M65C02_RDY)) == (M65C02_RWB|M65C02_RDY)):
                    pass
                    #print("RDY")

                if (pins & M65C02_SYNC):
                    print("SYNC", end=' ')
                    self._IR = M65C02._GD(pins)<<3
                    pins = M65C02._OFF(pins, M65C02_SYNC)
                    
                    if (0 != (self._irq_pip & 4)):
                        print("IRQ", end=' ')
                        self._brk_flags |= M65C02_BRK_IRQ

                    if (0 != (self._nmi_pip & 0xfffc)):
                        print("NMI", end=' ')
                        self._brk_flags |= M65C02_BRK_NMI

                    if not (pins & M65C02_RESB):
                        print("RESET", end=' ')
                        self._brk_flags |= M65C02_BRK_RESET

                    self._irq_pip &= 3
                    self._nmi_pip &= 3

                    if (self._brk_flags):
                        self._IR  = 0
                        self._P  &= (M65C02_BF^((1<<8)-1))
                    else:
                        self._PC = (self._PC + 1) & ((1<<16)-1)

            pins = M65C02._RD(pins)
            # BRK-s
            if   (self._IR == (0x00<<3|0)): print("00 000"); 
            elif (self._IR == (0x00<<3|1)): print("00 001"); 
            elif (self._IR == (0x00<<3|2)): print("00 010"); 
            elif (self._IR == (0x00<<3|3)): print("00 011"); 
            elif (self._IR == (0x00<<3|4)): print("00 100"); 
            elif (self._IR == (0x00<<3|5)): print("00 101"); 
            elif (self._IR == (0x00<<3|6)): print("00 110"); 
            elif (self._IR == (0x00<<3|7)): print("00 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ORA-(zp,x)                                    
            elif (self._IR == (0x01<<3|0)): print("01 000"); 
            elif (self._IR == (0x01<<3|1)): print("01 001"); 
            elif (self._IR == (0x01<<3|2)): print("01 010"); 
            elif (self._IR == (0x01<<3|3)): print("01 011"); 
            elif (self._IR == (0x01<<3|4)): print("01 100"); 
            elif (self._IR == (0x01<<3|5)): print("01 101"); 
            elif (self._IR == (0x01<<3|6)): print("01 110"); 
            elif (self._IR == (0x01<<3|7)): print("01 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # None                                          
            elif (self._IR == (0x02<<3|0)): print("02 000"); 
            elif (self._IR == (0x02<<3|1)): print("02 001"); 
            elif (self._IR == (0x02<<3|2)): print("02 010"); 
            elif (self._IR == (0x02<<3|3)): print("02 011"); 
            elif (self._IR == (0x02<<3|4)): print("02 100"); 
            elif (self._IR == (0x02<<3|5)): print("02 101"); 
            elif (self._IR == (0x02<<3|6)): print("02 110"); 
            elif (self._IR == (0x02<<3|7)): print("02 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # None                                          
            elif (self._IR == (0x03<<3|0)): print("03 000"); 
            elif (self._IR == (0x03<<3|1)): print("03 001"); 
            elif (self._IR == (0x03<<3|2)): print("03 010"); 
            elif (self._IR == (0x03<<3|3)): print("03 011"); 
            elif (self._IR == (0x03<<3|4)): print("03 100"); 
            elif (self._IR == (0x03<<3|5)): print("03 101"); 
            elif (self._IR == (0x03<<3|6)): print("03 110"); 
            elif (self._IR == (0x03<<3|7)): print("03 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # TSB-zp                                        
            elif (self._IR == (0x04<<3|0)): print("04 000");
            elif (self._IR == (0x04<<3|1)): print("04 001"); 
            elif (self._IR == (0x04<<3|2)): print("04 010"); 
            elif (self._IR == (0x04<<3|3)): print("04 011"); 
            elif (self._IR == (0x04<<3|4)): print("04 100"); 
            elif (self._IR == (0x04<<3|5)): print("04 101"); 
            elif (self._IR == (0x04<<3|6)): print("04 110"); 
            elif (self._IR == (0x04<<3|7)): print("04 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ORA-zp                                        
            elif (self._IR == (0x05<<3|0)): print("05 000"); 
            elif (self._IR == (0x05<<3|1)): print("05 001"); 
            elif (self._IR == (0x05<<3|2)): print("05 010"); 
            elif (self._IR == (0x05<<3|3)): print("05 011"); 
            elif (self._IR == (0x05<<3|4)): print("05 100"); 
            elif (self._IR == (0x05<<3|5)): print("05 101"); 
            elif (self._IR == (0x05<<3|6)): print("05 110"); 
            elif (self._IR == (0x05<<3|7)): print("05 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ASL-zp                                        
            elif (self._IR == (0x06<<3|0)): print("06 000"); 
            elif (self._IR == (0x06<<3|1)): print("06 001"); 
            elif (self._IR == (0x06<<3|2)): print("06 010"); 
            elif (self._IR == (0x06<<3|3)): print("06 011"); 
            elif (self._IR == (0x06<<3|4)): print("06 100"); 
            elif (self._IR == (0x06<<3|5)): print("06 101"); 
            elif (self._IR == (0x06<<3|6)): print("06 110"); 
            elif (self._IR == (0x06<<3|7)): print("06 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # RMB0-zp                                       
            elif (self._IR == (0x07<<3|0)): print("07 000"); 
            elif (self._IR == (0x07<<3|1)): print("07 001"); 
            elif (self._IR == (0x07<<3|2)): print("07 010"); 
            elif (self._IR == (0x07<<3|3)): print("07 011"); 
            elif (self._IR == (0x07<<3|4)): print("07 100"); 
            elif (self._IR == (0x07<<3|5)): print("07 101"); 
            elif (self._IR == (0x07<<3|6)): print("07 110"); 
            elif (self._IR == (0x07<<3|7)): print("07 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # PHP-s                                         
            elif (self._IR == (0x08<<3|0)): print("08 000"); 
            elif (self._IR == (0x08<<3|1)): print("08 001"); 
            elif (self._IR == (0x08<<3|2)): print("08 010"); 
            elif (self._IR == (0x08<<3|3)): print("08 011"); 
            elif (self._IR == (0x08<<3|4)): print("08 100"); 
            elif (self._IR == (0x08<<3|5)): print("08 101"); 
            elif (self._IR == (0x08<<3|6)): print("08 110"); 
            elif (self._IR == (0x08<<3|7)): print("08 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ORA-#                                         
            elif (self._IR == (0x09<<3|0)): print("09 000"); 
            elif (self._IR == (0x09<<3|1)): print("09 001"); 
            elif (self._IR == (0x09<<3|2)): print("09 010"); 
            elif (self._IR == (0x09<<3|3)): print("09 011"); 
            elif (self._IR == (0x09<<3|4)): print("09 100"); 
            elif (self._IR == (0x09<<3|5)): print("09 101"); 
            elif (self._IR == (0x09<<3|6)): print("09 110"); 
            elif (self._IR == (0x09<<3|7)): print("09 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ASL-A                                         
            elif (self._IR == (0x0a<<3|0)): print("0a 000"); 
            elif (self._IR == (0x0a<<3|1)): print("0a 001"); 
            elif (self._IR == (0x0a<<3|2)): print("0a 010"); 
            elif (self._IR == (0x0a<<3|3)): print("0a 011"); 
            elif (self._IR == (0x0a<<3|4)): print("0a 100"); 
            elif (self._IR == (0x0a<<3|5)): print("0a 101"); 
            elif (self._IR == (0x0a<<3|6)): print("0a 110"); 
            elif (self._IR == (0x0a<<3|7)): print("0a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # None                                          
            elif (self._IR == (0x0b<<3|0)): print("0b 000"); 
            elif (self._IR == (0x0b<<3|1)): print("0b 001"); 
            elif (self._IR == (0x0b<<3|2)): print("0b 010"); 
            elif (self._IR == (0x0b<<3|3)): print("0b 011"); 
            elif (self._IR == (0x0b<<3|4)): print("0b 100"); 
            elif (self._IR == (0x0b<<3|5)): print("0b 101"); 
            elif (self._IR == (0x0b<<3|6)): print("0b 110"); 
            elif (self._IR == (0x0b<<3|7)): print("0b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # TSB-a                                         
            elif (self._IR == (0x0c<<3|0)): print("0c 000"); 
            elif (self._IR == (0x0c<<3|1)): print("0c 001"); 
            elif (self._IR == (0x0c<<3|2)): print("0c 010"); 
            elif (self._IR == (0x0c<<3|3)): print("0c 011"); 
            elif (self._IR == (0x0c<<3|4)): print("0c 100"); 
            elif (self._IR == (0x0c<<3|5)): print("0c 101"); 
            elif (self._IR == (0x0c<<3|6)): print("0c 110"); 
            elif (self._IR == (0x0c<<3|7)): print("0c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ORA-a                                         
            elif (self._IR == (0x0d<<3|0)): print("0d 000"); 
            elif (self._IR == (0x0d<<3|1)): print("0d 001"); 
            elif (self._IR == (0x0d<<3|2)): print("0d 010"); 
            elif (self._IR == (0x0d<<3|3)): print("0d 011"); 
            elif (self._IR == (0x0d<<3|4)): print("0d 100"); 
            elif (self._IR == (0x0d<<3|5)): print("0d 101"); 
            elif (self._IR == (0x0d<<3|6)): print("0d 110"); 
            elif (self._IR == (0x0d<<3|7)): print("0d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ASL-a                                         
            elif (self._IR == (0x0e<<3|0)): print("0e 000"); 
            elif (self._IR == (0x0e<<3|1)): print("0e 001"); 
            elif (self._IR == (0x0e<<3|2)): print("0e 010"); 
            elif (self._IR == (0x0e<<3|3)): print("0e 011"); 
            elif (self._IR == (0x0e<<3|4)): print("0e 100"); 
            elif (self._IR == (0x0e<<3|5)): print("0e 101"); 
            elif (self._IR == (0x0e<<3|6)): print("0e 110"); 
            elif (self._IR == (0x0e<<3|7)): print("0e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # BBR0-r                                        
            elif (self._IR == (0x0f<<3|0)): print("0f 000"); 
            elif (self._IR == (0x0f<<3|1)): print("0f 001"); 
            elif (self._IR == (0x0f<<3|2)): print("0f 010"); 
            elif (self._IR == (0x0f<<3|3)): print("0f 011"); 
            elif (self._IR == (0x0f<<3|4)): print("0f 100"); 
            elif (self._IR == (0x0f<<3|5)): print("0f 101"); 
            elif (self._IR == (0x0f<<3|6)): print("0f 110"); 
            elif (self._IR == (0x0f<<3|7)): print("0f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
                                                            
                                                            
            # BPL-r                                         
            elif (self._IR == (0x10<<3|0)): print("10 000"); 
            elif (self._IR == (0x10<<3|1)): print("10 001"); 
            elif (self._IR == (0x10<<3|2)): print("10 010"); 
            elif (self._IR == (0x10<<3|3)): print("10 011"); 
            elif (self._IR == (0x10<<3|4)): print("10 100"); 
            elif (self._IR == (0x10<<3|5)): print("10 101"); 
            elif (self._IR == (0x10<<3|6)): print("10 110"); 
            elif (self._IR == (0x10<<3|7)): print("10 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ORA-(zp),y                                    
            elif (self._IR == (0x11<<3|0)): print("11 000"); 
            elif (self._IR == (0x11<<3|1)): print("11 001"); 
            elif (self._IR == (0x11<<3|2)): print("11 010"); 
            elif (self._IR == (0x11<<3|3)): print("11 011"); 
            elif (self._IR == (0x11<<3|4)): print("11 100"); 
            elif (self._IR == (0x11<<3|5)): print("11 101"); 
            elif (self._IR == (0x11<<3|6)): print("11 110"); 
            elif (self._IR == (0x11<<3|7)): print("11 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # ORA-(zp)                                      
            elif (self._IR == (0x12<<3|0)): print("12 000"); 
            elif (self._IR == (0x12<<3|1)): print("12 001"); 
            elif (self._IR == (0x12<<3|2)): print("12 010"); 
            elif (self._IR == (0x12<<3|3)): print("12 011"); 
            elif (self._IR == (0x12<<3|4)): print("12 100"); 
            elif (self._IR == (0x12<<3|5)): print("12 101"); 
            elif (self._IR == (0x12<<3|6)): print("12 110"); 
            elif (self._IR == (0x12<<3|7)): print("12 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # None                                          
            elif (self._IR == (0x13<<3|0)): print("13 000"); 
            elif (self._IR == (0x13<<3|1)): print("13 001"); 
            elif (self._IR == (0x13<<3|2)): print("13 010"); 
            elif (self._IR == (0x13<<3|3)): print("13 011"); 
            elif (self._IR == (0x13<<3|4)): print("13 100"); 
            elif (self._IR == (0x13<<3|5)): print("13 101"); 
            elif (self._IR == (0x13<<3|6)): print("13 110"); 
            elif (self._IR == (0x13<<3|7)): print("13 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                                            
            # TRB-zp                                        
            elif (self._IR == (0x14<<3|0)): print("14 000"); 
            elif (self._IR == (0x14<<3|1)): print("14 001"); 
            elif (self._IR == (0x14<<3|2)): print("14 010"); 
            elif (self._IR == (0x14<<3|3)): print("14 011"); 
            elif (self._IR == (0x14<<3|4)): print("14 100"); 
            elif (self._IR == (0x14<<3|5)): print("14 101"); 
            elif (self._IR == (0x14<<3|6)): print("14 110"); 
            elif (self._IR == (0x14<<3|7)): print("14 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ORA-zp,x                        
            elif (self._IR == (0x15<<3|0)): print("15 000"); 
            elif (self._IR == (0x15<<3|1)): print("15 001"); 
            elif (self._IR == (0x15<<3|2)): print("15 010"); 
            elif (self._IR == (0x15<<3|3)): print("15 011"); 
            elif (self._IR == (0x15<<3|4)): print("15 100"); 
            elif (self._IR == (0x15<<3|5)): print("15 101"); 
            elif (self._IR == (0x15<<3|6)): print("15 110"); 
            elif (self._IR == (0x15<<3|7)): print("15 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ASL-zp,x                        
            elif (self._IR == (0x16<<3|0)): print("16 000"); 
            elif (self._IR == (0x16<<3|1)): print("16 001"); 
            elif (self._IR == (0x16<<3|2)): print("16 010"); 
            elif (self._IR == (0x16<<3|3)): print("16 011"); 
            elif (self._IR == (0x16<<3|4)): print("16 100"); 
            elif (self._IR == (0x16<<3|5)): print("16 101"); 
            elif (self._IR == (0x16<<3|6)): print("16 110"); 
            elif (self._IR == (0x16<<3|7)): print("16 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB1-zp                         
            elif (self._IR == (0x17<<3|0)): print("17 000"); 
            elif (self._IR == (0x17<<3|1)): print("17 001"); 
            elif (self._IR == (0x17<<3|2)): print("17 010"); 
            elif (self._IR == (0x17<<3|3)): print("17 011"); 
            elif (self._IR == (0x17<<3|4)): print("17 100"); 
            elif (self._IR == (0x17<<3|5)): print("17 101"); 
            elif (self._IR == (0x17<<3|6)): print("17 110"); 
            elif (self._IR == (0x17<<3|7)): print("17 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CLC-i                           
            elif (self._IR == (0x18<<3|0)): print("18 000"); 
            elif (self._IR == (0x18<<3|1)): print("18 001"); 
            elif (self._IR == (0x18<<3|2)): print("18 010"); 
            elif (self._IR == (0x18<<3|3)): print("18 011"); 
            elif (self._IR == (0x18<<3|4)): print("18 100"); 
            elif (self._IR == (0x18<<3|5)): print("18 101"); 
            elif (self._IR == (0x18<<3|6)): print("18 110"); 
            elif (self._IR == (0x18<<3|7)): print("18 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ORA-a,y                         
            elif (self._IR == (0x19<<3|0)): print("19 000"); 
            elif (self._IR == (0x19<<3|1)): print("19 001"); 
            elif (self._IR == (0x19<<3|2)): print("19 010"); 
            elif (self._IR == (0x19<<3|3)): print("19 011"); 
            elif (self._IR == (0x19<<3|4)): print("19 100"); 
            elif (self._IR == (0x19<<3|5)): print("19 101"); 
            elif (self._IR == (0x19<<3|6)): print("19 110"); 
            elif (self._IR == (0x19<<3|7)): print("19 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INC-A                           
            elif (self._IR == (0x1a<<3|0)): print("1a 000"); 
            elif (self._IR == (0x1a<<3|1)): print("1a 001"); 
            elif (self._IR == (0x1a<<3|2)): print("1a 010"); 
            elif (self._IR == (0x1a<<3|3)): print("1a 011"); 
            elif (self._IR == (0x1a<<3|4)): print("1a 100"); 
            elif (self._IR == (0x1a<<3|5)): print("1a 101"); 
            elif (self._IR == (0x1a<<3|6)): print("1a 110"); 
            elif (self._IR == (0x1a<<3|7)): print("1a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x1b<<3|0)): print("1b 000"); 
            elif (self._IR == (0x1b<<3|1)): print("1b 001"); 
            elif (self._IR == (0x1b<<3|2)): print("1b 010"); 
            elif (self._IR == (0x1b<<3|3)): print("1b 011"); 
            elif (self._IR == (0x1b<<3|4)): print("1b 100"); 
            elif (self._IR == (0x1b<<3|5)): print("1b 101"); 
            elif (self._IR == (0x1b<<3|6)): print("1b 110"); 
            elif (self._IR == (0x1b<<3|7)): print("1b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TRB-a                           
            elif (self._IR == (0x1c<<3|0)): print("1c 000"); 
            elif (self._IR == (0x1c<<3|1)): print("1c 001"); 
            elif (self._IR == (0x1c<<3|2)): print("1c 010"); 
            elif (self._IR == (0x1c<<3|3)): print("1c 011"); 
            elif (self._IR == (0x1c<<3|4)): print("1c 100"); 
            elif (self._IR == (0x1c<<3|5)): print("1c 101"); 
            elif (self._IR == (0x1c<<3|6)): print("1c 110"); 
            elif (self._IR == (0x1c<<3|7)): print("1c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ORA-a,x                         
            elif (self._IR == (0x1d<<3|0)): print("1d 000"); 
            elif (self._IR == (0x1d<<3|1)): print("1d 001"); 
            elif (self._IR == (0x1d<<3|2)): print("1d 010"); 
            elif (self._IR == (0x1d<<3|3)): print("1d 011"); 
            elif (self._IR == (0x1d<<3|4)): print("1d 100"); 
            elif (self._IR == (0x1d<<3|5)): print("1d 101"); 
            elif (self._IR == (0x1d<<3|6)): print("1d 110"); 
            elif (self._IR == (0x1d<<3|7)): print("1d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ASL-a,x                         
            elif (self._IR == (0x1e<<3|0)): print("1e 000"); 
            elif (self._IR == (0x1e<<3|1)): print("1e 001"); 
            elif (self._IR == (0x1e<<3|2)): print("1e 010"); 
            elif (self._IR == (0x1e<<3|3)): print("1e 011"); 
            elif (self._IR == (0x1e<<3|4)): print("1e 100"); 
            elif (self._IR == (0x1e<<3|5)): print("1e 101"); 
            elif (self._IR == (0x1e<<3|6)): print("1e 110"); 
            elif (self._IR == (0x1e<<3|7)): print("1e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR1-r                          
            elif (self._IR == (0x1f<<3|0)): print("1f 000"); 
            elif (self._IR == (0x1f<<3|1)): print("1f 001"); 
            elif (self._IR == (0x1f<<3|2)): print("1f 010"); 
            elif (self._IR == (0x1f<<3|3)): print("1f 011"); 
            elif (self._IR == (0x1f<<3|4)): print("1f 100"); 
            elif (self._IR == (0x1f<<3|5)): print("1f 101"); 
            elif (self._IR == (0x1f<<3|6)): print("1f 110"); 
            elif (self._IR == (0x1f<<3|7)): print("1f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # JSR-a                           
            elif (self._IR == (0x20<<3|0)): print("20 000"); 
            elif (self._IR == (0x20<<3|1)): print("20 001"); 
            elif (self._IR == (0x20<<3|2)): print("20 010"); 
            elif (self._IR == (0x20<<3|3)): print("20 011"); 
            elif (self._IR == (0x20<<3|4)): print("20 100"); 
            elif (self._IR == (0x20<<3|5)): print("20 101"); 
            elif (self._IR == (0x20<<3|6)): print("20 110"); 
            elif (self._IR == (0x20<<3|7)): print("20 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-(zp,x)                      
            elif (self._IR == (0x21<<3|0)): print("21 000"); 
            elif (self._IR == (0x21<<3|1)): print("21 001"); 
            elif (self._IR == (0x21<<3|2)): print("21 010"); 
            elif (self._IR == (0x21<<3|3)): print("21 011"); 
            elif (self._IR == (0x21<<3|4)): print("21 100"); 
            elif (self._IR == (0x21<<3|5)): print("21 101"); 
            elif (self._IR == (0x21<<3|6)): print("21 110"); 
            elif (self._IR == (0x21<<3|7)): print("21 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x22<<3|0)): print("22 000"); 
            elif (self._IR == (0x22<<3|1)): print("22 001"); 
            elif (self._IR == (0x22<<3|2)): print("22 010"); 
            elif (self._IR == (0x22<<3|3)): print("22 011"); 
            elif (self._IR == (0x22<<3|4)): print("22 100"); 
            elif (self._IR == (0x22<<3|5)): print("22 101"); 
            elif (self._IR == (0x22<<3|6)): print("22 110"); 
            elif (self._IR == (0x22<<3|7)): print("22 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x23<<3|0)): print("23 000"); 
            elif (self._IR == (0x23<<3|1)): print("23 001"); 
            elif (self._IR == (0x23<<3|2)): print("23 010"); 
            elif (self._IR == (0x23<<3|3)): print("23 011"); 
            elif (self._IR == (0x23<<3|4)): print("23 100"); 
            elif (self._IR == (0x23<<3|5)): print("23 101"); 
            elif (self._IR == (0x23<<3|6)): print("23 110"); 
            elif (self._IR == (0x23<<3|7)): print("23 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BIT-zp                          
            elif (self._IR == (0x24<<3|0)): print("24 000"); 
            elif (self._IR == (0x24<<3|1)): print("24 001"); 
            elif (self._IR == (0x24<<3|2)): print("24 010"); 
            elif (self._IR == (0x24<<3|3)): print("24 011"); 
            elif (self._IR == (0x24<<3|4)): print("24 100"); 
            elif (self._IR == (0x24<<3|5)): print("24 101"); 
            elif (self._IR == (0x24<<3|6)): print("24 110"); 
            elif (self._IR == (0x24<<3|7)): print("24 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-zp                          
            elif (self._IR == (0x25<<3|0)): print("25 000"); 
            elif (self._IR == (0x25<<3|1)): print("25 001"); 
            elif (self._IR == (0x25<<3|2)): print("25 010"); 
            elif (self._IR == (0x25<<3|3)): print("25 011"); 
            elif (self._IR == (0x25<<3|4)): print("25 100"); 
            elif (self._IR == (0x25<<3|5)): print("25 101"); 
            elif (self._IR == (0x25<<3|6)): print("25 110"); 
            elif (self._IR == (0x25<<3|7)): print("25 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROL-zp                          
            elif (self._IR == (0x26<<3|0)): print("26 000"); 
            elif (self._IR == (0x26<<3|1)): print("26 001"); 
            elif (self._IR == (0x26<<3|2)): print("26 010"); 
            elif (self._IR == (0x26<<3|3)): print("26 011"); 
            elif (self._IR == (0x26<<3|4)): print("26 100"); 
            elif (self._IR == (0x26<<3|5)): print("26 101"); 
            elif (self._IR == (0x26<<3|6)): print("26 110"); 
            elif (self._IR == (0x26<<3|7)): print("26 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB2-zp                         
            elif (self._IR == (0x27<<3|0)): print("27 000"); 
            elif (self._IR == (0x27<<3|1)): print("27 001"); 
            elif (self._IR == (0x27<<3|2)): print("27 010"); 
            elif (self._IR == (0x27<<3|3)): print("27 011"); 
            elif (self._IR == (0x27<<3|4)): print("27 100"); 
            elif (self._IR == (0x27<<3|5)): print("27 101"); 
            elif (self._IR == (0x27<<3|6)): print("27 110"); 
            elif (self._IR == (0x27<<3|7)): print("27 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PLP-s                           
            elif (self._IR == (0x28<<3|0)): print("28 000"); 
            elif (self._IR == (0x28<<3|1)): print("28 001"); 
            elif (self._IR == (0x28<<3|2)): print("28 010"); 
            elif (self._IR == (0x28<<3|3)): print("28 011"); 
            elif (self._IR == (0x28<<3|4)): print("28 100"); 
            elif (self._IR == (0x28<<3|5)): print("28 101"); 
            elif (self._IR == (0x28<<3|6)): print("28 110"); 
            elif (self._IR == (0x28<<3|7)): print("28 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-#                           
            elif (self._IR == (0x29<<3|0)): print("29 000"); 
            elif (self._IR == (0x29<<3|1)): print("29 001"); 
            elif (self._IR == (0x29<<3|2)): print("29 010"); 
            elif (self._IR == (0x29<<3|3)): print("29 011"); 
            elif (self._IR == (0x29<<3|4)): print("29 100"); 
            elif (self._IR == (0x29<<3|5)): print("29 101"); 
            elif (self._IR == (0x29<<3|6)): print("29 110"); 
            elif (self._IR == (0x29<<3|7)): print("29 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROL-A                           
            elif (self._IR == (0x2a<<3|0)): print("2a 000"); 
            elif (self._IR == (0x2a<<3|1)): print("2a 001"); 
            elif (self._IR == (0x2a<<3|2)): print("2a 010"); 
            elif (self._IR == (0x2a<<3|3)): print("2a 011"); 
            elif (self._IR == (0x2a<<3|4)): print("2a 100"); 
            elif (self._IR == (0x2a<<3|5)): print("2a 101"); 
            elif (self._IR == (0x2a<<3|6)): print("2a 110"); 
            elif (self._IR == (0x2a<<3|7)): print("2a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x2b<<3|0)): print("2b 000"); 
            elif (self._IR == (0x2b<<3|1)): print("2b 001"); 
            elif (self._IR == (0x2b<<3|2)): print("2b 010"); 
            elif (self._IR == (0x2b<<3|3)): print("2b 011"); 
            elif (self._IR == (0x2b<<3|4)): print("2b 100"); 
            elif (self._IR == (0x2b<<3|5)): print("2b 101"); 
            elif (self._IR == (0x2b<<3|6)): print("2b 110"); 
            elif (self._IR == (0x2b<<3|7)): print("2b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BIT-a                           
            elif (self._IR == (0x2c<<3|0)): print("2c 000"); 
            elif (self._IR == (0x2c<<3|1)): print("2c 001"); 
            elif (self._IR == (0x2c<<3|2)): print("2c 010"); 
            elif (self._IR == (0x2c<<3|3)): print("2c 011"); 
            elif (self._IR == (0x2c<<3|4)): print("2c 100"); 
            elif (self._IR == (0x2c<<3|5)): print("2c 101"); 
            elif (self._IR == (0x2c<<3|6)): print("2c 110"); 
            elif (self._IR == (0x2c<<3|7)): print("2c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-a                           
            elif (self._IR == (0x2d<<3|0)): print("2d 000"); 
            elif (self._IR == (0x2d<<3|1)): print("2d 001"); 
            elif (self._IR == (0x2d<<3|2)): print("2d 010"); 
            elif (self._IR == (0x2d<<3|3)): print("2d 011"); 
            elif (self._IR == (0x2d<<3|4)): print("2d 100"); 
            elif (self._IR == (0x2d<<3|5)): print("2d 101"); 
            elif (self._IR == (0x2d<<3|6)): print("2d 110"); 
            elif (self._IR == (0x2d<<3|7)): print("2d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROL-a                           
            elif (self._IR == (0x2e<<3|0)): print("2e 000"); 
            elif (self._IR == (0x2e<<3|1)): print("2e 001"); 
            elif (self._IR == (0x2e<<3|2)): print("2e 010"); 
            elif (self._IR == (0x2e<<3|3)): print("2e 011"); 
            elif (self._IR == (0x2e<<3|4)): print("2e 100"); 
            elif (self._IR == (0x2e<<3|5)): print("2e 101"); 
            elif (self._IR == (0x2e<<3|6)): print("2e 110"); 
            elif (self._IR == (0x2e<<3|7)): print("2e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR2-r                          
            elif (self._IR == (0x2f<<3|0)): print("2f 000"); 
            elif (self._IR == (0x2f<<3|1)): print("2f 001"); 
            elif (self._IR == (0x2f<<3|2)): print("2f 010"); 
            elif (self._IR == (0x2f<<3|3)): print("2f 011"); 
            elif (self._IR == (0x2f<<3|4)): print("2f 100"); 
            elif (self._IR == (0x2f<<3|5)): print("2f 101"); 
            elif (self._IR == (0x2f<<3|6)): print("2f 110"); 
            elif (self._IR == (0x2f<<3|7)): print("2f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BMI-r                           
            elif (self._IR == (0x30<<3|0)): print("30 000"); 
            elif (self._IR == (0x30<<3|1)): print("30 001"); 
            elif (self._IR == (0x30<<3|2)): print("30 010"); 
            elif (self._IR == (0x30<<3|3)): print("30 011"); 
            elif (self._IR == (0x30<<3|4)): print("30 100"); 
            elif (self._IR == (0x30<<3|5)): print("30 101"); 
            elif (self._IR == (0x30<<3|6)): print("30 110"); 
            elif (self._IR == (0x30<<3|7)): print("30 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-(zp),y                      
            elif (self._IR == (0x31<<3|0)): print("31 000"); 
            elif (self._IR == (0x31<<3|1)): print("31 001"); 
            elif (self._IR == (0x31<<3|2)): print("31 010"); 
            elif (self._IR == (0x31<<3|3)): print("31 011"); 
            elif (self._IR == (0x31<<3|4)): print("31 100"); 
            elif (self._IR == (0x31<<3|5)): print("31 101"); 
            elif (self._IR == (0x31<<3|6)): print("31 110"); 
            elif (self._IR == (0x31<<3|7)): print("31 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-(zp)                        
            elif (self._IR == (0x32<<3|0)): print("32 000"); 
            elif (self._IR == (0x32<<3|1)): print("32 001"); 
            elif (self._IR == (0x32<<3|2)): print("32 010"); 
            elif (self._IR == (0x32<<3|3)): print("32 011"); 
            elif (self._IR == (0x32<<3|4)): print("32 100"); 
            elif (self._IR == (0x32<<3|5)): print("32 101"); 
            elif (self._IR == (0x32<<3|6)): print("32 110"); 
            elif (self._IR == (0x32<<3|7)): print("32 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x33<<3|0)): print("33 000"); 
            elif (self._IR == (0x33<<3|1)): print("33 001"); 
            elif (self._IR == (0x33<<3|2)): print("33 010"); 
            elif (self._IR == (0x33<<3|3)): print("33 011"); 
            elif (self._IR == (0x33<<3|4)): print("33 100"); 
            elif (self._IR == (0x33<<3|5)): print("33 101"); 
            elif (self._IR == (0x33<<3|6)): print("33 110"); 
            elif (self._IR == (0x33<<3|7)): print("33 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BIT-zp,x                        
            elif (self._IR == (0x34<<3|0)): print("34 000"); 
            elif (self._IR == (0x34<<3|1)): print("34 001"); 
            elif (self._IR == (0x34<<3|2)): print("34 010"); 
            elif (self._IR == (0x34<<3|3)): print("34 011"); 
            elif (self._IR == (0x34<<3|4)): print("34 100"); 
            elif (self._IR == (0x34<<3|5)): print("34 101"); 
            elif (self._IR == (0x34<<3|6)): print("34 110"); 
            elif (self._IR == (0x34<<3|7)): print("34 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-zp,x                        
            elif (self._IR == (0x35<<3|0)): print("35 000"); 
            elif (self._IR == (0x35<<3|1)): print("35 001"); 
            elif (self._IR == (0x35<<3|2)): print("35 010"); 
            elif (self._IR == (0x35<<3|3)): print("35 011"); 
            elif (self._IR == (0x35<<3|4)): print("35 100"); 
            elif (self._IR == (0x35<<3|5)): print("35 101"); 
            elif (self._IR == (0x35<<3|6)): print("35 110"); 
            elif (self._IR == (0x35<<3|7)): print("35 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROL-zp,x                        
            elif (self._IR == (0x36<<3|0)): print("36 000"); 
            elif (self._IR == (0x36<<3|1)): print("36 001"); 
            elif (self._IR == (0x36<<3|2)): print("36 010"); 
            elif (self._IR == (0x36<<3|3)): print("36 011"); 
            elif (self._IR == (0x36<<3|4)): print("36 100"); 
            elif (self._IR == (0x36<<3|5)): print("36 101"); 
            elif (self._IR == (0x36<<3|6)): print("36 110"); 
            elif (self._IR == (0x36<<3|7)): print("36 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB3-zp                         
            elif (self._IR == (0x37<<3|0)): print("37 000"); 
            elif (self._IR == (0x37<<3|1)): print("37 001"); 
            elif (self._IR == (0x37<<3|2)): print("37 010"); 
            elif (self._IR == (0x37<<3|3)): print("37 011"); 
            elif (self._IR == (0x37<<3|4)): print("37 100"); 
            elif (self._IR == (0x37<<3|5)): print("37 101"); 
            elif (self._IR == (0x37<<3|6)): print("37 110"); 
            elif (self._IR == (0x37<<3|7)): print("37 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SEC-I                           
            elif (self._IR == (0x38<<3|0)): print("38 000"); 
            elif (self._IR == (0x38<<3|1)): print("38 001"); 
            elif (self._IR == (0x38<<3|2)): print("38 010"); 
            elif (self._IR == (0x38<<3|3)): print("38 011"); 
            elif (self._IR == (0x38<<3|4)): print("38 100"); 
            elif (self._IR == (0x38<<3|5)): print("38 101"); 
            elif (self._IR == (0x38<<3|6)): print("38 110"); 
            elif (self._IR == (0x38<<3|7)): print("38 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-a,y                         
            elif (self._IR == (0x39<<3|0)): print("39 000"); 
            elif (self._IR == (0x39<<3|1)): print("39 001"); 
            elif (self._IR == (0x39<<3|2)): print("39 010"); 
            elif (self._IR == (0x39<<3|3)): print("39 011"); 
            elif (self._IR == (0x39<<3|4)): print("39 100"); 
            elif (self._IR == (0x39<<3|5)): print("39 101"); 
            elif (self._IR == (0x39<<3|6)): print("39 110"); 
            elif (self._IR == (0x39<<3|7)): print("39 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEC-A                           
            elif (self._IR == (0x3a<<3|0)): print("3a 000"); 
            elif (self._IR == (0x3a<<3|1)): print("3a 001"); 
            elif (self._IR == (0x3a<<3|2)): print("3a 010"); 
            elif (self._IR == (0x3a<<3|3)): print("3a 011"); 
            elif (self._IR == (0x3a<<3|4)): print("3a 100"); 
            elif (self._IR == (0x3a<<3|5)): print("3a 101"); 
            elif (self._IR == (0x3a<<3|6)): print("3a 110"); 
            elif (self._IR == (0x3a<<3|7)): print("3a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x3b<<3|0)): print("3b 000"); 
            elif (self._IR == (0x3b<<3|1)): print("3b 001"); 
            elif (self._IR == (0x3b<<3|2)): print("3b 010"); 
            elif (self._IR == (0x3b<<3|3)): print("3b 011"); 
            elif (self._IR == (0x3b<<3|4)): print("3b 100"); 
            elif (self._IR == (0x3b<<3|5)): print("3b 101"); 
            elif (self._IR == (0x3b<<3|6)): print("3b 110"); 
            elif (self._IR == (0x3b<<3|7)): print("3b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BIT-a,x                         
            elif (self._IR == (0x3c<<3|0)): print("3c 000"); 
            elif (self._IR == (0x3c<<3|1)): print("3c 001"); 
            elif (self._IR == (0x3c<<3|2)): print("3c 010"); 
            elif (self._IR == (0x3c<<3|3)): print("3c 011"); 
            elif (self._IR == (0x3c<<3|4)): print("3c 100"); 
            elif (self._IR == (0x3c<<3|5)): print("3c 101"); 
            elif (self._IR == (0x3c<<3|6)): print("3c 110"); 
            elif (self._IR == (0x3c<<3|7)): print("3c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # AND-a,x                         
            elif (self._IR == (0x3d<<3|0)): print("3d 000"); 
            elif (self._IR == (0x3d<<3|1)): print("3d 001"); 
            elif (self._IR == (0x3d<<3|2)): print("3d 010"); 
            elif (self._IR == (0x3d<<3|3)): print("3d 011"); 
            elif (self._IR == (0x3d<<3|4)): print("3d 100"); 
            elif (self._IR == (0x3d<<3|5)): print("3d 101"); 
            elif (self._IR == (0x3d<<3|6)): print("3d 110"); 
            elif (self._IR == (0x3d<<3|7)): print("3d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROL-a,x                         
            elif (self._IR == (0x3e<<3|0)): print("3e 000"); 
            elif (self._IR == (0x3e<<3|1)): print("3e 001"); 
            elif (self._IR == (0x3e<<3|2)): print("3e 010"); 
            elif (self._IR == (0x3e<<3|3)): print("3e 011"); 
            elif (self._IR == (0x3e<<3|4)): print("3e 100"); 
            elif (self._IR == (0x3e<<3|5)): print("3e 101"); 
            elif (self._IR == (0x3e<<3|6)): print("3e 110"); 
            elif (self._IR == (0x3e<<3|7)): print("3e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR3-r                          
            elif (self._IR == (0x3f<<3|0)): print("3f 000"); 
            elif (self._IR == (0x3f<<3|1)): print("3f 001"); 
            elif (self._IR == (0x3f<<3|2)): print("3f 010"); 
            elif (self._IR == (0x3f<<3|3)): print("3f 011"); 
            elif (self._IR == (0x3f<<3|4)): print("3f 100"); 
            elif (self._IR == (0x3f<<3|5)): print("3f 101"); 
            elif (self._IR == (0x3f<<3|6)): print("3f 110"); 
            elif (self._IR == (0x3f<<3|7)): print("3f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # RTI-s                           
            elif (self._IR == (0x40<<3|0)): print("40 000"); 
            elif (self._IR == (0x40<<3|1)): print("40 001"); 
            elif (self._IR == (0x40<<3|2)): print("40 010"); 
            elif (self._IR == (0x40<<3|3)): print("40 011"); 
            elif (self._IR == (0x40<<3|4)): print("40 100"); 
            elif (self._IR == (0x40<<3|5)): print("40 101"); 
            elif (self._IR == (0x40<<3|6)): print("40 110"); 
            elif (self._IR == (0x40<<3|7)): print("40 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-(zp,x)                      
            elif (self._IR == (0x41<<3|0)): print("41 000"); 
            elif (self._IR == (0x41<<3|1)): print("41 001"); 
            elif (self._IR == (0x41<<3|2)): print("41 010"); 
            elif (self._IR == (0x41<<3|3)): print("41 011"); 
            elif (self._IR == (0x41<<3|4)): print("41 100"); 
            elif (self._IR == (0x41<<3|5)): print("41 101"); 
            elif (self._IR == (0x41<<3|6)): print("41 110"); 
            elif (self._IR == (0x41<<3|7)): print("41 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x42<<3|0)): print("42 000"); 
            elif (self._IR == (0x42<<3|1)): print("42 001"); 
            elif (self._IR == (0x42<<3|2)): print("42 010"); 
            elif (self._IR == (0x42<<3|3)): print("42 011"); 
            elif (self._IR == (0x42<<3|4)): print("42 100"); 
            elif (self._IR == (0x42<<3|5)): print("42 101"); 
            elif (self._IR == (0x42<<3|6)): print("42 110"); 
            elif (self._IR == (0x42<<3|7)): print("42 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x43<<3|0)): print("43 000"); 
            elif (self._IR == (0x43<<3|1)): print("43 001"); 
            elif (self._IR == (0x43<<3|2)): print("43 010"); 
            elif (self._IR == (0x43<<3|3)): print("43 011"); 
            elif (self._IR == (0x43<<3|4)): print("43 100"); 
            elif (self._IR == (0x43<<3|5)): print("43 101"); 
            elif (self._IR == (0x43<<3|6)): print("43 110"); 
            elif (self._IR == (0x43<<3|7)): print("43 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x44<<3|0)): print("44 000"); 
            elif (self._IR == (0x44<<3|1)): print("44 001"); 
            elif (self._IR == (0x44<<3|2)): print("44 010"); 
            elif (self._IR == (0x44<<3|3)): print("44 011"); 
            elif (self._IR == (0x44<<3|4)): print("44 100"); 
            elif (self._IR == (0x44<<3|5)): print("44 101"); 
            elif (self._IR == (0x44<<3|6)): print("44 110"); 
            elif (self._IR == (0x44<<3|7)): print("44 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-zp                          
            elif (self._IR == (0x45<<3|0)): print("45 000"); 
            elif (self._IR == (0x45<<3|1)): print("45 001"); 
            elif (self._IR == (0x45<<3|2)): print("45 010"); 
            elif (self._IR == (0x45<<3|3)): print("45 011"); 
            elif (self._IR == (0x45<<3|4)): print("45 100"); 
            elif (self._IR == (0x45<<3|5)): print("45 101"); 
            elif (self._IR == (0x45<<3|6)): print("45 110"); 
            elif (self._IR == (0x45<<3|7)): print("45 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LSR-zp                          
            elif (self._IR == (0x46<<3|0)): print("46 000"); 
            elif (self._IR == (0x46<<3|1)): print("46 001"); 
            elif (self._IR == (0x46<<3|2)): print("46 010"); 
            elif (self._IR == (0x46<<3|3)): print("46 011"); 
            elif (self._IR == (0x46<<3|4)): print("46 100"); 
            elif (self._IR == (0x46<<3|5)): print("46 101"); 
            elif (self._IR == (0x46<<3|6)): print("46 110"); 
            elif (self._IR == (0x46<<3|7)): print("46 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB4-zp                         
            elif (self._IR == (0x47<<3|0)): print("47 000"); 
            elif (self._IR == (0x47<<3|1)): print("47 001"); 
            elif (self._IR == (0x47<<3|2)): print("47 010"); 
            elif (self._IR == (0x47<<3|3)): print("47 011"); 
            elif (self._IR == (0x47<<3|4)): print("47 100"); 
            elif (self._IR == (0x47<<3|5)): print("47 101"); 
            elif (self._IR == (0x47<<3|6)): print("47 110"); 
            elif (self._IR == (0x47<<3|7)): print("47 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PHA-s                           
            elif (self._IR == (0x48<<3|0)): print("48 000"); 
            elif (self._IR == (0x48<<3|1)): print("48 001"); 
            elif (self._IR == (0x48<<3|2)): print("48 010"); 
            elif (self._IR == (0x48<<3|3)): print("48 011"); 
            elif (self._IR == (0x48<<3|4)): print("48 100"); 
            elif (self._IR == (0x48<<3|5)): print("48 101"); 
            elif (self._IR == (0x48<<3|6)): print("48 110"); 
            elif (self._IR == (0x48<<3|7)): print("48 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-#                           
            elif (self._IR == (0x49<<3|0)): print("49 000"); 
            elif (self._IR == (0x49<<3|1)): print("49 001"); 
            elif (self._IR == (0x49<<3|2)): print("49 010"); 
            elif (self._IR == (0x49<<3|3)): print("49 011"); 
            elif (self._IR == (0x49<<3|4)): print("49 100"); 
            elif (self._IR == (0x49<<3|5)): print("49 101"); 
            elif (self._IR == (0x49<<3|6)): print("49 110"); 
            elif (self._IR == (0x49<<3|7)): print("49 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LSR-A                           
            elif (self._IR == (0x4a<<3|0)): print("4a 000"); 
            elif (self._IR == (0x4a<<3|1)): print("4a 001"); 
            elif (self._IR == (0x4a<<3|2)): print("4a 010"); 
            elif (self._IR == (0x4a<<3|3)): print("4a 011"); 
            elif (self._IR == (0x4a<<3|4)): print("4a 100"); 
            elif (self._IR == (0x4a<<3|5)): print("4a 101"); 
            elif (self._IR == (0x4a<<3|6)): print("4a 110"); 
            elif (self._IR == (0x4a<<3|7)): print("4a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x4b<<3|0)): print("4b 000"); 
            elif (self._IR == (0x4b<<3|1)): print("4b 001"); 
            elif (self._IR == (0x4b<<3|2)): print("4b 010"); 
            elif (self._IR == (0x4b<<3|3)): print("4b 011"); 
            elif (self._IR == (0x4b<<3|4)): print("4b 100"); 
            elif (self._IR == (0x4b<<3|5)): print("4b 101"); 
            elif (self._IR == (0x4b<<3|6)): print("4b 110"); 
            elif (self._IR == (0x4b<<3|7)): print("4b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # JMP-a                           
            elif (self._IR == (0x4c<<3|0)): print("4c 000"); 
            elif (self._IR == (0x4c<<3|1)): print("4c 001"); 
            elif (self._IR == (0x4c<<3|2)): print("4c 010"); 
            elif (self._IR == (0x4c<<3|3)): print("4c 011"); 
            elif (self._IR == (0x4c<<3|4)): print("4c 100"); 
            elif (self._IR == (0x4c<<3|5)): print("4c 101"); 
            elif (self._IR == (0x4c<<3|6)): print("4c 110"); 
            elif (self._IR == (0x4c<<3|7)): print("4c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-a                           
            elif (self._IR == (0x4d<<3|0)): print("4d 000"); 
            elif (self._IR == (0x4d<<3|1)): print("4d 001"); 
            elif (self._IR == (0x4d<<3|2)): print("4d 010"); 
            elif (self._IR == (0x4d<<3|3)): print("4d 011"); 
            elif (self._IR == (0x4d<<3|4)): print("4d 100"); 
            elif (self._IR == (0x4d<<3|5)): print("4d 101"); 
            elif (self._IR == (0x4d<<3|6)): print("4d 110"); 
            elif (self._IR == (0x4d<<3|7)): print("4d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LSR-a                           
            elif (self._IR == (0x4e<<3|0)): print("4e 000"); 
            elif (self._IR == (0x4e<<3|1)): print("4e 001"); 
            elif (self._IR == (0x4e<<3|2)): print("4e 010"); 
            elif (self._IR == (0x4e<<3|3)): print("4e 011"); 
            elif (self._IR == (0x4e<<3|4)): print("4e 100"); 
            elif (self._IR == (0x4e<<3|5)): print("4e 101"); 
            elif (self._IR == (0x4e<<3|6)): print("4e 110"); 
            elif (self._IR == (0x4e<<3|7)): print("4e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR4-r                          
            elif (self._IR == (0x4f<<3|0)): print("4f 000"); 
            elif (self._IR == (0x4f<<3|1)): print("4f 001"); 
            elif (self._IR == (0x4f<<3|2)): print("4f 010"); 
            elif (self._IR == (0x4f<<3|3)): print("4f 011"); 
            elif (self._IR == (0x4f<<3|4)): print("4f 100"); 
            elif (self._IR == (0x4f<<3|5)): print("4f 101"); 
            elif (self._IR == (0x4f<<3|6)): print("4f 110"); 
            elif (self._IR == (0x4f<<3|7)): print("4f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BVC-r                           
            elif (self._IR == (0x50<<3|0)): print("50 000"); 
            elif (self._IR == (0x50<<3|1)): print("50 001"); 
            elif (self._IR == (0x50<<3|2)): print("50 010"); 
            elif (self._IR == (0x50<<3|3)): print("50 011"); 
            elif (self._IR == (0x50<<3|4)): print("50 100"); 
            elif (self._IR == (0x50<<3|5)): print("50 101"); 
            elif (self._IR == (0x50<<3|6)): print("50 110"); 
            elif (self._IR == (0x50<<3|7)): print("50 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-(zp),y                      
            elif (self._IR == (0x51<<3|0)): print("51 000"); 
            elif (self._IR == (0x51<<3|1)): print("51 001"); 
            elif (self._IR == (0x51<<3|2)): print("51 010"); 
            elif (self._IR == (0x51<<3|3)): print("51 011"); 
            elif (self._IR == (0x51<<3|4)): print("51 100"); 
            elif (self._IR == (0x51<<3|5)): print("51 101"); 
            elif (self._IR == (0x51<<3|6)): print("51 110"); 
            elif (self._IR == (0x51<<3|7)): print("51 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-(zp)                        
            elif (self._IR == (0x52<<3|0)): print("52 000"); 
            elif (self._IR == (0x52<<3|1)): print("52 001"); 
            elif (self._IR == (0x52<<3|2)): print("52 010"); 
            elif (self._IR == (0x52<<3|3)): print("52 011"); 
            elif (self._IR == (0x52<<3|4)): print("52 100"); 
            elif (self._IR == (0x52<<3|5)): print("52 101"); 
            elif (self._IR == (0x52<<3|6)): print("52 110"); 
            elif (self._IR == (0x52<<3|7)): print("52 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x53<<3|0)): print("53 000"); 
            elif (self._IR == (0x53<<3|1)): print("53 001"); 
            elif (self._IR == (0x53<<3|2)): print("53 010"); 
            elif (self._IR == (0x53<<3|3)): print("53 011"); 
            elif (self._IR == (0x53<<3|4)): print("53 100"); 
            elif (self._IR == (0x53<<3|5)): print("53 101"); 
            elif (self._IR == (0x53<<3|6)): print("53 110"); 
            elif (self._IR == (0x53<<3|7)): print("53 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x54<<3|0)): print("54 000"); 
            elif (self._IR == (0x54<<3|1)): print("54 001"); 
            elif (self._IR == (0x54<<3|2)): print("54 010"); 
            elif (self._IR == (0x54<<3|3)): print("54 011"); 
            elif (self._IR == (0x54<<3|4)): print("54 100"); 
            elif (self._IR == (0x54<<3|5)): print("54 101"); 
            elif (self._IR == (0x54<<3|6)): print("54 110"); 
            elif (self._IR == (0x54<<3|7)): print("54 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-zp,x                        
            elif (self._IR == (0x55<<3|0)): print("55 000"); 
            elif (self._IR == (0x55<<3|1)): print("55 001"); 
            elif (self._IR == (0x55<<3|2)): print("55 010"); 
            elif (self._IR == (0x55<<3|3)): print("55 011"); 
            elif (self._IR == (0x55<<3|4)): print("55 100"); 
            elif (self._IR == (0x55<<3|5)): print("55 101"); 
            elif (self._IR == (0x55<<3|6)): print("55 110"); 
            elif (self._IR == (0x55<<3|7)): print("55 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LSR-zp,x                        
            elif (self._IR == (0x56<<3|0)): print("56 000"); 
            elif (self._IR == (0x56<<3|1)): print("56 001"); 
            elif (self._IR == (0x56<<3|2)): print("56 010"); 
            elif (self._IR == (0x56<<3|3)): print("56 011"); 
            elif (self._IR == (0x56<<3|4)): print("56 100"); 
            elif (self._IR == (0x56<<3|5)): print("56 101"); 
            elif (self._IR == (0x56<<3|6)): print("56 110"); 
            elif (self._IR == (0x56<<3|7)): print("56 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB5-zp                         
            elif (self._IR == (0x57<<3|0)): print("57 000"); 
            elif (self._IR == (0x57<<3|1)): print("57 001"); 
            elif (self._IR == (0x57<<3|2)): print("57 010"); 
            elif (self._IR == (0x57<<3|3)): print("57 011"); 
            elif (self._IR == (0x57<<3|4)): print("57 100"); 
            elif (self._IR == (0x57<<3|5)): print("57 101"); 
            elif (self._IR == (0x57<<3|6)): print("57 110"); 
            elif (self._IR == (0x57<<3|7)): print("57 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CLI-i                           
            elif (self._IR == (0x58<<3|0)): print("58 000"); 
            elif (self._IR == (0x58<<3|1)): print("58 001"); 
            elif (self._IR == (0x58<<3|2)): print("58 010"); 
            elif (self._IR == (0x58<<3|3)): print("58 011"); 
            elif (self._IR == (0x58<<3|4)): print("58 100"); 
            elif (self._IR == (0x58<<3|5)): print("58 101"); 
            elif (self._IR == (0x58<<3|6)): print("58 110"); 
            elif (self._IR == (0x58<<3|7)): print("58 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-a,y                         
            elif (self._IR == (0x59<<3|0)): print("59 000"); 
            elif (self._IR == (0x59<<3|1)): print("59 001"); 
            elif (self._IR == (0x59<<3|2)): print("59 010"); 
            elif (self._IR == (0x59<<3|3)): print("59 011"); 
            elif (self._IR == (0x59<<3|4)): print("59 100"); 
            elif (self._IR == (0x59<<3|5)): print("59 101"); 
            elif (self._IR == (0x59<<3|6)): print("59 110"); 
            elif (self._IR == (0x59<<3|7)): print("59 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PHY-s                           
            elif (self._IR == (0x5a<<3|0)): print("5a 000"); 
            elif (self._IR == (0x5a<<3|1)): print("5a 001"); 
            elif (self._IR == (0x5a<<3|2)): print("5a 010"); 
            elif (self._IR == (0x5a<<3|3)): print("5a 011"); 
            elif (self._IR == (0x5a<<3|4)): print("5a 100"); 
            elif (self._IR == (0x5a<<3|5)): print("5a 101"); 
            elif (self._IR == (0x5a<<3|6)): print("5a 110"); 
            elif (self._IR == (0x5a<<3|7)): print("5a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x5b<<3|0)): print("5b 000"); 
            elif (self._IR == (0x5b<<3|1)): print("5b 001"); 
            elif (self._IR == (0x5b<<3|2)): print("5b 010"); 
            elif (self._IR == (0x5b<<3|3)): print("5b 011"); 
            elif (self._IR == (0x5b<<3|4)): print("5b 100"); 
            elif (self._IR == (0x5b<<3|5)): print("5b 101"); 
            elif (self._IR == (0x5b<<3|6)): print("5b 110"); 
            elif (self._IR == (0x5b<<3|7)): print("5b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x5c<<3|0)): print("5c 000"); 
            elif (self._IR == (0x5c<<3|1)): print("5c 001"); 
            elif (self._IR == (0x5c<<3|2)): print("5c 010"); 
            elif (self._IR == (0x5c<<3|3)): print("5c 011"); 
            elif (self._IR == (0x5c<<3|4)): print("5c 100"); 
            elif (self._IR == (0x5c<<3|5)): print("5c 101"); 
            elif (self._IR == (0x5c<<3|6)): print("5c 110"); 
            elif (self._IR == (0x5c<<3|7)): print("5c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # EOR-a,x                         
            elif (self._IR == (0x5d<<3|0)): print("5d 000"); 
            elif (self._IR == (0x5d<<3|1)): print("5d 001"); 
            elif (self._IR == (0x5d<<3|2)): print("5d 010"); 
            elif (self._IR == (0x5d<<3|3)): print("5d 011"); 
            elif (self._IR == (0x5d<<3|4)): print("5d 100"); 
            elif (self._IR == (0x5d<<3|5)): print("5d 101"); 
            elif (self._IR == (0x5d<<3|6)): print("5d 110"); 
            elif (self._IR == (0x5d<<3|7)): print("5d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LSR-a,x                         
            elif (self._IR == (0x5e<<3|0)): print("5e 000"); 
            elif (self._IR == (0x5e<<3|1)): print("5e 001"); 
            elif (self._IR == (0x5e<<3|2)): print("5e 010"); 
            elif (self._IR == (0x5e<<3|3)): print("5e 011"); 
            elif (self._IR == (0x5e<<3|4)): print("5e 100"); 
            elif (self._IR == (0x5e<<3|5)): print("5e 101"); 
            elif (self._IR == (0x5e<<3|6)): print("5e 110"); 
            elif (self._IR == (0x5e<<3|7)): print("5e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR5-r                          
            elif (self._IR == (0x5f<<3|0)): print("5f 000"); 
            elif (self._IR == (0x5f<<3|1)): print("5f 001"); 
            elif (self._IR == (0x5f<<3|2)): print("5f 010"); 
            elif (self._IR == (0x5f<<3|3)): print("5f 011"); 
            elif (self._IR == (0x5f<<3|4)): print("5f 100"); 
            elif (self._IR == (0x5f<<3|5)): print("5f 101"); 
            elif (self._IR == (0x5f<<3|6)): print("5f 110"); 
            elif (self._IR == (0x5f<<3|7)): print("5f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # RTS-s                           
            elif (self._IR == (0x60<<3|0)): print("60 000"); 
            elif (self._IR == (0x60<<3|1)): print("60 001"); 
            elif (self._IR == (0x60<<3|2)): print("60 010"); 
            elif (self._IR == (0x60<<3|3)): print("60 011"); 
            elif (self._IR == (0x60<<3|4)): print("60 100"); 
            elif (self._IR == (0x60<<3|5)): print("60 101"); 
            elif (self._IR == (0x60<<3|6)): print("60 110"); 
            elif (self._IR == (0x60<<3|7)): print("60 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-(zp,x)                      
            elif (self._IR == (0x61<<3|0)): print("61 000"); 
            elif (self._IR == (0x61<<3|1)): print("61 001"); 
            elif (self._IR == (0x61<<3|2)): print("61 010"); 
            elif (self._IR == (0x61<<3|3)): print("61 011"); 
            elif (self._IR == (0x61<<3|4)): print("61 100"); 
            elif (self._IR == (0x61<<3|5)): print("61 101"); 
            elif (self._IR == (0x61<<3|6)): print("61 110"); 
            elif (self._IR == (0x61<<3|7)): print("61 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x62<<3|0)): print("62 000"); 
            elif (self._IR == (0x62<<3|1)): print("62 001"); 
            elif (self._IR == (0x62<<3|2)): print("62 010"); 
            elif (self._IR == (0x62<<3|3)): print("62 011"); 
            elif (self._IR == (0x62<<3|4)): print("62 100"); 
            elif (self._IR == (0x62<<3|5)): print("62 101"); 
            elif (self._IR == (0x62<<3|6)): print("62 110"); 
            elif (self._IR == (0x62<<3|7)): print("62 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x63<<3|0)): print("63 000"); 
            elif (self._IR == (0x63<<3|1)): print("63 001"); 
            elif (self._IR == (0x63<<3|2)): print("63 010"); 
            elif (self._IR == (0x63<<3|3)): print("63 011"); 
            elif (self._IR == (0x63<<3|4)): print("63 100"); 
            elif (self._IR == (0x63<<3|5)): print("63 101"); 
            elif (self._IR == (0x63<<3|6)): print("63 110"); 
            elif (self._IR == (0x63<<3|7)): print("63 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STZ-zp                          
            elif (self._IR == (0x64<<3|0)): print("64 000"); 
            elif (self._IR == (0x64<<3|1)): print("64 001"); 
            elif (self._IR == (0x64<<3|2)): print("64 010"); 
            elif (self._IR == (0x64<<3|3)): print("64 011"); 
            elif (self._IR == (0x64<<3|4)): print("64 100"); 
            elif (self._IR == (0x64<<3|5)): print("64 101"); 
            elif (self._IR == (0x64<<3|6)): print("64 110"); 
            elif (self._IR == (0x64<<3|7)): print("64 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-zp                          
            elif (self._IR == (0x65<<3|0)): print("65 000"); 
            elif (self._IR == (0x65<<3|1)): print("65 001"); 
            elif (self._IR == (0x65<<3|2)): print("65 010"); 
            elif (self._IR == (0x65<<3|3)): print("65 011"); 
            elif (self._IR == (0x65<<3|4)): print("65 100"); 
            elif (self._IR == (0x65<<3|5)): print("65 101"); 
            elif (self._IR == (0x65<<3|6)): print("65 110"); 
            elif (self._IR == (0x65<<3|7)): print("65 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROR-zp                          
            elif (self._IR == (0x66<<3|0)): print("66 000"); 
            elif (self._IR == (0x66<<3|1)): print("66 001"); 
            elif (self._IR == (0x66<<3|2)): print("66 010"); 
            elif (self._IR == (0x66<<3|3)): print("66 011"); 
            elif (self._IR == (0x66<<3|4)): print("66 100"); 
            elif (self._IR == (0x66<<3|5)): print("66 101"); 
            elif (self._IR == (0x66<<3|6)): print("66 110"); 
            elif (self._IR == (0x66<<3|7)): print("66 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB6-zp                         
            elif (self._IR == (0x67<<3|0)): print("67 000"); 
            elif (self._IR == (0x67<<3|1)): print("67 001"); 
            elif (self._IR == (0x67<<3|2)): print("67 010"); 
            elif (self._IR == (0x67<<3|3)): print("67 011"); 
            elif (self._IR == (0x67<<3|4)): print("67 100"); 
            elif (self._IR == (0x67<<3|5)): print("67 101"); 
            elif (self._IR == (0x67<<3|6)): print("67 110"); 
            elif (self._IR == (0x67<<3|7)): print("67 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PLA-s                           
            elif (self._IR == (0x68<<3|0)): print("68 000"); 
            elif (self._IR == (0x68<<3|1)): print("68 001"); 
            elif (self._IR == (0x68<<3|2)): print("68 010"); 
            elif (self._IR == (0x68<<3|3)): print("68 011"); 
            elif (self._IR == (0x68<<3|4)): print("68 100"); 
            elif (self._IR == (0x68<<3|5)): print("68 101"); 
            elif (self._IR == (0x68<<3|6)): print("68 110"); 
            elif (self._IR == (0x68<<3|7)): print("68 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-#                           
            elif (self._IR == (0x69<<3|0)): print("69 000"); 
            elif (self._IR == (0x69<<3|1)): print("69 001"); 
            elif (self._IR == (0x69<<3|2)): print("69 010"); 
            elif (self._IR == (0x69<<3|3)): print("69 011"); 
            elif (self._IR == (0x69<<3|4)): print("69 100"); 
            elif (self._IR == (0x69<<3|5)): print("69 101"); 
            elif (self._IR == (0x69<<3|6)): print("69 110"); 
            elif (self._IR == (0x69<<3|7)): print("69 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROR-A                           
            elif (self._IR == (0x6a<<3|0)): print("6a 000"); 
            elif (self._IR == (0x6a<<3|1)): print("6a 001"); 
            elif (self._IR == (0x6a<<3|2)): print("6a 010"); 
            elif (self._IR == (0x6a<<3|3)): print("6a 011"); 
            elif (self._IR == (0x6a<<3|4)): print("6a 100"); 
            elif (self._IR == (0x6a<<3|5)): print("6a 101"); 
            elif (self._IR == (0x6a<<3|6)): print("6a 110"); 
            elif (self._IR == (0x6a<<3|7)): print("6a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x6b<<3|0)): print("6b 000"); 
            elif (self._IR == (0x6b<<3|1)): print("6b 001"); 
            elif (self._IR == (0x6b<<3|2)): print("6b 010"); 
            elif (self._IR == (0x6b<<3|3)): print("6b 011"); 
            elif (self._IR == (0x6b<<3|4)): print("6b 100"); 
            elif (self._IR == (0x6b<<3|5)): print("6b 101"); 
            elif (self._IR == (0x6b<<3|6)): print("6b 110"); 
            elif (self._IR == (0x6b<<3|7)): print("6b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # JMP-(a)                         
            elif (self._IR == (0x6c<<3|0)): print("6c 000"); 
            elif (self._IR == (0x6c<<3|1)): print("6c 001"); 
            elif (self._IR == (0x6c<<3|2)): print("6c 010"); 
            elif (self._IR == (0x6c<<3|3)): print("6c 011"); 
            elif (self._IR == (0x6c<<3|4)): print("6c 100"); 
            elif (self._IR == (0x6c<<3|5)): print("6c 101"); 
            elif (self._IR == (0x6c<<3|6)): print("6c 110"); 
            elif (self._IR == (0x6c<<3|7)): print("6c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-a                           
            elif (self._IR == (0x6d<<3|0)): print("6d 000"); 
            elif (self._IR == (0x6d<<3|1)): print("6d 001"); 
            elif (self._IR == (0x6d<<3|2)): print("6d 010"); 
            elif (self._IR == (0x6d<<3|3)): print("6d 011"); 
            elif (self._IR == (0x6d<<3|4)): print("6d 100"); 
            elif (self._IR == (0x6d<<3|5)): print("6d 101"); 
            elif (self._IR == (0x6d<<3|6)): print("6d 110"); 
            elif (self._IR == (0x6d<<3|7)): print("6d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROR-a                           
            elif (self._IR == (0x6e<<3|0)): print("6e 000"); 
            elif (self._IR == (0x6e<<3|1)): print("6e 001"); 
            elif (self._IR == (0x6e<<3|2)): print("6e 010"); 
            elif (self._IR == (0x6e<<3|3)): print("6e 011"); 
            elif (self._IR == (0x6e<<3|4)): print("6e 100"); 
            elif (self._IR == (0x6e<<3|5)): print("6e 101"); 
            elif (self._IR == (0x6e<<3|6)): print("6e 110"); 
            elif (self._IR == (0x6e<<3|7)): print("6e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR6-r                          
            elif (self._IR == (0x6f<<3|0)): print("6f 000"); 
            elif (self._IR == (0x6f<<3|1)): print("6f 001"); 
            elif (self._IR == (0x6f<<3|2)): print("6f 010"); 
            elif (self._IR == (0x6f<<3|3)): print("6f 011"); 
            elif (self._IR == (0x6f<<3|4)): print("6f 100"); 
            elif (self._IR == (0x6f<<3|5)): print("6f 101"); 
            elif (self._IR == (0x6f<<3|6)): print("6f 110"); 
            elif (self._IR == (0x6f<<3|7)): print("6f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BVS-r                           
            elif (self._IR == (0x70<<3|0)): print("70 000"); 
            elif (self._IR == (0x70<<3|1)): print("70 001"); 
            elif (self._IR == (0x70<<3|2)): print("70 010"); 
            elif (self._IR == (0x70<<3|3)): print("70 011"); 
            elif (self._IR == (0x70<<3|4)): print("70 100"); 
            elif (self._IR == (0x70<<3|5)): print("70 101"); 
            elif (self._IR == (0x70<<3|6)): print("70 110"); 
            elif (self._IR == (0x70<<3|7)): print("70 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-(zp),y                      
            elif (self._IR == (0x71<<3|0)): print("71 000"); 
            elif (self._IR == (0x71<<3|1)): print("71 001"); 
            elif (self._IR == (0x71<<3|2)): print("71 010"); 
            elif (self._IR == (0x71<<3|3)): print("71 011"); 
            elif (self._IR == (0x71<<3|4)): print("71 100"); 
            elif (self._IR == (0x71<<3|5)): print("71 101"); 
            elif (self._IR == (0x71<<3|6)): print("71 110"); 
            elif (self._IR == (0x71<<3|7)): print("71 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-(zp)                        
            elif (self._IR == (0x72<<3|0)): print("72 000"); 
            elif (self._IR == (0x72<<3|1)): print("72 001"); 
            elif (self._IR == (0x72<<3|2)): print("72 010"); 
            elif (self._IR == (0x72<<3|3)): print("72 011"); 
            elif (self._IR == (0x72<<3|4)): print("72 100"); 
            elif (self._IR == (0x72<<3|5)): print("72 101"); 
            elif (self._IR == (0x72<<3|6)): print("72 110"); 
            elif (self._IR == (0x72<<3|7)): print("72 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x73<<3|0)): print("73 000"); 
            elif (self._IR == (0x73<<3|1)): print("73 001"); 
            elif (self._IR == (0x73<<3|2)): print("73 010"); 
            elif (self._IR == (0x73<<3|3)): print("73 011"); 
            elif (self._IR == (0x73<<3|4)): print("73 100"); 
            elif (self._IR == (0x73<<3|5)): print("73 101"); 
            elif (self._IR == (0x73<<3|6)): print("73 110"); 
            elif (self._IR == (0x73<<3|7)): print("73 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STZ-zp,x                        
            elif (self._IR == (0x74<<3|0)): print("74 000"); 
            elif (self._IR == (0x74<<3|1)): print("74 001"); 
            elif (self._IR == (0x74<<3|2)): print("74 010"); 
            elif (self._IR == (0x74<<3|3)): print("74 011"); 
            elif (self._IR == (0x74<<3|4)): print("74 100"); 
            elif (self._IR == (0x74<<3|5)): print("74 101"); 
            elif (self._IR == (0x74<<3|6)): print("74 110"); 
            elif (self._IR == (0x74<<3|7)): print("74 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-zp,x                        
            elif (self._IR == (0x75<<3|0)): print("75 000"); 
            elif (self._IR == (0x75<<3|1)): print("75 001"); 
            elif (self._IR == (0x75<<3|2)): print("75 010"); 
            elif (self._IR == (0x75<<3|3)): print("75 011"); 
            elif (self._IR == (0x75<<3|4)): print("75 100"); 
            elif (self._IR == (0x75<<3|5)): print("75 101"); 
            elif (self._IR == (0x75<<3|6)): print("75 110"); 
            elif (self._IR == (0x75<<3|7)): print("75 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROR-zp,x                        
            elif (self._IR == (0x76<<3|0)): print("76 000"); 
            elif (self._IR == (0x76<<3|1)): print("76 001"); 
            elif (self._IR == (0x76<<3|2)): print("76 010"); 
            elif (self._IR == (0x76<<3|3)): print("76 011"); 
            elif (self._IR == (0x76<<3|4)): print("76 100"); 
            elif (self._IR == (0x76<<3|5)): print("76 101"); 
            elif (self._IR == (0x76<<3|6)): print("76 110"); 
            elif (self._IR == (0x76<<3|7)): print("76 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # RMB7-zp                         
            elif (self._IR == (0x77<<3|0)): print("77 000"); 
            elif (self._IR == (0x77<<3|1)): print("77 001"); 
            elif (self._IR == (0x77<<3|2)): print("77 010"); 
            elif (self._IR == (0x77<<3|3)): print("77 011"); 
            elif (self._IR == (0x77<<3|4)): print("77 100"); 
            elif (self._IR == (0x77<<3|5)): print("77 101"); 
            elif (self._IR == (0x77<<3|6)): print("77 110"); 
            elif (self._IR == (0x77<<3|7)): print("77 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SEI-i                           
            elif (self._IR == (0x78<<3|0)): print("78 000"); 
            elif (self._IR == (0x78<<3|1)): print("78 001"); 
            elif (self._IR == (0x78<<3|2)): print("78 010"); 
            elif (self._IR == (0x78<<3|3)): print("78 011"); 
            elif (self._IR == (0x78<<3|4)): print("78 100"); 
            elif (self._IR == (0x78<<3|5)): print("78 101"); 
            elif (self._IR == (0x78<<3|6)): print("78 110"); 
            elif (self._IR == (0x78<<3|7)): print("78 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-a,y                         
            elif (self._IR == (0x79<<3|0)): print("79 000"); 
            elif (self._IR == (0x79<<3|1)): print("79 001"); 
            elif (self._IR == (0x79<<3|2)): print("79 010"); 
            elif (self._IR == (0x79<<3|3)): print("79 011"); 
            elif (self._IR == (0x79<<3|4)): print("79 100"); 
            elif (self._IR == (0x79<<3|5)): print("79 101"); 
            elif (self._IR == (0x79<<3|6)): print("79 110"); 
            elif (self._IR == (0x79<<3|7)): print("79 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PLY-s                           
            elif (self._IR == (0x7a<<3|0)): print("7a 000"); 
            elif (self._IR == (0x7a<<3|1)): print("7a 001"); 
            elif (self._IR == (0x7a<<3|2)): print("7a 010"); 
            elif (self._IR == (0x7a<<3|3)): print("7a 011"); 
            elif (self._IR == (0x7a<<3|4)): print("7a 100"); 
            elif (self._IR == (0x7a<<3|5)): print("7a 101"); 
            elif (self._IR == (0x7a<<3|6)): print("7a 110"); 
            elif (self._IR == (0x7a<<3|7)): print("7a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x7b<<3|0)): print("7b 000"); 
            elif (self._IR == (0x7b<<3|1)): print("7b 001"); 
            elif (self._IR == (0x7b<<3|2)): print("7b 010"); 
            elif (self._IR == (0x7b<<3|3)): print("7b 011"); 
            elif (self._IR == (0x7b<<3|4)): print("7b 100"); 
            elif (self._IR == (0x7b<<3|5)): print("7b 101"); 
            elif (self._IR == (0x7b<<3|6)): print("7b 110"); 
            elif (self._IR == (0x7b<<3|7)): print("7b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # JMP-(a,x)                       
            elif (self._IR == (0x7c<<3|0)): print("7c 000"); 
            elif (self._IR == (0x7c<<3|1)): print("7c 001"); 
            elif (self._IR == (0x7c<<3|2)): print("7c 010"); 
            elif (self._IR == (0x7c<<3|3)): print("7c 011"); 
            elif (self._IR == (0x7c<<3|4)): print("7c 100"); 
            elif (self._IR == (0x7c<<3|5)): print("7c 101"); 
            elif (self._IR == (0x7c<<3|6)): print("7c 110"); 
            elif (self._IR == (0x7c<<3|7)): print("7c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ADC-a,x                         
            elif (self._IR == (0x7d<<3|0)): print("7d 000"); 
            elif (self._IR == (0x7d<<3|1)): print("7d 001"); 
            elif (self._IR == (0x7d<<3|2)): print("7d 010"); 
            elif (self._IR == (0x7d<<3|3)): print("7d 011"); 
            elif (self._IR == (0x7d<<3|4)): print("7d 100"); 
            elif (self._IR == (0x7d<<3|5)): print("7d 101"); 
            elif (self._IR == (0x7d<<3|6)): print("7d 110"); 
            elif (self._IR == (0x7d<<3|7)): print("7d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # ROR-a,x                         
            elif (self._IR == (0x7e<<3|0)): print("7e 000"); 
            elif (self._IR == (0x7e<<3|1)): print("7e 001"); 
            elif (self._IR == (0x7e<<3|2)): print("7e 010"); 
            elif (self._IR == (0x7e<<3|3)): print("7e 011"); 
            elif (self._IR == (0x7e<<3|4)): print("7e 100"); 
            elif (self._IR == (0x7e<<3|5)): print("7e 101"); 
            elif (self._IR == (0x7e<<3|6)): print("7e 110"); 
            elif (self._IR == (0x7e<<3|7)): print("7e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBR7-r                          
            elif (self._IR == (0x7f<<3|0)): print("7f 000"); 
            elif (self._IR == (0x7f<<3|1)): print("7f 001"); 
            elif (self._IR == (0x7f<<3|2)): print("7f 010"); 
            elif (self._IR == (0x7f<<3|3)): print("7f 011"); 
            elif (self._IR == (0x7f<<3|4)): print("7f 100"); 
            elif (self._IR == (0x7f<<3|5)): print("7f 101"); 
            elif (self._IR == (0x7f<<3|6)): print("7f 110"); 
            elif (self._IR == (0x7f<<3|7)): print("7f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BRA-r                           
            elif (self._IR == (0x80<<3|0)): print("80 000"); 
            elif (self._IR == (0x80<<3|1)): print("80 001"); 
            elif (self._IR == (0x80<<3|2)): print("80 010"); 
            elif (self._IR == (0x80<<3|3)): print("80 011"); 
            elif (self._IR == (0x80<<3|4)): print("80 100"); 
            elif (self._IR == (0x80<<3|5)): print("80 101"); 
            elif (self._IR == (0x80<<3|6)): print("80 110"); 
            elif (self._IR == (0x80<<3|7)): print("80 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-(zp,x)                      
            elif (self._IR == (0x81<<3|0)): print("81 000"); 
            elif (self._IR == (0x81<<3|1)): print("81 001"); 
            elif (self._IR == (0x81<<3|2)): print("81 010"); 
            elif (self._IR == (0x81<<3|3)): print("81 011"); 
            elif (self._IR == (0x81<<3|4)): print("81 100"); 
            elif (self._IR == (0x81<<3|5)): print("81 101"); 
            elif (self._IR == (0x81<<3|6)): print("81 110"); 
            elif (self._IR == (0x81<<3|7)): print("81 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x82<<3|0)): print("82 000"); 
            elif (self._IR == (0x82<<3|1)): print("82 001"); 
            elif (self._IR == (0x82<<3|2)): print("82 010"); 
            elif (self._IR == (0x82<<3|3)): print("82 011"); 
            elif (self._IR == (0x82<<3|4)): print("82 100"); 
            elif (self._IR == (0x82<<3|5)): print("82 101"); 
            elif (self._IR == (0x82<<3|6)): print("82 110"); 
            elif (self._IR == (0x82<<3|7)): print("82 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x83<<3|0)): print("83 000"); 
            elif (self._IR == (0x83<<3|1)): print("83 001"); 
            elif (self._IR == (0x83<<3|2)): print("83 010"); 
            elif (self._IR == (0x83<<3|3)): print("83 011"); 
            elif (self._IR == (0x83<<3|4)): print("83 100"); 
            elif (self._IR == (0x83<<3|5)): print("83 101"); 
            elif (self._IR == (0x83<<3|6)): print("83 110"); 
            elif (self._IR == (0x83<<3|7)): print("83 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STY-zp                          
            elif (self._IR == (0x84<<3|0)): print("84 000"); 
            elif (self._IR == (0x84<<3|1)): print("84 001"); 
            elif (self._IR == (0x84<<3|2)): print("84 010"); 
            elif (self._IR == (0x84<<3|3)): print("84 011"); 
            elif (self._IR == (0x84<<3|4)): print("84 100"); 
            elif (self._IR == (0x84<<3|5)): print("84 101"); 
            elif (self._IR == (0x84<<3|6)): print("84 110"); 
            elif (self._IR == (0x84<<3|7)): print("84 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-zp                          
            elif (self._IR == (0x85<<3|0)): print("85 000"); 
            elif (self._IR == (0x85<<3|1)): print("85 001"); 
            elif (self._IR == (0x85<<3|2)): print("85 010"); 
            elif (self._IR == (0x85<<3|3)): print("85 011"); 
            elif (self._IR == (0x85<<3|4)): print("85 100"); 
            elif (self._IR == (0x85<<3|5)): print("85 101"); 
            elif (self._IR == (0x85<<3|6)): print("85 110"); 
            elif (self._IR == (0x85<<3|7)): print("85 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STX-zp                          
            elif (self._IR == (0x86<<3|0)): print("86 000"); 
            elif (self._IR == (0x86<<3|1)): print("86 001"); 
            elif (self._IR == (0x86<<3|2)): print("86 010"); 
            elif (self._IR == (0x86<<3|3)): print("86 011"); 
            elif (self._IR == (0x86<<3|4)): print("86 100"); 
            elif (self._IR == (0x86<<3|5)): print("86 101"); 
            elif (self._IR == (0x86<<3|6)): print("86 110"); 
            elif (self._IR == (0x86<<3|7)): print("86 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB0-zp                         
            elif (self._IR == (0x87<<3|0)): print("87 000"); 
            elif (self._IR == (0x87<<3|1)): print("87 001"); 
            elif (self._IR == (0x87<<3|2)): print("87 010"); 
            elif (self._IR == (0x87<<3|3)): print("87 011"); 
            elif (self._IR == (0x87<<3|4)): print("87 100"); 
            elif (self._IR == (0x87<<3|5)): print("87 101"); 
            elif (self._IR == (0x87<<3|6)): print("87 110"); 
            elif (self._IR == (0x87<<3|7)): print("87 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEY-i                           
            elif (self._IR == (0x88<<3|0)): print("88 000"); 
            elif (self._IR == (0x88<<3|1)): print("88 001"); 
            elif (self._IR == (0x88<<3|2)): print("88 010"); 
            elif (self._IR == (0x88<<3|3)): print("88 011"); 
            elif (self._IR == (0x88<<3|4)): print("88 100"); 
            elif (self._IR == (0x88<<3|5)): print("88 101"); 
            elif (self._IR == (0x88<<3|6)): print("88 110"); 
            elif (self._IR == (0x88<<3|7)): print("88 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BIT-#                           
            elif (self._IR == (0x89<<3|0)): print("89 000"); 
            elif (self._IR == (0x89<<3|1)): print("89 001"); 
            elif (self._IR == (0x89<<3|2)): print("89 010"); 
            elif (self._IR == (0x89<<3|3)): print("89 011"); 
            elif (self._IR == (0x89<<3|4)): print("89 100"); 
            elif (self._IR == (0x89<<3|5)): print("89 101"); 
            elif (self._IR == (0x89<<3|6)): print("89 110"); 
            elif (self._IR == (0x89<<3|7)): print("89 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TXA-i                           
            elif (self._IR == (0x8a<<3|0)): print("8a 000"); 
            elif (self._IR == (0x8a<<3|1)): print("8a 001"); 
            elif (self._IR == (0x8a<<3|2)): print("8a 010"); 
            elif (self._IR == (0x8a<<3|3)): print("8a 011"); 
            elif (self._IR == (0x8a<<3|4)): print("8a 100"); 
            elif (self._IR == (0x8a<<3|5)): print("8a 101"); 
            elif (self._IR == (0x8a<<3|6)): print("8a 110"); 
            elif (self._IR == (0x8a<<3|7)): print("8a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x8b<<3|0)): print("8b 000"); 
            elif (self._IR == (0x8b<<3|1)): print("8b 001"); 
            elif (self._IR == (0x8b<<3|2)): print("8b 010"); 
            elif (self._IR == (0x8b<<3|3)): print("8b 011"); 
            elif (self._IR == (0x8b<<3|4)): print("8b 100"); 
            elif (self._IR == (0x8b<<3|5)): print("8b 101"); 
            elif (self._IR == (0x8b<<3|6)): print("8b 110"); 
            elif (self._IR == (0x8b<<3|7)): print("8b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STY-a                           
            elif (self._IR == (0x8c<<3|0)): print("8c 000"); 
            elif (self._IR == (0x8c<<3|1)): print("8c 001"); 
            elif (self._IR == (0x8c<<3|2)): print("8c 010"); 
            elif (self._IR == (0x8c<<3|3)): print("8c 011"); 
            elif (self._IR == (0x8c<<3|4)): print("8c 100"); 
            elif (self._IR == (0x8c<<3|5)): print("8c 101"); 
            elif (self._IR == (0x8c<<3|6)): print("8c 110"); 
            elif (self._IR == (0x8c<<3|7)): print("8c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-a                           
            elif (self._IR == (0x8d<<3|0)): print("8d 000"); 
            elif (self._IR == (0x8d<<3|1)): print("8d 001"); 
            elif (self._IR == (0x8d<<3|2)): print("8d 010"); 
            elif (self._IR == (0x8d<<3|3)): print("8d 011"); 
            elif (self._IR == (0x8d<<3|4)): print("8d 100"); 
            elif (self._IR == (0x8d<<3|5)): print("8d 101"); 
            elif (self._IR == (0x8d<<3|6)): print("8d 110"); 
            elif (self._IR == (0x8d<<3|7)): print("8d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STX-a                           
            elif (self._IR == (0x8e<<3|0)): print("8e 000"); 
            elif (self._IR == (0x8e<<3|1)): print("8e 001"); 
            elif (self._IR == (0x8e<<3|2)): print("8e 010"); 
            elif (self._IR == (0x8e<<3|3)): print("8e 011"); 
            elif (self._IR == (0x8e<<3|4)): print("8e 100"); 
            elif (self._IR == (0x8e<<3|5)): print("8e 101"); 
            elif (self._IR == (0x8e<<3|6)): print("8e 110"); 
            elif (self._IR == (0x8e<<3|7)): print("8e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS0-r                          
            elif (self._IR == (0x8f<<3|0)): print("8f 000"); 
            elif (self._IR == (0x8f<<3|1)): print("8f 001"); 
            elif (self._IR == (0x8f<<3|2)): print("8f 010"); 
            elif (self._IR == (0x8f<<3|3)): print("8f 011"); 
            elif (self._IR == (0x8f<<3|4)): print("8f 100"); 
            elif (self._IR == (0x8f<<3|5)): print("8f 101"); 
            elif (self._IR == (0x8f<<3|6)): print("8f 110"); 
            elif (self._IR == (0x8f<<3|7)): print("8f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BCC-r                           
            elif (self._IR == (0x90<<3|0)): print("90 000"); 
            elif (self._IR == (0x90<<3|1)): print("90 001"); 
            elif (self._IR == (0x90<<3|2)): print("90 010"); 
            elif (self._IR == (0x90<<3|3)): print("90 011"); 
            elif (self._IR == (0x90<<3|4)): print("90 100"); 
            elif (self._IR == (0x90<<3|5)): print("90 101"); 
            elif (self._IR == (0x90<<3|6)): print("90 110"); 
            elif (self._IR == (0x90<<3|7)): print("90 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-(zp),y                      
            elif (self._IR == (0x91<<3|0)): print("91 000"); 
            elif (self._IR == (0x91<<3|1)): print("91 001"); 
            elif (self._IR == (0x91<<3|2)): print("91 010"); 
            elif (self._IR == (0x91<<3|3)): print("91 011"); 
            elif (self._IR == (0x91<<3|4)): print("91 100"); 
            elif (self._IR == (0x91<<3|5)): print("91 101"); 
            elif (self._IR == (0x91<<3|6)): print("91 110"); 
            elif (self._IR == (0x91<<3|7)): print("91 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-(zp)                        
            elif (self._IR == (0x92<<3|0)): print("92 000"); 
            elif (self._IR == (0x92<<3|1)): print("92 001"); 
            elif (self._IR == (0x92<<3|2)): print("92 010"); 
            elif (self._IR == (0x92<<3|3)): print("92 011"); 
            elif (self._IR == (0x92<<3|4)): print("92 100"); 
            elif (self._IR == (0x92<<3|5)): print("92 101"); 
            elif (self._IR == (0x92<<3|6)): print("92 110"); 
            elif (self._IR == (0x92<<3|7)): print("92 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x93<<3|0)): print("93 000"); 
            elif (self._IR == (0x93<<3|1)): print("93 001"); 
            elif (self._IR == (0x93<<3|2)): print("93 010"); 
            elif (self._IR == (0x93<<3|3)): print("93 011"); 
            elif (self._IR == (0x93<<3|4)): print("93 100"); 
            elif (self._IR == (0x93<<3|5)): print("93 101"); 
            elif (self._IR == (0x93<<3|6)): print("93 110"); 
            elif (self._IR == (0x93<<3|7)): print("93 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STY-zp,x                        
            elif (self._IR == (0x94<<3|0)): print("94 000"); 
            elif (self._IR == (0x94<<3|1)): print("94 001"); 
            elif (self._IR == (0x94<<3|2)): print("94 010"); 
            elif (self._IR == (0x94<<3|3)): print("94 011"); 
            elif (self._IR == (0x94<<3|4)): print("94 100"); 
            elif (self._IR == (0x94<<3|5)): print("94 101"); 
            elif (self._IR == (0x94<<3|6)): print("94 110"); 
            elif (self._IR == (0x94<<3|7)): print("94 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-zp,x                        
            elif (self._IR == (0x95<<3|0)): print("95 000"); 
            elif (self._IR == (0x95<<3|1)): print("95 001"); 
            elif (self._IR == (0x95<<3|2)): print("95 010"); 
            elif (self._IR == (0x95<<3|3)): print("95 011"); 
            elif (self._IR == (0x95<<3|4)): print("95 100"); 
            elif (self._IR == (0x95<<3|5)): print("95 101"); 
            elif (self._IR == (0x95<<3|6)): print("95 110"); 
            elif (self._IR == (0x95<<3|7)): print("95 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STX-zp,y                        
            elif (self._IR == (0x96<<3|0)): print("96 000"); 
            elif (self._IR == (0x96<<3|1)): print("96 001"); 
            elif (self._IR == (0x96<<3|2)): print("96 010"); 
            elif (self._IR == (0x96<<3|3)): print("96 011"); 
            elif (self._IR == (0x96<<3|4)): print("96 100"); 
            elif (self._IR == (0x96<<3|5)): print("96 101"); 
            elif (self._IR == (0x96<<3|6)): print("96 110"); 
            elif (self._IR == (0x96<<3|7)): print("96 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB1-zp                         
            elif (self._IR == (0x97<<3|0)): print("97 000"); 
            elif (self._IR == (0x97<<3|1)): print("97 001"); 
            elif (self._IR == (0x97<<3|2)): print("97 010"); 
            elif (self._IR == (0x97<<3|3)): print("97 011"); 
            elif (self._IR == (0x97<<3|4)): print("97 100"); 
            elif (self._IR == (0x97<<3|5)): print("97 101"); 
            elif (self._IR == (0x97<<3|6)): print("97 110"); 
            elif (self._IR == (0x97<<3|7)): print("97 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TYA-i                           
            elif (self._IR == (0x98<<3|0)): print("98 000"); 
            elif (self._IR == (0x98<<3|1)): print("98 001"); 
            elif (self._IR == (0x98<<3|2)): print("98 010"); 
            elif (self._IR == (0x98<<3|3)): print("98 011"); 
            elif (self._IR == (0x98<<3|4)): print("98 100"); 
            elif (self._IR == (0x98<<3|5)): print("98 101"); 
            elif (self._IR == (0x98<<3|6)): print("98 110"); 
            elif (self._IR == (0x98<<3|7)): print("98 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-a,y                         
            elif (self._IR == (0x99<<3|0)): print("99 000"); 
            elif (self._IR == (0x99<<3|1)): print("99 001"); 
            elif (self._IR == (0x99<<3|2)): print("99 010"); 
            elif (self._IR == (0x99<<3|3)): print("99 011"); 
            elif (self._IR == (0x99<<3|4)): print("99 100"); 
            elif (self._IR == (0x99<<3|5)): print("99 101"); 
            elif (self._IR == (0x99<<3|6)): print("99 110"); 
            elif (self._IR == (0x99<<3|7)): print("99 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TXS-i                           
            elif (self._IR == (0x9a<<3|0)): print("9a 000"); 
            elif (self._IR == (0x9a<<3|1)): print("9a 001"); 
            elif (self._IR == (0x9a<<3|2)): print("9a 010"); 
            elif (self._IR == (0x9a<<3|3)): print("9a 011"); 
            elif (self._IR == (0x9a<<3|4)): print("9a 100"); 
            elif (self._IR == (0x9a<<3|5)): print("9a 101"); 
            elif (self._IR == (0x9a<<3|6)): print("9a 110"); 
            elif (self._IR == (0x9a<<3|7)): print("9a 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0x9b<<3|0)): print("9b 000"); 
            elif (self._IR == (0x9b<<3|1)): print("9b 001"); 
            elif (self._IR == (0x9b<<3|2)): print("9b 010"); 
            elif (self._IR == (0x9b<<3|3)): print("9b 011"); 
            elif (self._IR == (0x9b<<3|4)): print("9b 100"); 
            elif (self._IR == (0x9b<<3|5)): print("9b 101"); 
            elif (self._IR == (0x9b<<3|6)): print("9b 110"); 
            elif (self._IR == (0x9b<<3|7)): print("9b 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STZ-a                           
            elif (self._IR == (0x9c<<3|0)): print("9c 000"); 
            elif (self._IR == (0x9c<<3|1)): print("9c 001"); 
            elif (self._IR == (0x9c<<3|2)): print("9c 010"); 
            elif (self._IR == (0x9c<<3|3)): print("9c 011"); 
            elif (self._IR == (0x9c<<3|4)): print("9c 100"); 
            elif (self._IR == (0x9c<<3|5)): print("9c 101"); 
            elif (self._IR == (0x9c<<3|6)): print("9c 110"); 
            elif (self._IR == (0x9c<<3|7)): print("9c 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STA-a,x                         
            elif (self._IR == (0x9d<<3|0)): print("9d 000"); 
            elif (self._IR == (0x9d<<3|1)): print("9d 001"); 
            elif (self._IR == (0x9d<<3|2)): print("9d 010"); 
            elif (self._IR == (0x9d<<3|3)): print("9d 011"); 
            elif (self._IR == (0x9d<<3|4)): print("9d 100"); 
            elif (self._IR == (0x9d<<3|5)): print("9d 101"); 
            elif (self._IR == (0x9d<<3|6)): print("9d 110"); 
            elif (self._IR == (0x9d<<3|7)): print("9d 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STZ-a,x                         
            elif (self._IR == (0x9e<<3|0)): print("9e 000"); 
            elif (self._IR == (0x9e<<3|1)): print("9e 001"); 
            elif (self._IR == (0x9e<<3|2)): print("9e 010"); 
            elif (self._IR == (0x9e<<3|3)): print("9e 011"); 
            elif (self._IR == (0x9e<<3|4)): print("9e 100"); 
            elif (self._IR == (0x9e<<3|5)): print("9e 101"); 
            elif (self._IR == (0x9e<<3|6)): print("9e 110"); 
            elif (self._IR == (0x9e<<3|7)): print("9e 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS1-r                          
            elif (self._IR == (0x9f<<3|0)): print("9f 000"); 
            elif (self._IR == (0x9f<<3|1)): print("9f 001"); 
            elif (self._IR == (0x9f<<3|2)): print("9f 010"); 
            elif (self._IR == (0x9f<<3|3)): print("9f 011"); 
            elif (self._IR == (0x9f<<3|4)): print("9f 100"); 
            elif (self._IR == (0x9f<<3|5)): print("9f 101"); 
            elif (self._IR == (0x9f<<3|6)): print("9f 110"); 
            elif (self._IR == (0x9f<<3|7)): print("9f 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # LDY-#                           
            elif (self._IR == (0xa0<<3|0)): print("a0 000"); 
            elif (self._IR == (0xa0<<3|1)): print("a0 001"); 
            elif (self._IR == (0xa0<<3|2)): print("a0 010"); 
            elif (self._IR == (0xa0<<3|3)): print("a0 011"); 
            elif (self._IR == (0xa0<<3|4)): print("a0 100"); 
            elif (self._IR == (0xa0<<3|5)): print("a0 101"); 
            elif (self._IR == (0xa0<<3|6)): print("a0 110"); 
            elif (self._IR == (0xa0<<3|7)): print("a0 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-(zp,x)                      
            elif (self._IR == (0xa1<<3|0)): print("a1 000"); 
            elif (self._IR == (0xa1<<3|1)): print("a1 001"); 
            elif (self._IR == (0xa1<<3|2)): print("a1 010"); 
            elif (self._IR == (0xa1<<3|3)): print("a1 011"); 
            elif (self._IR == (0xa1<<3|4)): print("a1 100"); 
            elif (self._IR == (0xa1<<3|5)): print("a1 101"); 
            elif (self._IR == (0xa1<<3|6)): print("a1 110"); 
            elif (self._IR == (0xa1<<3|7)): print("a1 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDX-#                           
            elif (self._IR == (0xa2<<3|0)): print("a2 000"); 
            elif (self._IR == (0xa2<<3|1)): print("a2 001"); 
            elif (self._IR == (0xa2<<3|2)): print("a2 010"); 
            elif (self._IR == (0xa2<<3|3)): print("a2 011"); 
            elif (self._IR == (0xa2<<3|4)): print("a2 100"); 
            elif (self._IR == (0xa2<<3|5)): print("a2 101"); 
            elif (self._IR == (0xa2<<3|6)): print("a2 110"); 
            elif (self._IR == (0xa2<<3|7)): print("a2 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xa3<<3|0)): print("a3 000"); 
            elif (self._IR == (0xa3<<3|1)): print("a3 001"); 
            elif (self._IR == (0xa3<<3|2)): print("a3 010"); 
            elif (self._IR == (0xa3<<3|3)): print("a3 011"); 
            elif (self._IR == (0xa3<<3|4)): print("a3 100"); 
            elif (self._IR == (0xa3<<3|5)): print("a3 101"); 
            elif (self._IR == (0xa3<<3|6)): print("a3 110"); 
            elif (self._IR == (0xa3<<3|7)): print("a3 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDY-zp                          
            elif (self._IR == (0xa4<<3|0)): print("a4 000"); 
            elif (self._IR == (0xa4<<3|1)): print("a4 001"); 
            elif (self._IR == (0xa4<<3|2)): print("a4 010"); 
            elif (self._IR == (0xa4<<3|3)): print("a4 011"); 
            elif (self._IR == (0xa4<<3|4)): print("a4 100"); 
            elif (self._IR == (0xa4<<3|5)): print("a4 101"); 
            elif (self._IR == (0xa4<<3|6)): print("a4 110"); 
            elif (self._IR == (0xa4<<3|7)): print("a4 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-zp                          
            elif (self._IR == (0xa5<<3|0)): print("a5 000"); 
            elif (self._IR == (0xa5<<3|1)): print("a5 001"); 
            elif (self._IR == (0xa5<<3|2)): print("a5 010"); 
            elif (self._IR == (0xa5<<3|3)): print("a5 011"); 
            elif (self._IR == (0xa5<<3|4)): print("a5 100"); 
            elif (self._IR == (0xa5<<3|5)): print("a5 101"); 
            elif (self._IR == (0xa5<<3|6)): print("a5 110"); 
            elif (self._IR == (0xa5<<3|7)): print("a5 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDX-zp                          
            elif (self._IR == (0xa6<<3|0)): print("a6 000"); 
            elif (self._IR == (0xa6<<3|1)): print("a6 001"); 
            elif (self._IR == (0xa6<<3|2)): print("a6 010"); 
            elif (self._IR == (0xa6<<3|3)): print("a6 011"); 
            elif (self._IR == (0xa6<<3|4)): print("a6 100"); 
            elif (self._IR == (0xa6<<3|5)): print("a6 101"); 
            elif (self._IR == (0xa6<<3|6)): print("a6 110"); 
            elif (self._IR == (0xa6<<3|7)): print("a6 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB2-zp                         
            elif (self._IR == (0xa7<<3|0)): print("a7 000"); 
            elif (self._IR == (0xa7<<3|1)): print("a7 001"); 
            elif (self._IR == (0xa7<<3|2)): print("a7 010"); 
            elif (self._IR == (0xa7<<3|3)): print("a7 011"); 
            elif (self._IR == (0xa7<<3|4)): print("a7 100"); 
            elif (self._IR == (0xa7<<3|5)): print("a7 101"); 
            elif (self._IR == (0xa7<<3|6)): print("a7 110"); 
            elif (self._IR == (0xa7<<3|7)): print("a7 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TAY-i                           
            elif (self._IR == (0xa8<<3|0)): print("a8 000"); 
            elif (self._IR == (0xa8<<3|1)): print("a8 001"); 
            elif (self._IR == (0xa8<<3|2)): print("a8 010"); 
            elif (self._IR == (0xa8<<3|3)): print("a8 011"); 
            elif (self._IR == (0xa8<<3|4)): print("a8 100"); 
            elif (self._IR == (0xa8<<3|5)): print("a8 101"); 
            elif (self._IR == (0xa8<<3|6)): print("a8 110"); 
            elif (self._IR == (0xa8<<3|7)): print("a8 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-#                           
            elif (self._IR == (0xa9<<3|0)): print("a9 000"); 
            elif (self._IR == (0xa9<<3|1)): print("a9 001"); 
            elif (self._IR == (0xa9<<3|2)): print("a9 010"); 
            elif (self._IR == (0xa9<<3|3)): print("a9 011"); 
            elif (self._IR == (0xa9<<3|4)): print("a9 100"); 
            elif (self._IR == (0xa9<<3|5)): print("a9 101"); 
            elif (self._IR == (0xa9<<3|6)): print("a9 110"); 
            elif (self._IR == (0xa9<<3|7)): print("a9 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TAX-i                           
            elif (self._IR == (0xaa<<3|0)): print("aa 000"); 
            elif (self._IR == (0xaa<<3|1)): print("aa 001"); 
            elif (self._IR == (0xaa<<3|2)): print("aa 010"); 
            elif (self._IR == (0xaa<<3|3)): print("aa 011"); 
            elif (self._IR == (0xaa<<3|4)): print("aa 100"); 
            elif (self._IR == (0xaa<<3|5)): print("aa 101"); 
            elif (self._IR == (0xaa<<3|6)): print("aa 110"); 
            elif (self._IR == (0xaa<<3|7)): print("aa 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xab<<3|0)): print("ab 000"); 
            elif (self._IR == (0xab<<3|1)): print("ab 001"); 
            elif (self._IR == (0xab<<3|2)): print("ab 010"); 
            elif (self._IR == (0xab<<3|3)): print("ab 011"); 
            elif (self._IR == (0xab<<3|4)): print("ab 100"); 
            elif (self._IR == (0xab<<3|5)): print("ab 101"); 
            elif (self._IR == (0xab<<3|6)): print("ab 110"); 
            elif (self._IR == (0xab<<3|7)): print("ab 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDY-A                           
            elif (self._IR == (0xac<<3|0)): print("ac 000"); 
            elif (self._IR == (0xac<<3|1)): print("ac 001"); 
            elif (self._IR == (0xac<<3|2)): print("ac 010"); 
            elif (self._IR == (0xac<<3|3)): print("ac 011"); 
            elif (self._IR == (0xac<<3|4)): print("ac 100"); 
            elif (self._IR == (0xac<<3|5)): print("ac 101"); 
            elif (self._IR == (0xac<<3|6)): print("ac 110"); 
            elif (self._IR == (0xac<<3|7)): print("ac 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-a                           
            elif (self._IR == (0xad<<3|0)): print("ad 000"); 
            elif (self._IR == (0xad<<3|1)): print("ad 001"); 
            elif (self._IR == (0xad<<3|2)): print("ad 010"); 
            elif (self._IR == (0xad<<3|3)): print("ad 011"); 
            elif (self._IR == (0xad<<3|4)): print("ad 100"); 
            elif (self._IR == (0xad<<3|5)): print("ad 101"); 
            elif (self._IR == (0xad<<3|6)): print("ad 110"); 
            elif (self._IR == (0xad<<3|7)): print("ad 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDX-a                           
            elif (self._IR == (0xae<<3|0)): print("ae 000"); 
            elif (self._IR == (0xae<<3|1)): print("ae 001"); 
            elif (self._IR == (0xae<<3|2)): print("ae 010"); 
            elif (self._IR == (0xae<<3|3)): print("ae 011"); 
            elif (self._IR == (0xae<<3|4)): print("ae 100"); 
            elif (self._IR == (0xae<<3|5)): print("ae 101"); 
            elif (self._IR == (0xae<<3|6)): print("ae 110"); 
            elif (self._IR == (0xae<<3|7)): print("ae 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS2-r                          
            elif (self._IR == (0xaf<<3|0)): print("af 000"); 
            elif (self._IR == (0xaf<<3|1)): print("af 001"); 
            elif (self._IR == (0xaf<<3|2)): print("af 010"); 
            elif (self._IR == (0xaf<<3|3)): print("af 011"); 
            elif (self._IR == (0xaf<<3|4)): print("af 100"); 
            elif (self._IR == (0xaf<<3|5)): print("af 101"); 
            elif (self._IR == (0xaf<<3|6)): print("af 110"); 
            elif (self._IR == (0xaf<<3|7)): print("af 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BCS-r                           
            elif (self._IR == (0xb0<<3|0)): print("b0 000"); 
            elif (self._IR == (0xb0<<3|1)): print("b0 001"); 
            elif (self._IR == (0xb0<<3|2)): print("b0 010"); 
            elif (self._IR == (0xb0<<3|3)): print("b0 011"); 
            elif (self._IR == (0xb0<<3|4)): print("b0 100"); 
            elif (self._IR == (0xb0<<3|5)): print("b0 101"); 
            elif (self._IR == (0xb0<<3|6)): print("b0 110"); 
            elif (self._IR == (0xb0<<3|7)): print("b0 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-(zp),y                      
            elif (self._IR == (0xb1<<3|0)): print("b1 000"); 
            elif (self._IR == (0xb1<<3|1)): print("b1 001"); 
            elif (self._IR == (0xb1<<3|2)): print("b1 010"); 
            elif (self._IR == (0xb1<<3|3)): print("b1 011"); 
            elif (self._IR == (0xb1<<3|4)): print("b1 100"); 
            elif (self._IR == (0xb1<<3|5)): print("b1 101"); 
            elif (self._IR == (0xb1<<3|6)): print("b1 110"); 
            elif (self._IR == (0xb1<<3|7)): print("b1 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-(zp)                        
            elif (self._IR == (0xb2<<3|0)): print("b2 000"); 
            elif (self._IR == (0xb2<<3|1)): print("b2 001"); 
            elif (self._IR == (0xb2<<3|2)): print("b2 010"); 
            elif (self._IR == (0xb2<<3|3)): print("b2 011"); 
            elif (self._IR == (0xb2<<3|4)): print("b2 100"); 
            elif (self._IR == (0xb2<<3|5)): print("b2 101"); 
            elif (self._IR == (0xb2<<3|6)): print("b2 110"); 
            elif (self._IR == (0xb2<<3|7)): print("b2 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xb3<<3|0)): print("b3 000"); 
            elif (self._IR == (0xb3<<3|1)): print("b3 001"); 
            elif (self._IR == (0xb3<<3|2)): print("b3 010"); 
            elif (self._IR == (0xb3<<3|3)): print("b3 011"); 
            elif (self._IR == (0xb3<<3|4)): print("b3 100"); 
            elif (self._IR == (0xb3<<3|5)): print("b3 101"); 
            elif (self._IR == (0xb3<<3|6)): print("b3 110"); 
            elif (self._IR == (0xb3<<3|7)): print("b3 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDY-zp,x                        
            elif (self._IR == (0xb4<<3|0)): print("b4 000"); 
            elif (self._IR == (0xb4<<3|1)): print("b4 001"); 
            elif (self._IR == (0xb4<<3|2)): print("b4 010"); 
            elif (self._IR == (0xb4<<3|3)): print("b4 011"); 
            elif (self._IR == (0xb4<<3|4)): print("b4 100"); 
            elif (self._IR == (0xb4<<3|5)): print("b4 101"); 
            elif (self._IR == (0xb4<<3|6)): print("b4 110"); 
            elif (self._IR == (0xb4<<3|7)): print("b4 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-zp,x                        
            elif (self._IR == (0xb5<<3|0)): print("b5 000"); 
            elif (self._IR == (0xb5<<3|1)): print("b5 001"); 
            elif (self._IR == (0xb5<<3|2)): print("b5 010"); 
            elif (self._IR == (0xb5<<3|3)): print("b5 011"); 
            elif (self._IR == (0xb5<<3|4)): print("b5 100"); 
            elif (self._IR == (0xb5<<3|5)): print("b5 101"); 
            elif (self._IR == (0xb5<<3|6)): print("b5 110"); 
            elif (self._IR == (0xb5<<3|7)): print("b5 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDX-zp,y                        
            elif (self._IR == (0xb6<<3|0)): print("b6 000"); 
            elif (self._IR == (0xb6<<3|1)): print("b6 001"); 
            elif (self._IR == (0xb6<<3|2)): print("b6 010"); 
            elif (self._IR == (0xb6<<3|3)): print("b6 011"); 
            elif (self._IR == (0xb6<<3|4)): print("b6 100"); 
            elif (self._IR == (0xb6<<3|5)): print("b6 101"); 
            elif (self._IR == (0xb6<<3|6)): print("b6 110"); 
            elif (self._IR == (0xb6<<3|7)): print("b6 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB3-zp                         
            elif (self._IR == (0xb7<<3|0)): print("b7 000"); 
            elif (self._IR == (0xb7<<3|1)): print("b7 001"); 
            elif (self._IR == (0xb7<<3|2)): print("b7 010"); 
            elif (self._IR == (0xb7<<3|3)): print("b7 011"); 
            elif (self._IR == (0xb7<<3|4)): print("b7 100"); 
            elif (self._IR == (0xb7<<3|5)): print("b7 101"); 
            elif (self._IR == (0xb7<<3|6)): print("b7 110"); 
            elif (self._IR == (0xb7<<3|7)): print("b7 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CLV-i                           
            elif (self._IR == (0xb8<<3|0)): print("b8 000"); 
            elif (self._IR == (0xb8<<3|1)): print("b8 001"); 
            elif (self._IR == (0xb8<<3|2)): print("b8 010"); 
            elif (self._IR == (0xb8<<3|3)): print("b8 011"); 
            elif (self._IR == (0xb8<<3|4)): print("b8 100"); 
            elif (self._IR == (0xb8<<3|5)): print("b8 101"); 
            elif (self._IR == (0xb8<<3|6)): print("b8 110"); 
            elif (self._IR == (0xb8<<3|7)): print("b8 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-A,y                         
            elif (self._IR == (0xb9<<3|0)): print("b9 000"); 
            elif (self._IR == (0xb9<<3|1)): print("b9 001"); 
            elif (self._IR == (0xb9<<3|2)): print("b9 010"); 
            elif (self._IR == (0xb9<<3|3)): print("b9 011"); 
            elif (self._IR == (0xb9<<3|4)): print("b9 100"); 
            elif (self._IR == (0xb9<<3|5)): print("b9 101"); 
            elif (self._IR == (0xb9<<3|6)): print("b9 110"); 
            elif (self._IR == (0xb9<<3|7)): print("b9 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # TSX-i                           
            elif (self._IR == (0xba<<3|0)): print("ba 000"); 
            elif (self._IR == (0xba<<3|1)): print("ba 001"); 
            elif (self._IR == (0xba<<3|2)): print("ba 010"); 
            elif (self._IR == (0xba<<3|3)): print("ba 011"); 
            elif (self._IR == (0xba<<3|4)): print("ba 100"); 
            elif (self._IR == (0xba<<3|5)): print("ba 101"); 
            elif (self._IR == (0xba<<3|6)): print("ba 110"); 
            elif (self._IR == (0xba<<3|7)): print("ba 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xbb<<3|0)): print("bb 000"); 
            elif (self._IR == (0xbb<<3|1)): print("bb 001"); 
            elif (self._IR == (0xbb<<3|2)): print("bb 010"); 
            elif (self._IR == (0xbb<<3|3)): print("bb 011"); 
            elif (self._IR == (0xbb<<3|4)): print("bb 100"); 
            elif (self._IR == (0xbb<<3|5)): print("bb 101"); 
            elif (self._IR == (0xbb<<3|6)): print("bb 110"); 
            elif (self._IR == (0xbb<<3|7)): print("bb 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDY-a,x                         
            elif (self._IR == (0xbc<<3|0)): print("bc 000"); 
            elif (self._IR == (0xbc<<3|1)): print("bc 001"); 
            elif (self._IR == (0xbc<<3|2)): print("bc 010"); 
            elif (self._IR == (0xbc<<3|3)): print("bc 011"); 
            elif (self._IR == (0xbc<<3|4)): print("bc 100"); 
            elif (self._IR == (0xbc<<3|5)): print("bc 101"); 
            elif (self._IR == (0xbc<<3|6)): print("bc 110"); 
            elif (self._IR == (0xbc<<3|7)): print("bc 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDA-a,x                         
            elif (self._IR == (0xbd<<3|0)): print("bd 000"); 
            elif (self._IR == (0xbd<<3|1)): print("bd 001"); 
            elif (self._IR == (0xbd<<3|2)): print("bd 010"); 
            elif (self._IR == (0xbd<<3|3)): print("bd 011"); 
            elif (self._IR == (0xbd<<3|4)): print("bd 100"); 
            elif (self._IR == (0xbd<<3|5)): print("bd 101"); 
            elif (self._IR == (0xbd<<3|6)): print("bd 110"); 
            elif (self._IR == (0xbd<<3|7)): print("bd 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # LDX-a,y                         
            elif (self._IR == (0xbe<<3|0)): print("be 000"); 
            elif (self._IR == (0xbe<<3|1)): print("be 001"); 
            elif (self._IR == (0xbe<<3|2)): print("be 010"); 
            elif (self._IR == (0xbe<<3|3)): print("be 011"); 
            elif (self._IR == (0xbe<<3|4)): print("be 100"); 
            elif (self._IR == (0xbe<<3|5)): print("be 101"); 
            elif (self._IR == (0xbe<<3|6)): print("be 110"); 
            elif (self._IR == (0xbe<<3|7)): print("be 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS3-r                          
            elif (self._IR == (0xbf<<3|0)): print("bf 000"); 
            elif (self._IR == (0xbf<<3|1)): print("bf 001"); 
            elif (self._IR == (0xbf<<3|2)): print("bf 010"); 
            elif (self._IR == (0xbf<<3|3)): print("bf 011"); 
            elif (self._IR == (0xbf<<3|4)): print("bf 100"); 
            elif (self._IR == (0xbf<<3|5)): print("bf 101"); 
            elif (self._IR == (0xbf<<3|6)): print("bf 110"); 
            elif (self._IR == (0xbf<<3|7)): print("bf 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # CPY-#                           
            elif (self._IR == (0xc0<<3|0)): print("c0 000"); 
            elif (self._IR == (0xc0<<3|1)): print("c0 001"); 
            elif (self._IR == (0xc0<<3|2)): print("c0 010"); 
            elif (self._IR == (0xc0<<3|3)): print("c0 011"); 
            elif (self._IR == (0xc0<<3|4)): print("c0 100"); 
            elif (self._IR == (0xc0<<3|5)): print("c0 101"); 
            elif (self._IR == (0xc0<<3|6)): print("c0 110"); 
            elif (self._IR == (0xc0<<3|7)): print("c0 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-(zp,x)                      
            elif (self._IR == (0xc1<<3|0)): print("c1 000"); 
            elif (self._IR == (0xc1<<3|1)): print("c1 001"); 
            elif (self._IR == (0xc1<<3|2)): print("c1 010"); 
            elif (self._IR == (0xc1<<3|3)): print("c1 011"); 
            elif (self._IR == (0xc1<<3|4)): print("c1 100"); 
            elif (self._IR == (0xc1<<3|5)): print("c1 101"); 
            elif (self._IR == (0xc1<<3|6)): print("c1 110"); 
            elif (self._IR == (0xc1<<3|7)): print("c1 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xc2<<3|0)): print("c2 000"); 
            elif (self._IR == (0xc2<<3|1)): print("c2 001"); 
            elif (self._IR == (0xc2<<3|2)): print("c2 010"); 
            elif (self._IR == (0xc2<<3|3)): print("c2 011"); 
            elif (self._IR == (0xc2<<3|4)): print("c2 100"); 
            elif (self._IR == (0xc2<<3|5)): print("c2 101"); 
            elif (self._IR == (0xc2<<3|6)): print("c2 110"); 
            elif (self._IR == (0xc2<<3|7)): print("c2 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xc3<<3|0)): print("c3 000"); 
            elif (self._IR == (0xc3<<3|1)): print("c3 001"); 
            elif (self._IR == (0xc3<<3|2)): print("c3 010"); 
            elif (self._IR == (0xc3<<3|3)): print("c3 011"); 
            elif (self._IR == (0xc3<<3|4)): print("c3 100"); 
            elif (self._IR == (0xc3<<3|5)): print("c3 101"); 
            elif (self._IR == (0xc3<<3|6)): print("c3 110"); 
            elif (self._IR == (0xc3<<3|7)): print("c3 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CPY-zp                          
            elif (self._IR == (0xc4<<3|0)): print("c4 000"); 
            elif (self._IR == (0xc4<<3|1)): print("c4 001"); 
            elif (self._IR == (0xc4<<3|2)): print("c4 010"); 
            elif (self._IR == (0xc4<<3|3)): print("c4 011"); 
            elif (self._IR == (0xc4<<3|4)): print("c4 100"); 
            elif (self._IR == (0xc4<<3|5)): print("c4 101"); 
            elif (self._IR == (0xc4<<3|6)): print("c4 110"); 
            elif (self._IR == (0xc4<<3|7)): print("c4 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-zp                          
            elif (self._IR == (0xc5<<3|0)): print("c5 000"); 
            elif (self._IR == (0xc5<<3|1)): print("c5 001"); 
            elif (self._IR == (0xc5<<3|2)): print("c5 010"); 
            elif (self._IR == (0xc5<<3|3)): print("c5 011"); 
            elif (self._IR == (0xc5<<3|4)): print("c5 100"); 
            elif (self._IR == (0xc5<<3|5)): print("c5 101"); 
            elif (self._IR == (0xc5<<3|6)): print("c5 110"); 
            elif (self._IR == (0xc5<<3|7)): print("c5 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEC-zp                          
            elif (self._IR == (0xc6<<3|0)): print("c6 000"); 
            elif (self._IR == (0xc6<<3|1)): print("c6 001"); 
            elif (self._IR == (0xc6<<3|2)): print("c6 010"); 
            elif (self._IR == (0xc6<<3|3)): print("c6 011"); 
            elif (self._IR == (0xc6<<3|4)): print("c6 100"); 
            elif (self._IR == (0xc6<<3|5)): print("c6 101"); 
            elif (self._IR == (0xc6<<3|6)): print("c6 110"); 
            elif (self._IR == (0xc6<<3|7)): print("c6 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB4-zp                         
            elif (self._IR == (0xc7<<3|0)): print("c7 000"); 
            elif (self._IR == (0xc7<<3|1)): print("c7 001"); 
            elif (self._IR == (0xc7<<3|2)): print("c7 010"); 
            elif (self._IR == (0xc7<<3|3)): print("c7 011"); 
            elif (self._IR == (0xc7<<3|4)): print("c7 100"); 
            elif (self._IR == (0xc7<<3|5)): print("c7 101"); 
            elif (self._IR == (0xc7<<3|6)): print("c7 110"); 
            elif (self._IR == (0xc7<<3|7)): print("c7 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INY-i                           
            elif (self._IR == (0xc8<<3|0)): print("c8 000"); 
            elif (self._IR == (0xc8<<3|1)): print("c8 001"); 
            elif (self._IR == (0xc8<<3|2)): print("c8 010"); 
            elif (self._IR == (0xc8<<3|3)): print("c8 011"); 
            elif (self._IR == (0xc8<<3|4)): print("c8 100"); 
            elif (self._IR == (0xc8<<3|5)): print("c8 101"); 
            elif (self._IR == (0xc8<<3|6)): print("c8 110"); 
            elif (self._IR == (0xc8<<3|7)): print("c8 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-#                           
            elif (self._IR == (0xc9<<3|0)): print("c9 000"); 
            elif (self._IR == (0xc9<<3|1)): print("c9 001"); 
            elif (self._IR == (0xc9<<3|2)): print("c9 010"); 
            elif (self._IR == (0xc9<<3|3)): print("c9 011"); 
            elif (self._IR == (0xc9<<3|4)): print("c9 100"); 
            elif (self._IR == (0xc9<<3|5)): print("c9 101"); 
            elif (self._IR == (0xc9<<3|6)): print("c9 110"); 
            elif (self._IR == (0xc9<<3|7)): print("c9 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEX-i                           
            elif (self._IR == (0xca<<3|0)): print("ca 000"); 
            elif (self._IR == (0xca<<3|1)): print("ca 001"); 
            elif (self._IR == (0xca<<3|2)): print("ca 010"); 
            elif (self._IR == (0xca<<3|3)): print("ca 011"); 
            elif (self._IR == (0xca<<3|4)): print("ca 100"); 
            elif (self._IR == (0xca<<3|5)): print("ca 101"); 
            elif (self._IR == (0xca<<3|6)): print("ca 110"); 
            elif (self._IR == (0xca<<3|7)): print("ca 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # WAI-I                           
            elif (self._IR == (0xcb<<3|0)): print("cb 000"); 
            elif (self._IR == (0xcb<<3|1)): print("cb 001"); 
            elif (self._IR == (0xcb<<3|2)): print("cb 010"); 
            elif (self._IR == (0xcb<<3|3)): print("cb 011"); 
            elif (self._IR == (0xcb<<3|4)): print("cb 100"); 
            elif (self._IR == (0xcb<<3|5)): print("cb 101"); 
            elif (self._IR == (0xcb<<3|6)): print("cb 110"); 
            elif (self._IR == (0xcb<<3|7)): print("cb 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CPY-a                           
            elif (self._IR == (0xcc<<3|0)): print("cc 000"); 
            elif (self._IR == (0xcc<<3|1)): print("cc 001"); 
            elif (self._IR == (0xcc<<3|2)): print("cc 010"); 
            elif (self._IR == (0xcc<<3|3)): print("cc 011"); 
            elif (self._IR == (0xcc<<3|4)): print("cc 100"); 
            elif (self._IR == (0xcc<<3|5)): print("cc 101"); 
            elif (self._IR == (0xcc<<3|6)): print("cc 110"); 
            elif (self._IR == (0xcc<<3|7)): print("cc 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-a                           
            elif (self._IR == (0xcd<<3|0)): print("cd 000"); 
            elif (self._IR == (0xcd<<3|1)): print("cd 001"); 
            elif (self._IR == (0xcd<<3|2)): print("cd 010"); 
            elif (self._IR == (0xcd<<3|3)): print("cd 011"); 
            elif (self._IR == (0xcd<<3|4)): print("cd 100"); 
            elif (self._IR == (0xcd<<3|5)): print("cd 101"); 
            elif (self._IR == (0xcd<<3|6)): print("cd 110"); 
            elif (self._IR == (0xcd<<3|7)): print("cd 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEC-a                           
            elif (self._IR == (0xce<<3|0)): print("ce 000"); 
            elif (self._IR == (0xce<<3|1)): print("ce 001"); 
            elif (self._IR == (0xce<<3|2)): print("ce 010"); 
            elif (self._IR == (0xce<<3|3)): print("ce 011"); 
            elif (self._IR == (0xce<<3|4)): print("ce 100"); 
            elif (self._IR == (0xce<<3|5)): print("ce 101"); 
            elif (self._IR == (0xce<<3|6)): print("ce 110"); 
            elif (self._IR == (0xce<<3|7)): print("ce 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS4-r                          
            elif (self._IR == (0xcf<<3|0)): print("cf 000"); 
            elif (self._IR == (0xcf<<3|1)): print("cf 001"); 
            elif (self._IR == (0xcf<<3|2)): print("cf 010"); 
            elif (self._IR == (0xcf<<3|3)): print("cf 011"); 
            elif (self._IR == (0xcf<<3|4)): print("cf 100"); 
            elif (self._IR == (0xcf<<3|5)): print("cf 101"); 
            elif (self._IR == (0xcf<<3|6)): print("cf 110"); 
            elif (self._IR == (0xcf<<3|7)): print("cf 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BNE-r                           
            elif (self._IR == (0xd0<<3|0)): print("d0 000"); 
            elif (self._IR == (0xd0<<3|1)): print("d0 001"); 
            elif (self._IR == (0xd0<<3|2)): print("d0 010"); 
            elif (self._IR == (0xd0<<3|3)): print("d0 011"); 
            elif (self._IR == (0xd0<<3|4)): print("d0 100"); 
            elif (self._IR == (0xd0<<3|5)): print("d0 101"); 
            elif (self._IR == (0xd0<<3|6)): print("d0 110"); 
            elif (self._IR == (0xd0<<3|7)): print("d0 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-(zp),y                      
            elif (self._IR == (0xd1<<3|0)): print("d1 000"); 
            elif (self._IR == (0xd1<<3|1)): print("d1 001"); 
            elif (self._IR == (0xd1<<3|2)): print("d1 010"); 
            elif (self._IR == (0xd1<<3|3)): print("d1 011"); 
            elif (self._IR == (0xd1<<3|4)): print("d1 100"); 
            elif (self._IR == (0xd1<<3|5)): print("d1 101"); 
            elif (self._IR == (0xd1<<3|6)): print("d1 110"); 
            elif (self._IR == (0xd1<<3|7)): print("d1 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-(zp)                        
            elif (self._IR == (0xd2<<3|0)): print("d2 000"); 
            elif (self._IR == (0xd2<<3|1)): print("d2 001"); 
            elif (self._IR == (0xd2<<3|2)): print("d2 010"); 
            elif (self._IR == (0xd2<<3|3)): print("d2 011"); 
            elif (self._IR == (0xd2<<3|4)): print("d2 100"); 
            elif (self._IR == (0xd2<<3|5)): print("d2 101"); 
            elif (self._IR == (0xd2<<3|6)): print("d2 110"); 
            elif (self._IR == (0xd2<<3|7)): print("d2 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xd3<<3|0)): print("d3 000"); 
            elif (self._IR == (0xd3<<3|1)): print("d3 001"); 
            elif (self._IR == (0xd3<<3|2)): print("d3 010"); 
            elif (self._IR == (0xd3<<3|3)): print("d3 011"); 
            elif (self._IR == (0xd3<<3|4)): print("d3 100"); 
            elif (self._IR == (0xd3<<3|5)): print("d3 101"); 
            elif (self._IR == (0xd3<<3|6)): print("d3 110"); 
            elif (self._IR == (0xd3<<3|7)): print("d3 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xd4<<3|0)): print("d4 000"); 
            elif (self._IR == (0xd4<<3|1)): print("d4 001"); 
            elif (self._IR == (0xd4<<3|2)): print("d4 010"); 
            elif (self._IR == (0xd4<<3|3)): print("d4 011"); 
            elif (self._IR == (0xd4<<3|4)): print("d4 100"); 
            elif (self._IR == (0xd4<<3|5)): print("d4 101"); 
            elif (self._IR == (0xd4<<3|6)): print("d4 110"); 
            elif (self._IR == (0xd4<<3|7)): print("d4 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-zp,x                        
            elif (self._IR == (0xd5<<3|0)): print("d5 000"); 
            elif (self._IR == (0xd5<<3|1)): print("d5 001"); 
            elif (self._IR == (0xd5<<3|2)): print("d5 010"); 
            elif (self._IR == (0xd5<<3|3)): print("d5 011"); 
            elif (self._IR == (0xd5<<3|4)): print("d5 100"); 
            elif (self._IR == (0xd5<<3|5)): print("d5 101"); 
            elif (self._IR == (0xd5<<3|6)): print("d5 110"); 
            elif (self._IR == (0xd5<<3|7)): print("d5 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEC-zp,x                        
            elif (self._IR == (0xd6<<3|0)): print("d6 000"); 
            elif (self._IR == (0xd6<<3|1)): print("d6 001"); 
            elif (self._IR == (0xd6<<3|2)): print("d6 010"); 
            elif (self._IR == (0xd6<<3|3)): print("d6 011"); 
            elif (self._IR == (0xd6<<3|4)): print("d6 100"); 
            elif (self._IR == (0xd6<<3|5)): print("d6 101"); 
            elif (self._IR == (0xd6<<3|6)): print("d6 110"); 
            elif (self._IR == (0xd6<<3|7)): print("d6 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB5-zp                         
            elif (self._IR == (0xd7<<3|0)): print("d7 000"); 
            elif (self._IR == (0xd7<<3|1)): print("d7 001"); 
            elif (self._IR == (0xd7<<3|2)): print("d7 010"); 
            elif (self._IR == (0xd7<<3|3)): print("d7 011"); 
            elif (self._IR == (0xd7<<3|4)): print("d7 100"); 
            elif (self._IR == (0xd7<<3|5)): print("d7 101"); 
            elif (self._IR == (0xd7<<3|6)): print("d7 110"); 
            elif (self._IR == (0xd7<<3|7)): print("d7 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CLD-i                           
            elif (self._IR == (0xd8<<3|0)): print("d8 000"); 
            elif (self._IR == (0xd8<<3|1)): print("d8 001"); 
            elif (self._IR == (0xd8<<3|2)): print("d8 010"); 
            elif (self._IR == (0xd8<<3|3)): print("d8 011"); 
            elif (self._IR == (0xd8<<3|4)): print("d8 100"); 
            elif (self._IR == (0xd8<<3|5)): print("d8 101"); 
            elif (self._IR == (0xd8<<3|6)): print("d8 110"); 
            elif (self._IR == (0xd8<<3|7)): print("d8 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-a,y                         
            elif (self._IR == (0xd9<<3|0)): print("d9 000"); 
            elif (self._IR == (0xd9<<3|1)): print("d9 001"); 
            elif (self._IR == (0xd9<<3|2)): print("d9 010"); 
            elif (self._IR == (0xd9<<3|3)): print("d9 011"); 
            elif (self._IR == (0xd9<<3|4)): print("d9 100"); 
            elif (self._IR == (0xd9<<3|5)): print("d9 101"); 
            elif (self._IR == (0xd9<<3|6)): print("d9 110"); 
            elif (self._IR == (0xd9<<3|7)): print("d9 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PHX-s                           
            elif (self._IR == (0xda<<3|0)): print("da 000"); 
            elif (self._IR == (0xda<<3|1)): print("da 001"); 
            elif (self._IR == (0xda<<3|2)): print("da 010"); 
            elif (self._IR == (0xda<<3|3)): print("da 011"); 
            elif (self._IR == (0xda<<3|4)): print("da 100"); 
            elif (self._IR == (0xda<<3|5)): print("da 101"); 
            elif (self._IR == (0xda<<3|6)): print("da 110"); 
            elif (self._IR == (0xda<<3|7)): print("da 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # STP-I                           
            elif (self._IR == (0xdb<<3|0)): print("db 000"); 
            elif (self._IR == (0xdb<<3|1)): print("db 001"); 
            elif (self._IR == (0xdb<<3|2)): print("db 010"); 
            elif (self._IR == (0xdb<<3|3)): print("db 011"); 
            elif (self._IR == (0xdb<<3|4)): print("db 100"); 
            elif (self._IR == (0xdb<<3|5)): print("db 101"); 
            elif (self._IR == (0xdb<<3|6)): print("db 110"); 
            elif (self._IR == (0xdb<<3|7)): print("db 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xdc<<3|0)): print("dc 000"); 
            elif (self._IR == (0xdc<<3|1)): print("dc 001"); 
            elif (self._IR == (0xdc<<3|2)): print("dc 010"); 
            elif (self._IR == (0xdc<<3|3)): print("dc 011"); 
            elif (self._IR == (0xdc<<3|4)): print("dc 100"); 
            elif (self._IR == (0xdc<<3|5)): print("dc 101"); 
            elif (self._IR == (0xdc<<3|6)): print("dc 110"); 
            elif (self._IR == (0xdc<<3|7)): print("dc 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CMP-a,x                         
            elif (self._IR == (0xdd<<3|0)): print("dd 000"); 
            elif (self._IR == (0xdd<<3|1)): print("dd 001"); 
            elif (self._IR == (0xdd<<3|2)): print("dd 010"); 
            elif (self._IR == (0xdd<<3|3)): print("dd 011"); 
            elif (self._IR == (0xdd<<3|4)): print("dd 100"); 
            elif (self._IR == (0xdd<<3|5)): print("dd 101"); 
            elif (self._IR == (0xdd<<3|6)): print("dd 110"); 
            elif (self._IR == (0xdd<<3|7)): print("dd 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # DEC-a,x                         
            elif (self._IR == (0xde<<3|0)): print("de 000"); 
            elif (self._IR == (0xde<<3|1)): print("de 001"); 
            elif (self._IR == (0xde<<3|2)): print("de 010"); 
            elif (self._IR == (0xde<<3|3)): print("de 011"); 
            elif (self._IR == (0xde<<3|4)): print("de 100"); 
            elif (self._IR == (0xde<<3|5)): print("de 101"); 
            elif (self._IR == (0xde<<3|6)): print("de 110"); 
            elif (self._IR == (0xde<<3|7)): print("de 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS5-r                          
            elif (self._IR == (0xdf<<3|0)): print("df 000"); 
            elif (self._IR == (0xdf<<3|1)): print("df 001"); 
            elif (self._IR == (0xdf<<3|2)): print("df 010"); 
            elif (self._IR == (0xdf<<3|3)): print("df 011"); 
            elif (self._IR == (0xdf<<3|4)): print("df 100"); 
            elif (self._IR == (0xdf<<3|5)): print("df 101"); 
            elif (self._IR == (0xdf<<3|6)): print("df 110"); 
            elif (self._IR == (0xdf<<3|7)): print("df 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # CPX-#                           
            elif (self._IR == (0xe0<<3|0)): print("e0 000"); 
            elif (self._IR == (0xe0<<3|1)): print("e0 001"); 
            elif (self._IR == (0xe0<<3|2)): print("e0 010"); 
            elif (self._IR == (0xe0<<3|3)): print("e0 011"); 
            elif (self._IR == (0xe0<<3|4)): print("e0 100"); 
            elif (self._IR == (0xe0<<3|5)): print("e0 101"); 
            elif (self._IR == (0xe0<<3|6)): print("e0 110"); 
            elif (self._IR == (0xe0<<3|7)): print("e0 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-(zp,x)                      
            elif (self._IR == (0xe1<<3|0)): print("e1 000"); 
            elif (self._IR == (0xe1<<3|1)): print("e1 001"); 
            elif (self._IR == (0xe1<<3|2)): print("e1 010"); 
            elif (self._IR == (0xe1<<3|3)): print("e1 011"); 
            elif (self._IR == (0xe1<<3|4)): print("e1 100"); 
            elif (self._IR == (0xe1<<3|5)): print("e1 101"); 
            elif (self._IR == (0xe1<<3|6)): print("e1 110"); 
            elif (self._IR == (0xe1<<3|7)): print("e1 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xe2<<3|0)): print("e2 000"); 
            elif (self._IR == (0xe2<<3|1)): print("e2 001"); 
            elif (self._IR == (0xe2<<3|2)): print("e2 010"); 
            elif (self._IR == (0xe2<<3|3)): print("e2 011"); 
            elif (self._IR == (0xe2<<3|4)): print("e2 100"); 
            elif (self._IR == (0xe2<<3|5)): print("e2 101"); 
            elif (self._IR == (0xe2<<3|6)): print("e2 110"); 
            elif (self._IR == (0xe2<<3|7)): print("e2 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xe3<<3|0)): print("e3 000"); 
            elif (self._IR == (0xe3<<3|1)): print("e3 001"); 
            elif (self._IR == (0xe3<<3|2)): print("e3 010"); 
            elif (self._IR == (0xe3<<3|3)): print("e3 011"); 
            elif (self._IR == (0xe3<<3|4)): print("e3 100"); 
            elif (self._IR == (0xe3<<3|5)): print("e3 101"); 
            elif (self._IR == (0xe3<<3|6)): print("e3 110"); 
            elif (self._IR == (0xe3<<3|7)): print("e3 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CPX-zp                          
            elif (self._IR == (0xe4<<3|0)): print("e4 000"); 
            elif (self._IR == (0xe4<<3|1)): print("e4 001"); 
            elif (self._IR == (0xe4<<3|2)): print("e4 010"); 
            elif (self._IR == (0xe4<<3|3)): print("e4 011"); 
            elif (self._IR == (0xe4<<3|4)): print("e4 100"); 
            elif (self._IR == (0xe4<<3|5)): print("e4 101"); 
            elif (self._IR == (0xe4<<3|6)): print("e4 110"); 
            elif (self._IR == (0xe4<<3|7)): print("e4 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-zp                          
            elif (self._IR == (0xe5<<3|0)): print("e5 000"); 
            elif (self._IR == (0xe5<<3|1)): print("e5 001"); 
            elif (self._IR == (0xe5<<3|2)): print("e5 010"); 
            elif (self._IR == (0xe5<<3|3)): print("e5 011"); 
            elif (self._IR == (0xe5<<3|4)): print("e5 100"); 
            elif (self._IR == (0xe5<<3|5)): print("e5 101"); 
            elif (self._IR == (0xe5<<3|6)): print("e5 110"); 
            elif (self._IR == (0xe5<<3|7)): print("e5 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INC-zp                          
            elif (self._IR == (0xe6<<3|0)): print("e6 000"); 
            elif (self._IR == (0xe6<<3|1)): print("e6 001"); 
            elif (self._IR == (0xe6<<3|2)): print("e6 010"); 
            elif (self._IR == (0xe6<<3|3)): print("e6 011"); 
            elif (self._IR == (0xe6<<3|4)): print("e6 100"); 
            elif (self._IR == (0xe6<<3|5)): print("e6 101"); 
            elif (self._IR == (0xe6<<3|6)): print("e6 110"); 
            elif (self._IR == (0xe6<<3|7)): print("e6 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB6-zp                         
            elif (self._IR == (0xe7<<3|0)): print("e7 000"); 
            elif (self._IR == (0xe7<<3|1)): print("e7 001"); 
            elif (self._IR == (0xe7<<3|2)): print("e7 010"); 
            elif (self._IR == (0xe7<<3|3)): print("e7 011"); 
            elif (self._IR == (0xe7<<3|4)): print("e7 100"); 
            elif (self._IR == (0xe7<<3|5)): print("e7 101"); 
            elif (self._IR == (0xe7<<3|6)): print("e7 110"); 
            elif (self._IR == (0xe7<<3|7)): print("e7 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INX-i                           
            elif (self._IR == (0xe8<<3|0)): print("e8 000"); 
            elif (self._IR == (0xe8<<3|1)): print("e8 001"); 
            elif (self._IR == (0xe8<<3|2)): print("e8 010"); 
            elif (self._IR == (0xe8<<3|3)): print("e8 011"); 
            elif (self._IR == (0xe8<<3|4)): print("e8 100"); 
            elif (self._IR == (0xe8<<3|5)): print("e8 101"); 
            elif (self._IR == (0xe8<<3|6)): print("e8 110"); 
            elif (self._IR == (0xe8<<3|7)): print("e8 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-#                           
            elif (self._IR == (0xe9<<3|0)): print("e9 000"); 
            elif (self._IR == (0xe9<<3|1)): print("e9 001"); 
            elif (self._IR == (0xe9<<3|2)): print("e9 010"); 
            elif (self._IR == (0xe9<<3|3)): print("e9 011"); 
            elif (self._IR == (0xe9<<3|4)): print("e9 100"); 
            elif (self._IR == (0xe9<<3|5)): print("e9 101"); 
            elif (self._IR == (0xe9<<3|6)): print("e9 110"); 
            elif (self._IR == (0xe9<<3|7)): print("e9 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # NOP-i                           
            elif (self._IR == (0xea<<3|0)): print("ea 000"); 
            elif (self._IR == (0xea<<3|1)): print("ea 001"); 
            elif (self._IR == (0xea<<3|2)): print("ea 010"); 
            elif (self._IR == (0xea<<3|3)): print("ea 011"); 
            elif (self._IR == (0xea<<3|4)): print("ea 100"); 
            elif (self._IR == (0xea<<3|5)): print("ea 101"); 
            elif (self._IR == (0xea<<3|6)): print("ea 110"); 
            elif (self._IR == (0xea<<3|7)): print("ea 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xeb<<3|0)): print("eb 000"); 
            elif (self._IR == (0xeb<<3|1)): print("eb 001"); 
            elif (self._IR == (0xeb<<3|2)): print("eb 010"); 
            elif (self._IR == (0xeb<<3|3)): print("eb 011"); 
            elif (self._IR == (0xeb<<3|4)): print("eb 100"); 
            elif (self._IR == (0xeb<<3|5)): print("eb 101"); 
            elif (self._IR == (0xeb<<3|6)): print("eb 110"); 
            elif (self._IR == (0xeb<<3|7)): print("eb 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # CPX-a                           
            elif (self._IR == (0xec<<3|0)): print("ec 000"); 
            elif (self._IR == (0xec<<3|1)): print("ec 001"); 
            elif (self._IR == (0xec<<3|2)): print("ec 010"); 
            elif (self._IR == (0xec<<3|3)): print("ec 011"); 
            elif (self._IR == (0xec<<3|4)): print("ec 100"); 
            elif (self._IR == (0xec<<3|5)): print("ec 101"); 
            elif (self._IR == (0xec<<3|6)): print("ec 110"); 
            elif (self._IR == (0xec<<3|7)): print("ec 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-a                           
            elif (self._IR == (0xed<<3|0)): print("ed 000"); 
            elif (self._IR == (0xed<<3|1)): print("ed 001"); 
            elif (self._IR == (0xed<<3|2)): print("ed 010"); 
            elif (self._IR == (0xed<<3|3)): print("ed 011"); 
            elif (self._IR == (0xed<<3|4)): print("ed 100"); 
            elif (self._IR == (0xed<<3|5)): print("ed 101"); 
            elif (self._IR == (0xed<<3|6)): print("ed 110"); 
            elif (self._IR == (0xed<<3|7)): print("ed 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INC-a                           
            elif (self._IR == (0xee<<3|0)): print("ee 000"); 
            elif (self._IR == (0xee<<3|1)): print("ee 001"); 
            elif (self._IR == (0xee<<3|2)): print("ee 010"); 
            elif (self._IR == (0xee<<3|3)): print("ee 011"); 
            elif (self._IR == (0xee<<3|4)): print("ee 100"); 
            elif (self._IR == (0xee<<3|5)): print("ee 101"); 
            elif (self._IR == (0xee<<3|6)): print("ee 110"); 
            elif (self._IR == (0xee<<3|7)): print("ee 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS6-r                          
            elif (self._IR == (0xef<<3|0)): print("ef 000"); 
            elif (self._IR == (0xef<<3|1)): print("ef 001"); 
            elif (self._IR == (0xef<<3|2)): print("ef 010"); 
            elif (self._IR == (0xef<<3|3)): print("ef 011"); 
            elif (self._IR == (0xef<<3|4)): print("ef 100"); 
            elif (self._IR == (0xef<<3|5)): print("ef 101"); 
            elif (self._IR == (0xef<<3|6)): print("ef 110"); 
            elif (self._IR == (0xef<<3|7)): print("ef 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
                                              
                                              
            # BEQ-r                           
            elif (self._IR == (0xf0<<3|0)): print("f0 000"); 
            elif (self._IR == (0xf0<<3|1)): print("f0 001"); 
            elif (self._IR == (0xf0<<3|2)): print("f0 010"); 
            elif (self._IR == (0xf0<<3|3)): print("f0 011"); 
            elif (self._IR == (0xf0<<3|4)): print("f0 100"); 
            elif (self._IR == (0xf0<<3|5)): print("f0 101"); 
            elif (self._IR == (0xf0<<3|6)): print("f0 110"); 
            elif (self._IR == (0xf0<<3|7)): print("f0 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-(zp),y                      
            elif (self._IR == (0xf1<<3|0)): print("f1 000"); 
            elif (self._IR == (0xf1<<3|1)): print("f1 001"); 
            elif (self._IR == (0xf1<<3|2)): print("f1 010"); 
            elif (self._IR == (0xf1<<3|3)): print("f1 011"); 
            elif (self._IR == (0xf1<<3|4)): print("f1 100"); 
            elif (self._IR == (0xf1<<3|5)): print("f1 101"); 
            elif (self._IR == (0xf1<<3|6)): print("f1 110"); 
            elif (self._IR == (0xf1<<3|7)): print("f1 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-(zp)                        
            elif (self._IR == (0xf2<<3|0)): print("f2 000"); 
            elif (self._IR == (0xf2<<3|1)): print("f2 001"); 
            elif (self._IR == (0xf2<<3|2)): print("f2 010"); 
            elif (self._IR == (0xf2<<3|3)): print("f2 011"); 
            elif (self._IR == (0xf2<<3|4)): print("f2 100"); 
            elif (self._IR == (0xf2<<3|5)): print("f2 101"); 
            elif (self._IR == (0xf2<<3|6)): print("f2 110"); 
            elif (self._IR == (0xf2<<3|7)): print("f2 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xf3<<3|0)): print("f3 000"); 
            elif (self._IR == (0xf3<<3|1)): print("f3 001"); 
            elif (self._IR == (0xf3<<3|2)): print("f3 010"); 
            elif (self._IR == (0xf3<<3|3)): print("f3 011"); 
            elif (self._IR == (0xf3<<3|4)): print("f3 100"); 
            elif (self._IR == (0xf3<<3|5)): print("f3 101"); 
            elif (self._IR == (0xf3<<3|6)): print("f3 110"); 
            elif (self._IR == (0xf3<<3|7)): print("f3 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xf4<<3|0)): print("f4 000"); 
            elif (self._IR == (0xf4<<3|1)): print("f4 001"); 
            elif (self._IR == (0xf4<<3|2)): print("f4 010"); 
            elif (self._IR == (0xf4<<3|3)): print("f4 011"); 
            elif (self._IR == (0xf4<<3|4)): print("f4 100"); 
            elif (self._IR == (0xf4<<3|5)): print("f4 101"); 
            elif (self._IR == (0xf4<<3|6)): print("f4 110"); 
            elif (self._IR == (0xf4<<3|7)): print("f4 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-zp,x                        
            elif (self._IR == (0xf5<<3|0)): print("f5 000"); 
            elif (self._IR == (0xf5<<3|1)): print("f5 001"); 
            elif (self._IR == (0xf5<<3|2)): print("f5 010"); 
            elif (self._IR == (0xf5<<3|3)): print("f5 011"); 
            elif (self._IR == (0xf5<<3|4)): print("f5 100"); 
            elif (self._IR == (0xf5<<3|5)): print("f5 101"); 
            elif (self._IR == (0xf5<<3|6)): print("f5 110"); 
            elif (self._IR == (0xf5<<3|7)): print("f5 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INC-zp,x                        
            elif (self._IR == (0xf6<<3|0)): print("f6 000"); 
            elif (self._IR == (0xf6<<3|1)): print("f6 001"); 
            elif (self._IR == (0xf6<<3|2)): print("f6 010"); 
            elif (self._IR == (0xf6<<3|3)): print("f6 011"); 
            elif (self._IR == (0xf6<<3|4)): print("f6 100"); 
            elif (self._IR == (0xf6<<3|5)): print("f6 101"); 
            elif (self._IR == (0xf6<<3|6)): print("f6 110"); 
            elif (self._IR == (0xf6<<3|7)): print("f6 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SMB7-zp                         
            elif (self._IR == (0xf7<<3|0)): print("f7 000"); 
            elif (self._IR == (0xf7<<3|1)): print("f7 001"); 
            elif (self._IR == (0xf7<<3|2)): print("f7 010"); 
            elif (self._IR == (0xf7<<3|3)): print("f7 011"); 
            elif (self._IR == (0xf7<<3|4)): print("f7 100"); 
            elif (self._IR == (0xf7<<3|5)): print("f7 101"); 
            elif (self._IR == (0xf7<<3|6)): print("f7 110"); 
            elif (self._IR == (0xf7<<3|7)): print("f7 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SED-i                           
            elif (self._IR == (0xf8<<3|0)): print("f8 000"); 
            elif (self._IR == (0xf8<<3|1)): print("f8 001"); 
            elif (self._IR == (0xf8<<3|2)): print("f8 010"); 
            elif (self._IR == (0xf8<<3|3)): print("f8 011"); 
            elif (self._IR == (0xf8<<3|4)): print("f8 100"); 
            elif (self._IR == (0xf8<<3|5)): print("f8 101"); 
            elif (self._IR == (0xf8<<3|6)): print("f8 110"); 
            elif (self._IR == (0xf8<<3|7)): print("f8 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-a,y                         
            elif (self._IR == (0xf9<<3|0)): print("f9 000"); 
            elif (self._IR == (0xf9<<3|1)): print("f9 001"); 
            elif (self._IR == (0xf9<<3|2)): print("f9 010"); 
            elif (self._IR == (0xf9<<3|3)): print("f9 011"); 
            elif (self._IR == (0xf9<<3|4)): print("f9 100"); 
            elif (self._IR == (0xf9<<3|5)): print("f9 101"); 
            elif (self._IR == (0xf9<<3|6)): print("f9 110"); 
            elif (self._IR == (0xf9<<3|7)): print("f9 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # PLX-s                           
            elif (self._IR == (0xfa<<3|0)): print("fa 000"); 
            elif (self._IR == (0xfa<<3|1)): print("fa 001"); 
            elif (self._IR == (0xfa<<3|2)): print("fa 010"); 
            elif (self._IR == (0xfa<<3|3)): print("fa 011"); 
            elif (self._IR == (0xfa<<3|4)): print("fa 100"); 
            elif (self._IR == (0xfa<<3|5)): print("fa 101"); 
            elif (self._IR == (0xfa<<3|6)): print("fa 110"); 
            elif (self._IR == (0xfa<<3|7)): print("fa 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xfb<<3|0)): print("fb 000"); 
            elif (self._IR == (0xfb<<3|1)): print("fb 001"); 
            elif (self._IR == (0xfb<<3|2)): print("fb 010"); 
            elif (self._IR == (0xfb<<3|3)): print("fb 011"); 
            elif (self._IR == (0xfb<<3|4)): print("fb 100"); 
            elif (self._IR == (0xfb<<3|5)): print("fb 101"); 
            elif (self._IR == (0xfb<<3|6)): print("fb 110"); 
            elif (self._IR == (0xfb<<3|7)): print("fb 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # None                            
            elif (self._IR == (0xfc<<3|0)): print("fc 000"); 
            elif (self._IR == (0xfc<<3|1)): print("fc 001"); 
            elif (self._IR == (0xfc<<3|2)): print("fc 010"); 
            elif (self._IR == (0xfc<<3|3)): print("fc 011"); 
            elif (self._IR == (0xfc<<3|4)): print("fc 100"); 
            elif (self._IR == (0xfc<<3|5)): print("fc 101"); 
            elif (self._IR == (0xfc<<3|6)): print("fc 110"); 
            elif (self._IR == (0xfc<<3|7)): print("fc 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # SBC-a,x                         
            elif (self._IR == (0xfd<<3|0)): print("fd 000"); 
            elif (self._IR == (0xfd<<3|1)): print("fd 001"); 
            elif (self._IR == (0xfd<<3|2)): print("fd 010"); 
            elif (self._IR == (0xfd<<3|3)): print("fd 011"); 
            elif (self._IR == (0xfd<<3|4)): print("fd 100"); 
            elif (self._IR == (0xfd<<3|5)): print("fd 101"); 
            elif (self._IR == (0xfd<<3|6)): print("fd 110"); 
            elif (self._IR == (0xfd<<3|7)): print("fd 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # INC-a,x                         
            elif (self._IR == (0xfe<<3|0)): print("fe 000"); 
            elif (self._IR == (0xfe<<3|1)): print("fe 001"); 
            elif (self._IR == (0xfe<<3|2)): print("fe 010"); 
            elif (self._IR == (0xfe<<3|3)): print("fe 011"); 
            elif (self._IR == (0xfe<<3|4)): print("fe 100"); 
            elif (self._IR == (0xfe<<3|5)): print("fe 101"); 
            elif (self._IR == (0xfe<<3|6)): print("fe 110"); 
            elif (self._IR == (0xfe<<3|7)): print("fe 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)
                                              
            # BBS7-r                          
            elif (self._IR == (0xff<<3|0)): print("ff 000"); 
            elif (self._IR == (0xff<<3|1)): print("ff 001"); 
            elif (self._IR == (0xff<<3|2)): print("ff 010"); 
            elif (self._IR == (0xff<<3|3)): print("ff 011"); 
            elif (self._IR == (0xff<<3|4)): print("ff 100"); 
            elif (self._IR == (0xff<<3|5)): print("ff 101"); 
            elif (self._IR == (0xff<<3|6)): print("ff 110"); 
            elif (self._IR == (0xff<<3|7)): print("ff 111"); print("FETCH"); pins = M65C02._FETCH(pins, self)

            self._IR += 1

        self._PINS = pins
        return pins


if __name__ == "__main__":
    pins = 0b0000000000000000000000000000000000000000
    pins |= (M65C02_VCC|M65C02_RDY|M65C02_IRQB|M65C02_NMIB|M65C02_BE|M65C02_RESB)
    cpu = M65C02(pins)

    addr = 0xaa5a
    print(f"pins before _SA({to_bin(addr, 16)}):", to_bin(pins, 40))
    pins = M65C02._SA(pins, addr)
    print(f"pins after  _SA({to_bin(addr, 16)}):", to_bin(pins, 40))
    print(f"addr from _GA():{to_bin(M65C02._GA(pins), 16)}")
    print()

    pins = M65C02._SA(pins, 0x0000)

    data = 0xff
    print(f"pins before _SD({to_bin(data, 8)}):", to_bin(pins, 40))
    pins = M65C02._SD(pins, data)
    print(f"pins after  _SD({to_bin(data, 8)}):", to_bin(pins, 40))
    print(f"addr from _GD():{to_bin(M65C02._GD(pins), 8)}")
    print()

    pins = 0
    pins = M65C02._ON(pins, M65C02_RESB)
    print(f"pins after  on RESB:", to_bin(pins, 40))
    pins = ((1<<40)-1)
    pins = M65C02._OFF(pins, M65C02_RESB)
    print(f"pins after off RESB:", to_bin(pins, 40))
    print()

    pins = 0
    pins = M65C02._RD(pins)
    print(f"pins after _RD:", to_bin(pins, 40))
    pins = ((1<<40)-1)
    pins = M65C02._WR(pins)
    print(f"pins after _WR:", to_bin(pins, 40))
    print()

    print("_NZ tests:")
    print(to_bin(cpu._P, 8))
    M65C02._NZ(cpu, 0x10)
    print(to_bin(cpu._P, 8))
    M65C02._NZ(cpu, 0x00)
    print(to_bin(cpu._P, 8))
    M65C02._NZ(cpu, 0x80)
    print(to_bin(cpu._P, 8))
    M65C02._NZ(cpu, 0x05)
    print(to_bin(cpu._P, 8))
    print()

    print("_FETCH tests:")
    pins = 0
    cpu._PC = 0xaf05
    pins = M65C02._FETCH(pins, cpu)
    print(f"pins:", to_bin(pins, 40))
    print()

    print("_SAD tests:")
    pins = 0
    pins = M65C02._SAD(pins, 0x8001, 0x81)
    print(f"pins:", to_bin(pins, 40))
    print()



