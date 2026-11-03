from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
font=ImageFont.truetype(str(ROOT/'data/DejaVuSans.ttf'),12)
rom=np.zeros((128,16),np.uint8)
for code in range(32,127):
    image=Image.new('L',(8,12));ImageDraw.Draw(image).text((0,-2),chr(code),font=font,fill=255)
    bits=np.asarray(image)>=85
    for row in range(12):rom[code,row]=sum(int(bits[row,x])<<(7-x) for x in range(8))
np.save(ROOT/'data/font_bitmap.npy',rom)
lines=['`timescale 1ns/1ps','module font_rom(input wire [6:0] code,input wire [3:0] row,output reg [7:0] bits);','always @* begin','case({code,row})']
for code in range(32,127):
    for row in range(12):
        if rom[code,row]:lines.append("11'd%d: bits=8'h%02x;"%(code*16+row,int(rom[code,row])))
lines += ["default:bits=0;","endcase","end","endmodule"]
(ROOT/'rtl/font_rom.v').write_text('\n'.join(lines)+'\n',encoding='ascii')
print('Font ROM generated:',int(np.count_nonzero(rom)),'nonzero rows')
