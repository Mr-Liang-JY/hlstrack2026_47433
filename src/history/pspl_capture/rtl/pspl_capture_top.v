`timescale 1ns / 1ps

// A small, synthesizable bridge between AXI GPIO and the Day 4 buffer.
// Both the GPIO IP and this module must use the SAME 100 MHz FCLK_CLK0.
// No external signal is acquired here: the PL generates a digital test ramp.
module pspl_capture_top #(
    parameter integer SAMPLE_DIV = 1000000
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk, ASSOCIATED_RESET resetn, FREQ_HZ 100000000" *)
    input  wire        clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *)
    input  wire        resetn,
    input  wire [31:0] ps_control,
    output wire [31:0] pl_status
);
    // Control: [31:16] ramp base, [5:2] read address,
    //          [1] software reset release, [0] start request.
    wire core_rst_n = resetn & ps_control[1];
    wire [3:0] read_address = ps_control[5:2];
    wire [15:0] requested_base = ps_control[31:16];

    reg start_previous;
    wire start_edge = ps_control[0] & ~start_previous;
    wire busy;
    wire done;
    wire [4:0] sample_count;
    wire [15:0] read_data;
    wire accepted_start = start_edge & ~busy;
    reg [3:0] frame_id;

    // Convert a slow PS-written level to one PL-clock event. Keeping start
    // high after completion must NOT start the capture again automatically.
    always @(posedge clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            start_previous <= 1'b0;
            frame_id <= 4'd0;
        end else begin
            start_previous <= ps_control[0];
            if (accepted_start)
                frame_id <= frame_id + 4'd1;
        end
    end

    reg [31:0] divider_count;
    reg [4:0] ramp_index;
    reg [15:0] latched_base;
    reg [15:0] generated_data;
    reg generated_valid;

    // The default divider gives 100 test samples/s at a 100 MHz FCLK.
    // Samples become visible to sample_buffer on the following clock edge.
    always @(posedge clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            divider_count <= 32'd0;
            ramp_index <= 5'd0;
            latched_base <= 16'd0;
            generated_data <= 16'd0;
            generated_valid <= 1'b0;
        end else begin
            generated_valid <= 1'b0;
            if (accepted_start) begin
                divider_count <= 32'd0;
                ramp_index <= 5'd0;
                latched_base <= requested_base;
            end else if (busy) begin
                if (divider_count == SAMPLE_DIV - 1) begin
                    divider_count <= 32'd0;
                    generated_data <= latched_base + {11'd0, ramp_index};
                    generated_valid <= 1'b1;
                    ramp_index <= ramp_index + 5'd1;
                end else begin
                    divider_count <= divider_count + 32'd1;
                end
            end else begin
                divider_count <= 32'd0;
            end
        end
    end

    sample_buffer capture_buffer (
        .clk(clk), .rst_n(core_rst_n), .start(start_edge),
        .sample_valid(generated_valid), .sample_data(generated_data),
        .rd_addr(read_address), .busy(busy), .done(done),
        .sample_count(sample_count), .wr_en(), .wr_addr(),
        .last_sample(), .rd_data(read_data)
    );

    // Status: [31:28] signature A, [27:24] frame id (modulo 16),
    // [23] reset released, [22] done, [21] busy, [20:16] sample count,
    // [15:0] data at the selected read address.
    assign pl_status = {4'hA, frame_id, core_rst_n, done, busy,
                        sample_count, read_data};
endmodule
