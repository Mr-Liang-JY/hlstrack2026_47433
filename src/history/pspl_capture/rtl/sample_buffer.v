`timescale 1ns / 1ps

// Day 4 teaching design: one frame contains 16 samples, 16 bits each.
// Inputs must belong to the clk domain and meet its setup/hold requirements.
// start is a one-cycle pulse, accepted only while busy == 0.
// The start edge arms the frame; the first sample is accepted on a later edge.
// Samples are accepted only when busy && sample_valid at a rising clk edge.
// done stays high after completion until reset or a new accepted start.
module sample_buffer (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire        sample_valid,
    input  wire [15:0] sample_data,
    input  wire [3:0]  rd_addr,
    output reg         busy,
    output reg         done,
    output reg  [4:0]  sample_count,
    output reg         wr_en,
    output reg  [3:0]  wr_addr,
    output reg  [15:0] last_sample,
    output wire [15:0] rd_data
);

    // Sixteen storage locations. Each location holds one 16-bit sample.
    reg [15:0] buffer_mem [0:15];

    // Small asynchronous read port, intended for this teaching buffer.
    // Unwritten positions return zero; reset invalidates the old frame.
    assign rd_data = ({1'b0, rd_addr} < sample_count)
                   ? buffer_mem[rd_addr] : 16'd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy         <= 1'b0;
            done         <= 1'b0;
            sample_count <= 5'd0;
            wr_en        <= 1'b0;
            wr_addr      <= 4'd0;
            last_sample  <= 16'd0;
        end else begin
            // One clock pulse for each accepted sample.
            wr_en <= 1'b0;

            if (start && !busy) begin
                busy         <= 1'b1;
                done         <= 1'b0;
                sample_count <= 5'd0;
                wr_addr      <= 4'd0;
                last_sample  <= 16'd0;
            end else if (busy && sample_valid) begin
                // The RHS uses the count before this clock edge's updates.
                buffer_mem[sample_count[3:0]] <= sample_data;
                wr_addr      <= sample_count[3:0];
                last_sample  <= sample_data;
                wr_en        <= 1'b1;
                sample_count <= sample_count + 5'd1;

                // Old count 15 means the 16th sample is being stored now.
                if (sample_count == 5'd15) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
            end
        end
    end
endmodule
