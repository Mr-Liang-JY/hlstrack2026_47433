`timescale 1ns/1ps
// 640x480, 60.000 Hz with a 25.200 MHz pixel clock.
// h: active 640, front porch 16, sync 96, back porch 48 = 800.
// v: active 480, front porch 10, sync 2, back porch 33 = 525.
module video_timing(
    input wire pixel_clk, input wire rst,
    output reg [9:0] x, output reg [9:0] y,
    output wire de, output wire hsync, output wire vsync,
    output wire frame_end
);
    always @(posedge pixel_clk) begin
        if (rst) begin x <= 0; y <= 0; end
        else if (x == 799) begin
            x <= 0;
            if (y == 524) y <= 0;
            else y <= y + 1'b1;
        end else x <= x + 1'b1;
    end
    assign de = (x < 640) && (y < 480);
    assign hsync = !((x >= 656) && (x < 752));
    assign vsync = !((y >= 490) && (y < 492));
    assign frame_end = (x == 799) && (y == 524);
endmodule
