`timescale 1ns/1ps
// Monotonic binary counters only. Register Gray code before crossing domains.
module cdc_counter(input wire src_clk,input wire src_rst,input wire [31:0] src_count,
    input wire dst_clk,input wire dst_rst,output reg [31:0] dst_count);
    reg [31:0] src_gray;
    (* ASYNC_REG="TRUE" *) reg [31:0] gray_meta,gray_sync;
    integer k;
    always @(posedge src_clk or posedge src_rst)
        if(src_rst) src_gray<=0;
        else src_gray<=(src_count>>1)^src_count;
    always @(posedge dst_clk or posedge dst_rst)
        if(dst_rst) begin gray_meta<=0;gray_sync<=0;end
        else begin gray_meta<=src_gray;gray_sync<=gray_meta;end
    always @* begin
        dst_count[31]=gray_sync[31];
        for(k=30;k>=0;k=k-1) dst_count[k]=dst_count[k+1]^gray_sync[k];
    end
endmodule
