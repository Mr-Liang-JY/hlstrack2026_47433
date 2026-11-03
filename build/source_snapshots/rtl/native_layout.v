`timescale 1ns/1ps
// Pixel address generator. UI is native 720p: two 128x128 images enlarged 4x,
// ASCII glyphs and plots come from a compact per-frame packet, not a full UI bitmap.
module native_layout(input wire [10:0] x,input wire [9:0] y,input wire de,
 output reg [13:0] address,output reg [2:0] kind,output reg [1:0] lane,
 output reg [3:0] glyph_row,output reg [2:0] glyph_bit,
 output reg [4:0] plot_y,output reg [7:0] foreground);
 integer offset,rx,ry,col,line_index;
 always @* begin
  address=0;kind=0;lane=0;glyph_row=0;glyph_bit=0;plot_y=0;foreground=10;
  offset=0;rx=0;ry=0;col=0;line_index=0;
  if(de) begin
   // A constant kind avoids unnecessary RAM accesses for background/borders.
   if((x==1090 || x==1260) && y>=94 && y<=660)foreground=45;
   if((y==94 || y==660) && x>=1090 && x<=1260)foreground=45;
   if(y>=130 && y<642 && x>=24 && x<536)begin
    kind=1;address=(((y-130)>>2)*32)+((x-24)>>4);lane=((x-24)>>2)&3;
   end else if(y>=130 && y<642 && x>=556 && x<1068)begin
    kind=1;address=4096+(((y-130)>>2)*32)+((x-556)>>4);lane=((x-556)>>2)&3;
   end else if(y>=12 && y<36 && x>=24 && x<1048)begin
    kind=2;rx=x-24;ry=y-12;offset=(rx>>4);foreground=205;
   end else if(y>=55 && y<79 && x>=24 && x<1272)begin
    kind=2;rx=x-24;ry=y-55;offset=64+(rx>>4);foreground=135;
   end else if(y>=94 && y<118 && x>=24 && x<536)begin
    kind=2;rx=x-24;ry=y-94;offset=144+(rx>>4);foreground=180;
   end else if(y>=94 && y<118 && x>=556 && x<1068)begin
    kind=2;rx=x-556;ry=y-94;offset=176+(rx>>4);foreground=180;
   end else if(y>=104 && y<552 && x>=1092 && x<1252)begin
    kind=2;rx=x-1092;ry=(y-104)&31;line_index=(y-104)>>5;
    offset=208+line_index*10+(rx>>4);foreground=185;
   end else if(y>=550 && y<574 && x>=1092 && x<1252)begin
    kind=2;rx=x-1092;ry=y-550;offset=348+(rx>>4);foreground=150;
   end else if(y>=606 && y<630 && x>=1092 && x<1252)begin
    kind=2;rx=x-1092;ry=y-606;offset=364+(rx>>4);foreground=150;
   end else if(y>=680 && y<704 && x>=24 && x<1272)begin
    kind=2;rx=x-24;ry=y-680;offset=380+(rx>>4);foreground=115;
   end else if(y>=578 && y<=602 && x>=1102 && x<1230)begin
    kind=3;offset=512+2*(x-1102);plot_y=y-578;foreground=185;
   end else if(y>=634 && y<=658 && x>=1102 && x<1230)begin
    kind=4;offset=768+(x-1102);plot_y=y-634;foreground=165;
   end
   if(kind==2)begin
    address=8192+(offset>>2);lane=offset&3;glyph_row=ry>>1;glyph_bit=(rx>>1)&7;
   end else if(kind>=3)begin address=8192+(offset>>2);lane=offset&3;end
  end
 end
endmodule
