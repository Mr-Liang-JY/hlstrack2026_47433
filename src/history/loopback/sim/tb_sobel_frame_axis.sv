`timescale 1ns/1ps
module tb_sobel_frame_axis;
reg clk=0;always #5 clk=~clk;
reg resetn=0;reg[31:0]ps_control=0,roi_config=0;
wire[31:0]pl_status,roi_edge_count,roi_edge_y_sum;
reg[31:0]s_axis_tdata=0;reg[3:0]s_axis_tkeep=15;
reg s_axis_tlast=0,s_axis_tvalid=0;wire s_axis_tready;
wire[31:0]m_axis_tdata;wire[3:0]m_axis_tkeep;
wire m_axis_tlast,m_axis_tvalid;reg m_axis_tready=0;
sobel_frame_axis dut(.*);
integer sent=0,received=0,cycles=0;
reg stalled=0;reg[31:0]held;reg held_last;
always @(posedge clk)begin
 cycles=cycles+1;
 if(stalled && (!m_axis_tvalid || m_axis_tdata!==held || m_axis_tlast!==held_last))$fatal(1,"Unstable AXIS under backpressure");
 stalled=m_axis_tvalid&&!m_axis_tready;held=m_axis_tdata;held_last=m_axis_tlast;
end
initial begin
 repeat(5)@(negedge clk);resetn=1;
 fork
 begin
 while(sent<4096)begin
 @(negedge clk);s_axis_tvalid=1;s_axis_tdata=sent*32'h10204081;s_axis_tlast=(sent==4095);
 @(posedge clk);
 while(!s_axis_tready)@(posedge clk);
 sent=sent+1;
 @(negedge clk);s_axis_tvalid=0;
 end
 end
 begin
 while(received<4096)begin
 @(negedge clk);m_axis_tready=(cycles%7!=2 && cycles%11!=4);
 @(posedge clk);
 if(m_axis_tvalid&&m_axis_tready)begin
 if(m_axis_tdata!==(received*32'h10204081) || m_axis_tkeep!==15 || m_axis_tlast!==(received==4095))$fatal(1,"Loopback mismatch at %0d",received);
 received=received+1;
 end
 end
 end
 join
 $display("LOOPBACK RTL SIMULATION PASSED (4096 uint32 words; backpressure and TLAST)");$finish;
end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
