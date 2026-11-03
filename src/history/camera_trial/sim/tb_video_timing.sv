`timescale 1ns/1ps
module tb_video_timing;
    reg clk=0, rst=1;
    always #5 clk=~clk;
    wire [9:0] x,y;
    wire de,hs,vs,fe,hb;
    wire [23:0] rgb;
    video_timing dut(clk,rst,x,y,de,hs,vs,fe);
    test_pattern pat(clk,rst,fe,x,y,de,rgb,hb);
    integer n, active_count=0, hlow=0, vlow=0;
    reg [23:0] expected;
    initial begin
        repeat(4) @(negedge clk);
        rst=0;
        for(n=0;n<840000;n=n+1) begin
            #1;
            if(x !== n%800 || y !== (n/800)%525) $fatal(1,"COUNTER n=%0d x=%0d y=%0d",n,x,y);
            if(de !== ((x<640)&&(y<480))) $fatal(1,"DE");
            if(hs !== !((x>=656)&&(x<752))) $fatal(1,"HSYNC");
            if(vs !== !((y>=490)&&(y<492))) $fatal(1,"VSYNC");
            if(fe !== ((x==799)&&(y==524))) $fatal(1,"FRAME_END");
            if(de) active_count=active_count+1;
            if(!hs) hlow=hlow+1;
            if(!vs) vlow=vlow+1;
            if(!de && rgb!==0) $fatal(1,"BLANKING RGB");
            if(de && (x<2 || x>=638 || y<2 || y>=478) && rgb!==24'hffffff) $fatal(1,"BORDER");
            if(y==200 && x>=2 && x<638) begin
                case(x/80)
                    0: expected=24'hffffff; 1: expected=24'hffff00;
                    2: expected=24'h00ffff; 3: expected=24'h00ff00;
                    4: expected=24'hff00ff; 5: expected=24'hff0000;
                    6: expected=24'h0000ff; 7: expected=24'h000000;
                endcase
                if(rgb!==expected) $fatal(1,"BAR x=%0d got=%h",x,rgb);
            end
            @(negedge clk);
        end
        if(active_count!=614400 || hlow!=100800 || vlow!=3200) $fatal(1,"FRAME TOTALS");
        if(pat.box_x!=36 || pat.box_y!=66) $fatal(1,"BOX FRAME UPDATE");
        $display("PASS TIMING: 2 frames, 840000 pixels, 614400 active, bars/border/motion checked");
        $finish;
    end
    initial begin #10000000; $fatal(1,"TIMEOUT"); end
endmodule
