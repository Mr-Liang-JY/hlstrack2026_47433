`timescale 1ns/1ps
module tb_dvp_framebuffer;
    reg pc=0,vc=0,pr=1,vr=1,hs=0,vs=0,swap=0,fe=0;
    reg [7:0] data=0;reg [3:0] addr=0;
    wire [15:0] pixel;wire valid;
    wire [31:0] good,bad,dropped,shown;
    reg pc_run=1;
    always #7 if(pc_run) pc=~pc;else pc=0;
    always #11 vc=~vc;
    dvp_framebuffer #(.WIDTH(4),.HEIGHT(3)) dut(pc,pr,data,hs,vs,swap,vc,vr,fe,addr,pixel,valid,good,bad,dropped,shown);
    integer i,j,index;
    reg [15:0] word,expected;
    task sync_pulse;
        begin @(negedge pc);vs=1;repeat(3)@(negedge pc);vs=0;repeat(3)@(negedge pc);end
    endtask
    task send_frame(input integer tag,input integer malformed);
        begin
            sync_pulse();
            for(j=0;j<3;j=j+1) begin
                for(i=0;i<8;i=i+1) begin
                    @(negedge pc);hs=1;index=j*4+i/2;word=tag+index;
                    data=(i%2==0)?word[15:8]:word[7:0];
                    if(malformed && j==1 && i==7) hs=0;
                end
                @(negedge pc);hs=0;repeat(3)@(negedge pc);
            end
            sync_pulse();repeat(8)@(negedge vc);
        end
    endtask
    task commit;
        begin @(negedge vc);fe=1;@(negedge vc);fe=0;repeat(8)@(negedge pc);end
    endtask
    task check_frame(input integer tag,input integer reversed);
        integer n;
        begin
            for(n=0;n<12;n=n+1) begin
                @(negedge vc);addr=n;@(posedge vc);#1;
                expected=tag+n;
                if(reversed) expected={expected[7:0],expected[15:8]};
                if(pixel!==expected) $fatal(1,"PIXEL %0d expected=%h got=%h",n,expected,pixel);
            end
        end
    endtask
    always @(posedge pc) if(!pr && dut.wr_en) begin
        if(dut.wr_address>=24) $fatal(1,"WRITE OUT OF RANGE");
        if(valid && ((dut.wr_address>=12)==dut.display_bank)) $fatal(1,"WRITING DISPLAY BANK / TEARING");
    end
    initial begin
        repeat(5)@(negedge pc);pr=0;vr=0;
        send_frame(16'h1200,0);
        if(good!=1 || valid) $fatal(1,"FIRST FRAME MUST WAIT FOR DISPLAY BOUNDARY");
        send_frame(16'h2200,0);
        if(dropped!=1 || good!=1) $fatal(1,"NO FREE BANK MUST DROP WHOLE FRAME");
        commit();if(!valid || shown!=1) $fatal(1,"COMMIT");check_frame(16'h1200,0);
        send_frame(16'h3400,0);check_frame(16'h1200,0);
        commit();check_frame(16'h3400,0);
        send_frame(16'h5600,1);
        if(bad!=1 || good!=2) $fatal(1,"ODD BYTE LINE MUST BE REJECTED");
        commit();check_frame(16'h3400,0);
        swap=1;send_frame(16'h7800,0);commit();check_frame(16'h7800,1);
        if(good!=3 || shown!=3) $fatal(1,"FINAL COUNTS");
        // Camera clock can stop while reset is asserted. The pixel side must
        // invalidate the old frame, then accept only fresh data after restart.
        @(negedge pc);pc_run=0;pr=1;vr=1;
        repeat(8)@(negedge vc);
        if(valid || shown!=0) $fatal(1,"RESET WITH STOPPED PCLK MUST INVALIDATE DISPLAY");
        pc_run=1;repeat(5)@(negedge pc);pr=0;vr=0;swap=0;
        send_frame(16'h9a00,0);
        if(good!=1 || valid) $fatal(1,"RESTART MUST WAIT FOR A NEW COMPLETE FRAME");
        commit();check_frame(16'h9a00,0);
        if(good!=1 || shown!=1) $fatal(1,"RESTART COUNTS");
        $display("PASS DVP: bytes, pixel order, both VSYNC edges, malformed line, buffer ownership, frame-boundary swap, dropped frame, byte swap and stopped-clock reset/restart");
        $finish;
    end
    initial begin #100000;$fatal(1,"TIMEOUT");end
endmodule
