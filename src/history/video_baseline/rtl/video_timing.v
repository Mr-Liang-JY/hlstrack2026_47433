`timescale 1ns/1ps
// CEA 720p60: 74.25 MHz / (1650 * 750) = 60 Hz, positive H/V sync.
module video_timing(
    input wire pixel_clk, input wire rst,
    output reg [10:0] x, output reg [9:0] y,
    output wire de, output wire hsync, output wire vsync,
    output wire frame_end
);
    always @(posedge pixel_clk) begin
        if (rst) begin x<=0; y<=0; end
        else if (x==1649) begin
            x<=0;
            if(y==749) y<=0; else y<=y+1'b1;
        end else x<=x+1'b1;
    end
    assign de=x<1280 && y<720;
    assign hsync=x>=1390 && x<1430;
    assign vsync=y>=725 && y<730;
    assign frame_end=x==1649 && y==749;
endmodule
