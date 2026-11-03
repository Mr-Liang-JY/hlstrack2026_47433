`timescale 1ns/1ps
module tb_video_display;
 reg ref_clk=0,pixel_clk=0,serial_clk=0;
 always #5 ref_clk=~ref_clk;always #6.734 pixel_clk=~pixel_clk;
 // SERDES word/bit behavior is checked independently by tb_serializer.
 reg resetn=0,locked=0,button_reset=0,hdmi_hpd_n=0;
 reg [31:0] control=1,s_axis_tdata=0;reg [3:0] s_axis_tkeep=15;
 reg s_axis_tvalid=0,s_axis_tlast=0;wire s_axis_tready;
 wire [31:0] status;wire [3:0] leds;wire hdmi_clk_p,hdmi_clk_n;
 wire [2:0] hdmi_data_p,hdmi_data_n;
 video_display dut(.*);
 reg [31:0] packet[0:8447];reg [7:0] golden[0:921599];
 integer i,checked=0,previous0=0,previous1=0,current;
 reg de0=0,de1=0,hs0=0,hs1=0,vs0=0,vs1=0,have0=0,have1=0;
 reg now_de,now_hs,now_vs,now_have;
 always @(posedge pixel_clk)begin
  current=(dut.x<1280 && dut.y<720) ? dut.y*1280+dut.x : 0;
  now_de=dut.de;now_hs=dut.hs;now_vs=dut.vs;now_have=dut.have_frame;
  #0.1;
  if(!dut.rst && have1)begin
   if(dut.de_out!==de1 || dut.hs_out!==hs1 || dut.vs_out!==vs1)$fatal(1,"native control alignment");
   if(dut.de_out)begin
    if(dut.gray_pixel!==golden[previous1])$fatal(1,"native pixel %d got=%d expected=%d",previous1,dut.gray_pixel,golden[previous1]);
    checked=checked+1;
   end
  end
  previous1=previous0;previous0=current;de1=de0;de0=now_de;hs1=hs0;hs0=now_hs;
  vs1=vs0;vs0=now_vs;have1=have0;have0=now_have;
  if(checked==921600)begin
   $display("PASS native compositor: 921600 pixels; image scales, ASCII glyphs, ROI, plots, pipeline alignment");$finish;
  end
 end
 initial begin
  $readmemh("native_packet.mem",packet);$readmemh("native_golden.mem",golden);
  repeat(5)@(negedge ref_clk);resetn=1;locked=1;
  repeat(10)@(negedge ref_clk);
  for(i=0;i<8448;i=i+1)begin
   @(negedge ref_clk);s_axis_tdata=packet[i];s_axis_tvalid=1;s_axis_tlast=i==8447;
   @(posedge ref_clk);while(!s_axis_tready)@(posedge ref_clk);
  end
  @(negedge ref_clk);s_axis_tvalid=0;s_axis_tlast=0;
 end
 initial begin #50000000;$fatal(1,"native display timeout");end
endmodule
