`timescale 1ns/1ps
module tb_serializer;
    reg pixel_clk=0,serial_clk=0,rst=1;
    always #20 pixel_clk=~pixel_clk;
    always #4 serial_clk=~serial_clk;
    reg [9:0] word=0;
    wire data_out,clock_out;
    serializer_10to1 dut(pixel_clk,serial_clk,rst,word,data_out);
    serializer_10to1 forwarded_clock(pixel_clk,serial_clk,rst,10'b0000011111,clock_out);
    integer n,k,received=0;
    reg started=0;
    reg [9:0] captured,expected;
    initial begin
        repeat(10) @(negedge pixel_clk); rst=0;
        repeat(10) @(negedge pixel_clk);
        for(n=0;n<128;n=n+1) begin
            word=(10'h155+n*13)&1023;
            @(negedge pixel_clk);
        end
        word=0;
    end
    initial forever begin
        @(posedge clock_out); #0.2;
        captured[0]=data_out;
        for(k=1;k<10;k=k+1) begin
            @(posedge serial_clk or negedge serial_clk); #0.2;
            captured[k]=data_out;
        end
        if(!started && captured==10'h155) started=1;
        if(started) begin
            expected=(10'h155+received*13)&1023;
            if(captured!==expected) $fatal(1,"SERIAL BIT ORDER n=%0d expected=%h got=%h",received,expected,captured);
            received=received+1;
            if(received==128) begin
                $display("PASS SERIALIZER: 128 words, 1280 bits, clock recovery and LSB-first order (UNISIM)");
                $finish;
            end
        end
    end
    initial begin #20000; $fatal(1,"SERIAL TIMEOUT received=%0d",received); end
endmodule
