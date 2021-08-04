  .org $8000

reset:

loop:
  jmp loop


  .org $fffc
  .word reset
  .word $00
