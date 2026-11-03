`timescale 1ns/1ps
module tb_video_display;
    reg ref_clk=0,pixel_clk=0,serial_clk=0;
    always #5 ref_clk=~ref_clk;
    always #6.734 pixel_clk=~pixel_clk;
    // This test checks the framebuffer-to-encoder pixel pipeline. Keep the
    // high-speed clock stopped: serializer bit order is independently tested
    // in tb_serializer, avoiding tens of millions of unrelated SERDES events.
    reg resetn=0,locked=0,button_reset=0,hdmi_hpd_n=0;
    reg [31:0] control=1,s_axis_tdata=0;reg [3:0] s_axis_tkeep=15;
    reg s_axis_tvalid=0,s_axis_tlast=0;wire s_axis_tready;
    wire [31:0] status;wire [3:0] leds;
    wire hdmi_clk_p,hdmi_clk_n;wire [2:0] hdmi_data_p,hdmi_data_n;
    video_display dut(.*);
    integer i,col,row,checked=0,previous_value=0;
    reg previous_de=0,previous_hs=0,previous_vs=0,previous_have=0;
    integer now_value;reg now_de,now_hs,now_vs,now_have;
    always @(posedge pixel_clk) begin
        now_value=((dut.x>>1)+(dut.y>>1))&255;
        now_de=dut.de;now_hs=dut.hs;now_vs=dut.vs;now_have=dut.have_frame;
        #0.1;
        if(!dut.rst && previous_have && dut.de_q) begin
            if(!previous_de || dut.gray_pixel!==previous_value[7:0])
                $fatal(1,"pixel alignment mismatch got=%d expected=%d",dut.gray_pixel,previous_value);
            checked=checked+1;
        end
        if(!dut.rst && previous_have && (dut.de_q!==previous_de || dut.hs_q!==previous_hs || dut.vs_q!==previous_vs))
            $fatal(1,"control pipeline alignment mismatch");
        previous_value=now_value;previous_de=now_de;previous_hs=now_hs;previous_vs=now_vs;previous_have=now_have;
        if(checked==1280*720) begin
            $display("PASS display pipeline: 921600 pixel values, byte order, 2x scaling, DE/HS/VS alignment");$finish;
        end
    end
    initial begin
        repeat(5) @(negedge ref_clk);resetn=1;locked=1;
        repeat(10) @(negedge ref_clk);
        for(i=0;i<57600;i=i+1) begin
            row=i/160;col=(i%160)*4;
            @(negedge ref_clk);
            s_axis_tdata=((row+col)&255)|(((row+col+1)&255)<<8)|(((row+col+2)&255)<<16)|(((row+col+3)&255)<<24);
            s_axis_tvalid=1;s_axis_tlast=i==57599;
            @(posedge ref_clk);while(!s_axis_tready) @(posedge ref_clk);
        end
        @(negedge ref_clk);s_axis_tvalid=0;s_axis_tlast=0;
    end
    initial begin #50000000;$fatal(1,"display pipeline timeout");end
endmodule
