`timescale 1ns/1ps
module tb_sobel_frame_axis;
    reg clk=0; always #5 clk=~clk;
    reg resetn=0;
    reg [31:0] ps_control=0, roi_config=0;
    wire [31:0] pl_status,roi_edge_count,roi_edge_y_sum;
    reg [31:0] s_axis_tdata=0;
    reg [3:0] s_axis_tkeep=15;
    reg s_axis_tlast=0,s_axis_tvalid=0;
    wire s_axis_tready;
    wire [31:0] m_axis_tdata;
    wire [3:0] m_axis_tkeep;
    wire m_axis_tlast,m_axis_tvalid;
    reg m_axis_tready=0;
    sobel_frame_axis dut(.*);
    integer handle, scanned, cases, case_index, i, sent, received, cycles=0;
    integer th,x0,y0,x1,y1,expected_count,expected_sum;
    integer total_checked=0;
    integer input_pixels[0:16383], expected_pixels[0:16383];
    reg stalled=0;
    reg [31:0] stalled_data;
    reg stalled_last;
    always @(posedge clk) begin
        cycles=cycles+1;
        if (stalled && (!m_axis_tvalid || m_axis_tdata!==stalled_data || m_axis_tlast!==stalled_last))
            $fatal(1,"AXIS output changed under backpressure");
        stalled=m_axis_tvalid && !m_axis_tready;
        stalled_data=m_axis_tdata; stalled_last=m_axis_tlast;
    end
    initial begin
        repeat(5) @(negedge clk); resetn=1;
        handle=$fopen("vectors.txt","r");
        if(!handle) $fatal(1,"Missing vectors.txt");
        scanned=$fscanf(handle,"%d\n",cases);
        for(case_index=0;case_index<cases;case_index=case_index+1) begin
            scanned=$fscanf(handle,"%d %d %d %d %d %d %d\n",th,x0,y0,x1,y1,expected_count,expected_sum);
            if(scanned!=7) $fatal(1,"Invalid vector header");
            for(i=0;i<16384;i=i+1) begin
                scanned=$fscanf(handle,"%d %d\n",input_pixels[i],expected_pixels[i]);
                if(scanned!=2) $fatal(1,"Incomplete frame vector");
            end
            @(negedge clk);
            roi_config=(y1<<24)|(x1<<16)|(y0<<8)|x0;
            ps_control=(th<<8)|1;
            repeat(3) @(negedge clk);
            ps_control=(th<<8)|3;
            repeat(3) @(negedge clk);
            ps_control=(th<<8)|1;
            sent=0;received=0;
            fork
                begin
                    while(sent<16384) begin
                        @(negedge clk);
                        s_axis_tvalid=(cycles%5 != 0);
                        s_axis_tdata=input_pixels[sent];
                        s_axis_tlast=(sent==16383);
                        @(posedge clk);
                        if(s_axis_tvalid && s_axis_tready) sent=sent+1;
                    end
                    @(negedge clk);s_axis_tvalid=0;s_axis_tlast=0;
                end
                begin
                    while(received<16384) begin
                        @(negedge clk);m_axis_tready=(cycles%7 != 2 && cycles%11 != 4);
                        @(posedge clk);
                        if(m_axis_tvalid && m_axis_tready) begin
                            if(m_axis_tdata!==expected_pixels[received] || m_axis_tkeep!==4'hf ||
                               m_axis_tlast!==(received==16383))
                                $fatal(1,"Frame %0d pixel %0d got %0d expected %0d LAST=%b",case_index,received,m_axis_tdata,expected_pixels[received],m_axis_tlast);
                            received=received+1;total_checked=total_checked+1;
                        end
                    end
                    @(negedge clk);m_axis_tready=0;
                end
            join
            repeat(3) @(negedge clk);
            if(pl_status[1:0]!=1 || pl_status[23:20]!=0 ||
               roi_edge_count!=expected_count || roi_edge_y_sum!=expected_sum)
                $fatal(1,"ROI/status mismatch case=%0d status=%h count=%0d/%0d sum=%0d/%0d",case_index,pl_status,roi_edge_count,expected_count,roi_edge_y_sum,expected_sum);
            $display("FRAME %0d PASSED: 16384 pixels, ROI count=%0d ysum=%0d",case_index,roi_edge_count,roi_edge_y_sum);
        end
        $display("DAY9 AXIS SOBEL SIMULATION PASSED (%0d frames; %0d pixels; backpressure, TLAST and ROI verified)",cases,total_checked);
        $finish;
    end
    initial begin #100000000; $fatal(1,"Simulation timeout"); end
endmodule
