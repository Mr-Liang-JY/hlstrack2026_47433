`timescale 1ns/1ps
module tb_cdc_counter;
    reg sc=0,dc=0,sr=1,dr=1;
    reg [31:0] count=0;wire [31:0] result;
    always #13 sc=~sc;
    always #5 dc=~dc;
    cdc_counter dut(sc,sr,count,dc,dr,result);
    integer n;reg [31:0] previous=0;
    always @(negedge dc) if(!dr) begin
        if(result>count || result<previous) $fatal(1,"COUNTER CDC ORDER");
        previous=result;
    end
    initial begin
        repeat(4)@(negedge sc);sr=0;dr=0;
        for(n=0;n<1000;n=n+1) begin @(negedge sc);count=count+1;end
        repeat(12)@(negedge dc);
        if(result!=1000) $fatal(1,"FINAL COUNTER");
        $display("PASS CDC: 1000 asynchronous counter increments, monotonic transfer, final value");$finish;
    end
endmodule
