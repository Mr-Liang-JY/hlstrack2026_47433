`timescale 1ns/1ps
module tb_video_timing;
    reg pixel_clk=0;always #2 pixel_clk=~pixel_clk;
    reg rst=1;wire [10:0] x;wire [9:0] y;wire de,hsync,vsync,frame_end;
    video_timing dut(.*);
    integer n,active=0,sync_h=0,sync_v=0;
    initial begin
        repeat(4) @(negedge pixel_clk);rst=0;
        for(n=0;n<2*1650*750;n=n+1) begin
            if(x!==n%1650 || y!==(n/1650)%750) $fatal(1,"coordinate mismatch");
            if(de!==(x<1280 && y<720)) $fatal(1,"DE mismatch");
            if(hsync!==(x>=1390 && x<1430)) $fatal(1,"HS mismatch");
            if(vsync!==(y>=725 && y<730)) $fatal(1,"VS mismatch");
            if(frame_end!==(x==1649 && y==749)) $fatal(1,"frame end mismatch");
            if(de)active=active+1;if(hsync)sync_h=sync_h+1;if(vsync)sync_v=sync_v+1;
            @(negedge pixel_clk);
        end
        if(active!=2*1280*720 || sync_h!=2*40*750 || sync_v!=2*5*1650) $fatal(1,"frame totals mismatch");
        $display("PASS 720p timing: two 1650x750 frames, 1843200 active pixels, positive sync");$finish;
    end
endmodule
