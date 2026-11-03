`timescale 1ns/1ps
module cdc_bit(input wire clk, input wire arst, input wire din, output wire dout);
    (* ASYNC_REG="TRUE" *) reg cdc_meta, cdc_sync;
    always @(posedge clk or posedge arst)
        if(arst) begin cdc_meta<=0; cdc_sync<=0; end
        else begin cdc_meta<=din; cdc_sync<=cdc_meta; end
    assign dout=cdc_sync;
endmodule
