BLACK        := $(shell tput -Txterm setaf 0)
RED          := $(shell tput -Txterm setaf 1)
GREEN        := $(shell tput -Txterm setaf 2)
YELLOW       := $(shell tput -Txterm setaf 3)
LIGHTPURPLE  := $(shell tput -Txterm setaf 4)
PURPLE       := $(shell tput -Txterm setaf 5)
BLUE         := $(shell tput -Txterm setaf 6)
WHITE        := $(shell tput -Txterm setaf 7)
RESET        := $(shell tput -Txterm sgr0)

##################
## PARAMETERS ####
##################
ASM      = ~/Documents/vasm/vasm/vasm6502_oldstyle
ASMFLAGS = -Fbin -dotdir -c02
WRITER   = minipro
DEVICE   = AT28C256

SRC = ""
OBJ_DIR = bin
OBJ = a.out

##################
## Makers ########
##################
# assemble, dump and write.
all: assemble hexdump write

# assemble.
assemble:
	@echo "$(LIGHTPURPLE)$(ASM) $(ASMFLAGS) $(SRC) -o $(OBJ_DIR)/$(OBJ)$(RESET)"
	@$(ASM) $(ASMFLAGS) $(SRC) -o $(OBJ_DIR)/$(OBJ)

# dump the content of the object file.
hexdump:
	@echo "$(LIGHTPURPLE)hexdump -C $(OBJ_DIR)/$(OBJ)$(RESET)"
	@hexdump -C $(OBJ_DIR)/$(OBJ)

# write to the eePROM.
write:
	@echo "$(LIGHTPURPLE)$(WRITER) -p $(DEVICE) -w $(OBJ_DIR)/$(OBJ)$(RESET)"
	@$(WRITER) -p $(DEVICE) -w $(OBJ_DIR)/$(OBJ)
