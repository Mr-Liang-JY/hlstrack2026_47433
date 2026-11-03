`timescale 1ns/1ps
module tb_axis_framebuffer;
    reg clk=0,pixel_clk=0;always #5 clk=~clk;always #7 pixel_clk=~pixel_clk;
    reg resetn=0,pixel_reset=1;
    reg [31:0] data=0;reg [3:0] keep=15;
    reg valid=0,last=0;wire ready,pending,protocol_error;
    wire [15:0] presented;reg vblank_start=0;reg [3:0] read_address=0;
    wire [31:0] read_data;wire have_frame;
    axis_framebuffer #(.WORDS(8),.AW(4)) dut(.*);
    integer i;
    task word(input [31:0] value,input integer final_word);
        begin
            @(negedge clk);data=value;last=final_word;valid=1;
            @(posedge clk);while(!ready) @(posedge clk);
            @(negedge clk);valid=0;last=0;
        end
    endtask
    task blank;
        begin
            repeat(5) @(negedge pixel_clk);
            vblank_start=1;@(negedge pixel_clk);vblank_start=0;
            repeat(7) @(negedge clk);
        end
    endtask
    task read_check(input integer base);
        begin
            for(integer j=0;j<8;j=j+1) begin
                @(negedge pixel_clk);read_address=j;
                @(posedge pixel_clk);#1;
                if(read_data!==(base+j)) $fatal(1,"buffer read bank corruption at %d got %h expected %h",j,read_data,base+j);
            end
        end
    endtask
    initial begin
        repeat(5) @(negedge clk);resetn=1;
        repeat(5) @(negedge pixel_clk);pixel_reset=0;
        for(i=0;i<8;i=i+1) word(32'h10203000+i,i==7);
        repeat(3) @(negedge clk);
        if(!pending || ready || have_frame) $fatal(1,"must wait for vblank before first display");
        blank();if(presented!=1 || !have_frame || pending) $fatal(1,"first swap acknowledgment");
        read_check(32'h10203000);
        // Update second bank, while reading the untouched first bank.
        for(i=0;i<8;i=i+1) begin word(32'h50607000+i,i==7);if(i==3)read_check(32'h10203000);end
        read_check(32'h10203000);blank();read_check(32'h50607000);
        if(presented!=2) $fatal(1,"second swap missing");
        // Immediate post-ack transfer exercises the bank ownership transition.
        for(i=0;i<8;i=i+1) word(32'h12340000+i,i==7);
        blank();read_check(32'h12340000);
        // Reject short packet, preserve visible bank, then recover with full frame.
        word(99,0);word(100,1);blank();
        if(!protocol_error || presented!=3) $fatal(1,"short TLAST not rejected");
        read_check(32'h12340000);
        for(i=0;i<8;i=i+1) word(32'h56780000+i,i==7);
        blank();read_check(32'h56780000);
        if(presented!=4) $fatal(1,"did not recover after short packet");
        $display("PASS framebuffer: atomic swaps, bank ownership, CDC, short-packet rejection and recovery");$finish;
    end
    initial begin #1000000;$fatal(1,"timeout");end
endmodule
