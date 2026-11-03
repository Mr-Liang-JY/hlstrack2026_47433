`timescale 1ns/1ps
// 126 MHz DDR transmits 10 bits per 25.2 MHz pixel, least-significant first.
// MASTER consumes bits 0..7; SLAVE extends the word with bits 8..9.
module serializer_10to1(
    input wire pixel_clk, input wire serial_clk, input wire rst,
    input wire [9:0] word, output wire serial_out
);
    wire shift1, shift2;
    OSERDESE2 #(
        .DATA_RATE_OQ("DDR"), .DATA_RATE_TQ("SDR"), .DATA_WIDTH(10),
        .SERDES_MODE("MASTER"), .TRISTATE_WIDTH(1),
        .TBYTE_CTL("FALSE"), .TBYTE_SRC("FALSE"), .INIT_OQ(1'b0), .SRVAL_OQ(1'b0)
    ) master (
        .CLK(serial_clk), .CLKDIV(pixel_clk), .RST(rst), .OCE(1'b1),
        .D1(word[0]), .D2(word[1]), .D3(word[2]), .D4(word[3]),
        .D5(word[4]), .D6(word[5]), .D7(word[6]), .D8(word[7]),
        .SHIFTIN1(shift1), .SHIFTIN2(shift2), .OQ(serial_out),
        .SHIFTOUT1(), .SHIFTOUT2(), .OFB(), .TFB(), .TQ(), .TBYTEOUT(),
        .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0),
        .TBYTEIN(1'b0), .TCE(1'b0)
    );
    OSERDESE2 #(
        .DATA_RATE_OQ("DDR"), .DATA_RATE_TQ("SDR"), .DATA_WIDTH(10),
        .SERDES_MODE("SLAVE"), .TRISTATE_WIDTH(1),
        .TBYTE_CTL("FALSE"), .TBYTE_SRC("FALSE"), .INIT_OQ(1'b0), .SRVAL_OQ(1'b0)
    ) slave (
        .CLK(serial_clk), .CLKDIV(pixel_clk), .RST(rst), .OCE(1'b1),
        .D1(1'b0), .D2(1'b0), .D3(word[8]), .D4(word[9]),
        .D5(1'b0), .D6(1'b0), .D7(1'b0), .D8(1'b0),
        .SHIFTIN1(1'b0), .SHIFTIN2(1'b0), .SHIFTOUT1(shift1), .SHIFTOUT2(shift2),
        .OQ(), .OFB(), .TFB(), .TQ(), .TBYTEOUT(),
        .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0),
        .TBYTEIN(1'b0), .TCE(1'b0)
    );
endmodule
