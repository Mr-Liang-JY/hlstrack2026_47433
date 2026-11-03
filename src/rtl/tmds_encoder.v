`timescale 1ns/1ps
// DVI TMDS: 8 data bits -> 10 channel bits, with running DC balance.
// The BLUE channel carries {vsync, hsync} during blanking.
module tmds_encoder(
    input wire pixel_clk, input wire rst,
    input wire [7:0] data, input wire de,
    input wire c0, input wire c1,
    output reg [9:0] symbol
);
    integer i, ones_data, ones_qm;
    reg use_xnor;
    reg [8:0] qm;
    integer balance;
    reg signed [5:0] disparity;
    always @* begin
        ones_data = 0;
        for (i = 0; i < 8; i = i + 1) ones_data = ones_data + data[i];
        use_xnor = (ones_data > 4) || ((ones_data == 4) && !data[0]);
        qm[0] = data[0];
        for (i = 1; i < 8; i = i + 1)
            if (use_xnor) qm[i] = ~(qm[i-1] ^ data[i]);
            else          qm[i] = qm[i-1] ^ data[i];
        qm[8] = !use_xnor;
        ones_qm = 0;
        for (i = 0; i < 8; i = i + 1) ones_qm = ones_qm + qm[i];
        balance = 2 * ones_qm - 8;
    end
    always @(posedge pixel_clk) begin
        if (rst) begin symbol <= 10'b1101010100; disparity <= 0; end
        else if (!de) begin
            disparity <= 0;
            case ({c1,c0})
                2'b00: symbol <= 10'b1101010100;
                2'b01: symbol <= 10'b0010101011;
                2'b10: symbol <= 10'b0101010100;
                2'b11: symbol <= 10'b1010101011;
            endcase
        end else if ((disparity == 0) || (balance == 0)) begin
            symbol <= {~qm[8], qm[8], qm[8] ? qm[7:0] : ~qm[7:0]};
            if (qm[8]) disparity <= disparity + balance;
            else       disparity <= disparity - balance;
        end else if (((disparity > 0) && (balance > 0)) ||
                     ((disparity < 0) && (balance < 0))) begin
            symbol <= {1'b1, qm[8], ~qm[7:0]};
            disparity <= disparity - balance + (qm[8] ? 2 : 0);
        end else begin
            symbol <= {1'b0, qm[8], qm[7:0]};
            disparity <= disparity + balance - (qm[8] ? 0 : 2);
        end
    end
endmodule
