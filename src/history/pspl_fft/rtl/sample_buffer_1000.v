`timescale 1ns/1ps
// One frame: 1000 signed-16-bit bit patterns. No reset loop over memory.
module sample_buffer_1000 (
    input wire clk,
    input wire rst_n,
    input wire start,
    input wire sample_valid,
    input wire [15:0] sample_data,
    input wire [9:0] rd_addr,
    output reg busy,
    output reg done,
    output reg [9:0] sample_count,
    output wire [15:0] rd_data
);
    // Synchronous read permits block RAM inference. Check the actual report.
    (* ram_style = "block" *) reg [15:0] memory [0:999];
    reg [15:0] read_register;
    always @(posedge clk) begin
        if (rst_n && busy && sample_valid)
            memory[sample_count] <= sample_data;
    end
    always @(posedge clk) begin
        if (rd_addr < 10'd1000)
            read_register <= memory[rd_addr];
        else
            read_register <= 16'd0;
    end
    assign rd_data = (rst_n && rd_addr < sample_count && rd_addr < 10'd1000)
                   ? read_register : 16'd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            sample_count <= 10'd0;
        end else if (start && !busy) begin
            busy <= 1'b1;
            done <= 1'b0;
            sample_count <= 10'd0;
        end else if (busy && sample_valid) begin
            sample_count <= sample_count + 10'd1;
            if (sample_count == 10'd999) begin
                busy <= 1'b0;
                done <= 1'b1;
            end
        end
    end
endmodule
