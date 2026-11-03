`timescale 1ns/1ps
module test_pattern(
    input wire pixel_clk, input wire rst, input wire frame_end,
    input wire [9:0] x, input wire [9:0] y, input wire de,
    output reg [23:0] rgb, output wire heartbeat
);
    reg [9:0] box_x, box_y;
    reg direction_x, direction_y;
    reg [5:0] frame_count;
    always @(posedge pixel_clk) begin
        if (rst) begin
            box_x <= 32; box_y <= 64;
            direction_x <= 1; direction_y <= 1; frame_count <= 0;
        end else if (frame_end) begin
            frame_count <= frame_count + 1'b1;
            if (direction_x) begin
                if (box_x >= 576) begin direction_x <= 0; box_x <= 574; end
                else box_x <= box_x + 2;
            end else begin
                if (box_x <= 32) begin direction_x <= 1; box_x <= 34; end
                else box_x <= box_x - 2;
            end
            if (direction_y) begin
                if (box_y >= 416) begin direction_y <= 0; box_y <= 415; end
                else box_y <= box_y + 1'b1;
            end else begin
                if (box_y <= 32) begin direction_y <= 1; box_y <= 33; end
                else box_y <= box_y - 1'b1;
            end
        end
    end
    assign heartbeat = frame_count[5];
    always @* begin
        rgb = 24'h000000;
        if (de) begin
            if      (x < 80)  rgb = 24'hffffff; // white
            else if (x < 160) rgb = 24'hffff00; // yellow
            else if (x < 240) rgb = 24'h00ffff; // cyan
            else if (x < 320) rgb = 24'h00ff00; // green
            else if (x < 400) rgb = 24'hff00ff; // magenta
            else if (x < 480) rgb = 24'hff0000; // red
            else if (x < 560) rgb = 24'h0000ff; // blue
            else             rgb = 24'h000000; // black
            if (x >= box_x && x < box_x + 32 && y >= box_y && y < box_y + 32) begin
                if (x < box_x + 2 || x >= box_x + 30 ||
                    y < box_y + 2 || y >= box_y + 30) rgb = 24'h000000;
                else rgb = 24'hffffff;
            end
            // A two-pixel border exposes cropping/overscan at all four sides.
            if (x < 2 || x >= 638 || y < 2 || y >= 478) rgb = 24'hffffff;
        end
    end
endmodule
