`timescale 1ns/1ps
module tb_tmds_encoder;
    reg clk=0,rst=1,de=0,c0=0,c1=0;
    reg [7:0] data=0;
    wire [9:0] symbol;
    always #5 clk=~clk;
    tmds_encoder dut(clk,rst,data,de,c0,c1,symbol);
    integer rd=0,checks=0,n,k,ones,transitions;
    reg [7:0] q,decoded;
    reg [9:0] expected_control;
    reg [31:0] lfsr=32'h3d61fa89;
    task check(input reg active,input reg [7:0] d,input reg [1:0] control);
        begin
            @(negedge clk); de=active; data=d; {c1,c0}=control;
            @(posedge clk); #1;
            if(!active) begin
                case(control)
                    0:expected_control=10'b1101010100;
                    1:expected_control=10'b0010101011;
                    2:expected_control=10'b0101010100;
                    3:expected_control=10'b1010101011;
                endcase
                if(symbol!==expected_control) $fatal(1,"CONTROL %b got=%b",control,symbol);
                rd=0;
            end else begin
                // Decode the transmitted symbol instead of duplicating the RTL encoder.
                q=symbol[9] ? ~symbol[7:0] : symbol[7:0];
                decoded[0]=q[0]; transitions=0;
                for(k=1;k<8;k=k+1) begin
                    decoded[k]=symbol[8] ? q[k]^q[k-1] : ~(q[k]^q[k-1]);
                    if(q[k]!=q[k-1]) transitions=transitions+1;
                end
                if(decoded!==d) $fatal(1,"DECODE sent=%h recovered=%h symbol=%b",d,decoded,symbol);
                if(transitions>4) $fatal(1,"TRANSITION MINIMIZATION");
                ones=0;
                for(k=0;k<10;k=k+1) ones=ones+symbol[k];
                rd=rd+2*ones-10;
                if(rd < -8 || rd > 8) $fatal(1,"DC BALANCE rd=%0d",rd);
            end
            if($signed(dut.disparity)!==rd) $fatal(1,"RUNNING DISPARITY got=%0d expected=%0d",$signed(dut.disparity),rd);
            checks=checks+1;
        end
    endtask
    initial begin
        repeat(4) @(negedge clk); rst=0;
        for(n=0;n<4;n=n+1) check(0,0,n);
        check(1,0,0); if(symbol!==10'h100) $fatal(1,"KNOWN ZERO SYMBOL");
        check(0,0,0);
        check(1,255,0); if(symbol!==10'h200) $fatal(1,"KNOWN FF SYMBOL");
        for(n=0;n<256;n=n+1) begin
            check(0,0,n%4);
            repeat(16) check(1,n,0);
        end
        for(n=0;n<32768;n=n+1) begin
            lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
            check(1,lfsr[7:0],0);
            if(n%257==0) check(0,0,n%4);
        end
        $display("PASS TMDS: %0d symbols, all bytes, controls, decode, transitions and DC balance",checks);
        $finish;
    end
    initial begin #2000000; $fatal(1,"TIMEOUT"); end
endmodule
