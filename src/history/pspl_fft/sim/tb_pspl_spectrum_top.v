`timescale 1ns/1ps
module tb_pspl_spectrum_top;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg resetn = 1'b0;
    reg [31:0] control = 32'd0;
    wire [31:0] status, sample;
    reg [15:0] lut [0:99];
    reg signed [15:0] expected;
    integer checks = 0;
    integer csv_file, ticks, address, frame, frequency, half;
    integer last_count, changes, last_tick, interval_checks;
    pspl_spectrum_top #(.SAMPLE_DIV(3)) dut (
        .clk(clk), .resetn(resetn), .ps_control(control),
        .pl_status(status), .pl_sample(sample)
    );
    task check;
        input condition;
        input [639:0] message;
        begin
            checks = checks + 1;
            if (condition !== 1'b1) begin
                $display("FAIL: %0s at %0t status=%h sample=%h", message, $time, status, sample);
                $finish(1);
            end
        end
    endtask
    function [31:0] command;
        input integer f, h, a, s;
        begin command = ((f == 5) << 12) | (h << 13) | (a << 2) | 2 | s; end
    endfunction
    task set_command;
        input [31:0] value;
        begin
            @(negedge clk); control = value;
            repeat (3) @(negedge clk);
        end
    endtask
    task run_frame;
        input integer f, h, expected_id;
        input integer try_busy_start;
        begin
            set_command(command(f,h,0,0));
            set_command(command(f,h,0,1));
            check(status[27:24] == expected_id, "frame id advanced once");
            if (try_busy_start) begin
                set_command(command(5,1,0,0));
                set_command(command(5,1,0,1));
                check(status[27:24] == expected_id, "busy start ignored");
            end
            ticks = 0;
            while (!status[22] && ticks < 4000) begin
                @(negedge clk); ticks = ticks + 1;
            end
            check(status[22] && !status[21] && status[9:0] == 1000, "done at exactly 1000");
            check(status[20] == (f == 5) && status[19] == h, "configuration latched at start");
            repeat (15) @(negedge clk);
            check(status[27:24] == expected_id && status[22], "held start cannot retrigger");
            for (address=0; address<1000; address=address+1) begin
                // Preserve a high start level even as the read address changes.
                set_command(command(f,h,address,1));
                expected = lut[(address*f)%100];
                if (h) expected = expected / 16'sd2;
                check(sample[31:28] == 4'hC && sample[27:24] == expected_id
                      && sample[23], "sample signature, frame id and valid flag");
                check(sample[15:0] == expected, "cached sample equals independent LUT reference");
                if (expected_id == 1 || expected_id == 2)
                    $fdisplay(csv_file,"%0d,%0d,%0d,%0d,%08h,%08h",f,h,address,$signed(sample[15:0]),status,sample);
            end
            check(status[27:24] == expected_id && status[22], "address writes do not retrigger");
            set_command(command(f,h,1023,1));
            check(!sample[23] && sample[15:0] == 0, "out-of-range address invalid and zero");
        end
    endtask
    // Independently check that successive stored values occur every 3 PL clocks.
    always @(negedge clk) begin
        if (!dut.core_rst_n || !status[21]) begin
            last_count = 0; changes = 0; last_tick = 0;
        end else begin
            changes = changes + 1;
            if (status[9:0] > last_count) begin
                if (last_count > 0) begin
                    check(changes-last_tick == 3, "test sample interval equals SAMPLE_DIV");
                    interval_checks = interval_checks + 1;
                end
                last_tick = changes;
                last_count = status[9:0];
            end
        end
    end
    initial begin
        interval_checks = 0;
        $readmemh("sim/lut_reference.hex", lut);
        csv_file = $fopen("rtl_samples.csv", "w");
        $fdisplay(csv_file,"frequency_hz,half_amplitude,index,received_counts,status_hex,data_hex");
        repeat (5) @(negedge clk);
        resetn = 1'b1;
        set_command(32'd2);
        check(status == 32'hB0800000, "reset identity and empty state");
        check(!sample[23], "empty cache is not valid");
        run_frame(2,0,1,1);
        run_frame(5,1,2,0);
        run_frame(2,1,3,0);
        run_frame(5,0,4,0);
        // Reset an unfinished frame, then prove recovery and no stale memory.
        set_command(command(2,0,0,0));
        set_command(command(2,0,0,1));
        repeat (20) @(negedge clk);
        set_command(32'd0);
        check(status[9:0] == 0 && !status[22] && !status[21] && !sample[23], "software reset masks old data");
        set_command(32'd2);
        run_frame(5,0,1,0);
        // Frame-id wrap; only check completion for the remaining frames.
        for (frame=2; frame<=16; frame=frame+1) begin
            set_command(command(2,0,0,0));
            set_command(command(2,0,0,1));
            ticks=0;
            while (!status[22] && ticks<4000) begin
                @(negedge clk); ticks=ticks+1;
            end
            check(status[22] && status[27:24] == (frame%16), "frame id wraps modulo 16");
        end
        $fclose(csv_file);
        $display("PASS: %0d checks, including %0d sample-interval checks", checks, interval_checks);
        $finish;
    end
    initial begin
        #2000000;
        $display("FAIL: global simulation timeout");
        $finish(1);
    end
endmodule
