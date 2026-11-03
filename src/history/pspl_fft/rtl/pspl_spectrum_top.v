`timescale 1ns/1ps
// PS control, PL sine source and 1000-point frame cache. Verilog-2005.
module pspl_spectrum_top #(
    parameter integer SAMPLE_DIV = 1000000
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk, ASSOCIATED_RESET resetn, FREQ_HZ 100000000" *)
    input wire clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *)
    input wire resetn,
    input wire [31:0] ps_control,
    output wire [31:0] pl_status,
    output wire [31:0] pl_sample
);
    wire core_rst_n = resetn & ps_control[1];
    reg start_previous;
    wire start_edge = ps_control[0] & ~start_previous;
    wire busy, done;
    wire accepted_start = start_edge & ~busy;
    reg [3:0] frame_id;
    reg frequency_5hz;
    reg half_amplitude;
    reg [31:0] divider;
    reg [6:0] phase;
    wire [7:0] next_phase = {1'b0, phase} +
                            (frequency_5hz ? 8'd5 : 8'd2);
    wire signed [15:0] lut_value;
    wire signed [15:0] half_value = lut_value / 16'sd2;
    reg [15:0] generated_data;
    reg generated_valid;
    wire [9:0] sample_count;
    wire [9:0] read_address = ps_control[11:2];
    wire [15:0] read_data;
    wire data_valid = core_rst_n && done && (read_address < 10'd1000);

    sine_lut_100 sine_table (.phase(phase), .value(lut_value));
    sample_buffer_1000 frame_cache (
        .clk(clk), .rst_n(core_rst_n), .start(accepted_start),
        .sample_valid(generated_valid), .sample_data(generated_data),
        .rd_addr(read_address), .busy(busy), .done(done),
        .sample_count(sample_count), .rd_data(read_data)
    );

    always @(posedge clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            start_previous <= 1'b0;
            frame_id <= 4'd0;
            frequency_5hz <= 1'b0;
            half_amplitude <= 1'b0;
            divider <= 32'd0;
            phase <= 7'd0;
            generated_data <= 16'd0;
            generated_valid <= 1'b0;
        end else begin
            start_previous <= ps_control[0];
            generated_valid <= 1'b0;
            if (accepted_start) begin
                frame_id <= frame_id + 4'd1;
                frequency_5hz <= ps_control[12];
                half_amplitude <= ps_control[13];
                divider <= 32'd0;
                phase <= 7'd0;
            end else if (busy) begin
                if (divider == SAMPLE_DIV - 1) begin
                    divider <= 32'd0;
                    generated_data <= half_amplitude ? half_value : lut_value;
                    generated_valid <= 1'b1;
                    phase <= (next_phase >= 8'd100) ? next_phase - 8'd100 : next_phase;
                end else begin
                    divider <= divider + 32'd1;
                end
            end
        end
    end

    // ctrl GPIO ch2: status. data GPIO ch1: signed sample and frame tag.
    assign pl_status = {4'hB, frame_id, core_rst_n, done, busy,
                        frequency_5hz, half_amplitude, 9'd0, sample_count};
    assign pl_sample = {4'hC, frame_id, data_valid, 7'd0,
                        (data_valid ? read_data : 16'd0)};
endmodule
