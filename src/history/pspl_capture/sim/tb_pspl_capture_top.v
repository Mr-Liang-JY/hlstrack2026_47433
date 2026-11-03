`timescale 1ns / 1ps

// Logic-level GPIO-vector test. This does not simulate the AXI GPIO IP,
// the AXI bus, the PS, implementation timing, or a physical board.
module tb_pspl_capture_top;
    reg clk;
    reg resetn;
    reg [31:0] control;
    wire [31:0] status;
    integer checks;
    integer errors;
    integer address;
    integer csv_file;
    reg [15:0] expected;

    pspl_capture_top #(.SAMPLE_DIV(4)) dut (
        .clk(clk), .resetn(resetn),
        .ps_control(control), .pl_status(status)
    );
    initial clk = 1'b0;
    always #5 clk = ~clk;

    task check;
        input condition;
        input [8*110-1:0] message;
        begin
            checks = checks + 1;
            if (condition !== 1'b1) begin
                errors = errors + 1;
                $display("FAIL @ %0t: %0s", $time, message);
            end
        end
    endtask

    task write_control;
        input start_bit;
        input release_reset;
        input [3:0] read_address;
        input [15:0] base_value;
        begin
            @(negedge clk);
            control = {base_value, 10'd0, read_address,
                       release_reset, start_bit};
            @(posedge clk);
            #1;
        end
    endtask

    task wait_done;
        input [3:0] expected_frame;
        integer cycles;
        begin
            cycles = 0;
            while ((status[22] !== 1'b1 || status[27:24] !== expected_frame)
                   && cycles < 500) begin
                @(posedge clk);
                #1;
                cycles = cycles + 1;
            end
            check(cycles < 500, "capture must finish within the cycle limit");
            check(status[31:28] === 4'hA, "signature must be A");
            check(status[27:24] === expected_frame, "frame id must match accepted start");
            check(status[23] === 1'b1, "software reset must be released");
            check(status[22] === 1'b1 && status[21] === 1'b0,
                  "completed frame must have done=1 and busy=0");
            check(status[20:16] === 5'd16, "completed frame must contain 16 samples");
        end
    endtask

    task read_frame;
        input [15:0] base_value;
        input [3:0] expected_frame;
        begin
            for (address = 0; address < 16; address = address + 1) begin
                write_control(1'b1, 1'b1, address, base_value);
                @(posedge clk);
                #1;
                expected = base_value + address;
                check(status[15:0] === expected, "readback sample must match the PL ramp");
                check(status[27:24] === expected_frame, "read address writes must not restart capture");
                check(status[20:16] === 5'd16 && status[22] === 1'b1,
                      "readback must preserve completed status");
                $fdisplay(csv_file, "%0d,%0d,%0d,%08h", expected_frame,
                          address, expected, status);
            end
        end
    endtask

    initial begin
        checks = 0;
        errors = 0;
        resetn = 1'b0;
        control = 32'd0;
        csv_file = $fopen("rtl_status_vectors.csv", "w");
        if (csv_file == 0) begin
            $display("TESTS FAILED: cannot create status vector CSV");
            $finish;
        end
        $fdisplay(csv_file, "frame_id,address,expected_value,status_hex");
        repeat (3) @(negedge clk);
        resetn = 1'b1;
        #1;
        check(status === 32'hA0000000, "GPIO default zero must hold the core in reset");

        $display("CASE 1: start held high and data 0..15");
        write_control(1'b0, 1'b1, 4'd0, 16'd0);
        write_control(1'b1, 1'b1, 4'd0, 16'd0);
        wait_done(4'd1);
        repeat (160) @(posedge clk);
        #1;
        check(status[27:24] === 4'd1 && status[22] === 1'b1,
              "a held start level must never automatically retrigger");
        read_frame(16'd0, 4'd1);

        $display("CASE 2: restart, ignore busy start, latch base");
        write_control(1'b0, 1'b1, 4'd0, 16'd100);
        write_control(1'b1, 1'b1, 4'd0, 16'd100);
        repeat (8) @(posedge clk);
        #1;
        check(status[21] === 1'b1 && status[27:24] === 4'd2,
              "second capture must be busy with the new frame id");
        write_control(1'b0, 1'b1, 4'd0, 16'd500);
        write_control(1'b1, 1'b1, 4'd0, 16'd500);
        check(status[27:24] === 4'd2, "start while busy must be ignored");
        wait_done(4'd2);
        read_frame(16'd100, 4'd2);

        $display("CASE 3: 16-bit wraparound");
        write_control(1'b0, 1'b1, 4'd0, 16'd65530);
        write_control(1'b1, 1'b1, 4'd0, 16'd65530);
        wait_done(4'd3);
        read_frame(16'd65530, 4'd3);

        $display("CASE 4: reset during capture and capture again");
        write_control(1'b0, 1'b1, 4'd0, 16'd200);
        write_control(1'b1, 1'b1, 4'd0, 16'd200);
        repeat (12) @(posedge clk);
        #1;
        check(status[20:16] > 0 && status[21] === 1'b1,
              "partial capture must have received some samples");
        write_control(1'b0, 1'b0, 4'd0, 16'd0);
        check(status === 32'hA0000000, "soft reset clears count, frame id, and status");
        write_control(1'b0, 1'b1, 4'd0, 16'd300);
        write_control(1'b1, 1'b1, 4'd0, 16'd300);
        wait_done(4'd1);
        read_frame(16'd300, 4'd1);

        $fclose(csv_file);
        if (errors == 0)
            $display("ALL RTL TESTS PASSED (%0d checks)", checks);
        else
            $display("TESTS FAILED: %0d errors in %0d checks", errors, checks);
        $finish;
    end

    initial begin
        #200000;
        $display("TESTS FAILED: testbench timeout");
        $finish;
    end
endmodule
