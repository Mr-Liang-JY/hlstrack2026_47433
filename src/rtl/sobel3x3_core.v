`timescale 1ns/1ps
// Day9 pipelined derivative of the user's day8 L1 Sobel core.
// Four arithmetic stages, one patch/cycle throughput; no video line buffers.
module sobel3x3_core (
 input wire clk, input wire rst_n, input wire in_valid,
 input wire [7:0] p00,p01,p02,p10,p11,p12,p20,p21,p22,
 input wire [7:0] threshold,
 output reg out_valid, output reg [10:0] magnitude, output reg edge_bit
);
 reg v1,v2,v3;
 reg [9:0] right_sum,left_sum,bottom_sum,top_sum;
 reg signed [10:0] gx,gy;
 reg [10:0] total;
 reg [7:0] threshold1,threshold2,threshold3;
 wire [10:0] abs_gx = gx[10] ? -gx : gx;
 wire [10:0] abs_gy = gy[10] ? -gy : gy;
 always @(posedge clk) begin
   if (!rst_n) begin
     v1<=0;v2<=0;v3<=0;out_valid<=0;magnitude<=0;edge_bit<=0;
     right_sum<=0;left_sum<=0;bottom_sum<=0;top_sum<=0;
     gx<=0;gy<=0;total<=0;threshold1<=0;threshold2<=0;threshold3<=0;
   end
   else begin
     v1<=in_valid;v2<=v1;v3<=v2;out_valid<=v3;
     if (in_valid) begin
       right_sum<={2'b0,p02}+{1'b0,p12,1'b0}+{2'b0,p22};
       left_sum<={2'b0,p00}+{1'b0,p10,1'b0}+{2'b0,p20};
       bottom_sum<={2'b0,p20}+{1'b0,p21,1'b0}+{2'b0,p22};
       top_sum<={2'b0,p00}+{1'b0,p01,1'b0}+{2'b0,p02};
       threshold1<=threshold;
     end
     if(v1) begin
       gx<=$signed({1'b0,right_sum})-$signed({1'b0,left_sum});
       gy<=$signed({1'b0,bottom_sum})-$signed({1'b0,top_sum});
       threshold2<=threshold1;
     end
     if(v2) begin total<=abs_gx+abs_gy;threshold3<=threshold2;end
     if(v3) begin
       magnitude<=total;
       // For an 8-bit threshold, raw>=T is identical to min(raw,255)>=T.
       edge_bit <= (total >= {3'd0,threshold3});
     end
   end
 end
endmodule
