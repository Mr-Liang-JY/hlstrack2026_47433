`timescale 1ns/1ps
// Three independent pixel encoders, four 10:1 serializers and TMDS output buffers.
module hdmi_video(
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME ref_clk, FREQ_HZ 100000000, ASSOCIATED_RESET resetn" *)
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ref_clk CLK" *)
    input wire ref_clk,
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME pixel_clk, FREQ_HZ 25200000" *)
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 pixel_clk CLK" *)
    input wire pixel_clk,
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME serial_clk, FREQ_HZ 126000000" *)
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 serial_clk CLK" *)
    input wire serial_clk,
    input wire resetn, input wire locked, input wire button_reset,
    input wire hdmi_hpd_n,
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME hdmi_clk_p, FREQ_HZ 25200000" *)
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 hdmi_clk_p CLK" *)
    output wire hdmi_clk_p,
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME hdmi_clk_n, FREQ_HZ 25200000" *)
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 hdmi_clk_n CLK" *)
    output wire hdmi_clk_n,
    output wire [2:0] hdmi_data_p, output wire [2:0] hdmi_data_n,
    output wire [3:0] leds, output wire [31:0] status
);
    wire rst;
    reset_sync pixel_reset(.clk(pixel_clk),
        .arst(!resetn || !locked || button_reset), .rst(rst));
    wire [9:0] x, y;
    wire de, hsync, vsync, frame_end, heartbeat;
    wire [23:0] rgb;
    video_timing timing(pixel_clk, rst, x, y, de, hsync, vsync, frame_end);
    test_pattern pattern(pixel_clk, rst, frame_end, x, y, de, rgb, heartbeat);
    wire [9:0] encoded [0:2];
    tmds_encoder blue(pixel_clk, rst, rgb[7:0], de, hsync, vsync, encoded[0]);
    tmds_encoder green(pixel_clk, rst, rgb[15:8], de, 1'b0, 1'b0, encoded[1]);
    tmds_encoder red(pixel_clk, rst, rgb[23:16], de, 1'b0, 1'b0, encoded[2]);
    wire [2:0] data_serial;
    wire clock_serial;
    genvar k;
    generate for (k=0; k<3; k=k+1) begin: channels
        serializer_10to1 ser(pixel_clk, serial_clk, rst, encoded[k], data_serial[k]);
        OBUFDS #(.IOSTANDARD("TMDS_33"), .SLEW("FAST"))
            data_buffer(.I(data_serial[k]), .O(hdmi_data_p[k]), .OB(hdmi_data_n[k]));
    end endgenerate
    serializer_10to1 clock_ser(pixel_clk, serial_clk, rst, 10'b0000011111, clock_serial);
    OBUFDS #(.IOSTANDARD("TMDS_33"), .SLEW("FAST"))
        clock_buffer(.I(clock_serial), .O(hdmi_clk_p), .OB(hdmi_clk_n));

    // Synchronize each independent debug bit into the 100 MHz AXI clock domain.
    (* ASYNC_REG = "TRUE" *) reg [1:0] hpd_sync, alive_sync, rstn_sync, lock_sync;
    always @(posedge ref_clk) begin
        if (!resetn) begin
            hpd_sync <= 2'b11; alive_sync <= 0; rstn_sync <= 0; lock_sync <= 0;
        end else begin
            hpd_sync <= {hpd_sync[0], hdmi_hpd_n};
            alive_sync <= {alive_sync[0], heartbeat};
            rstn_sync <= {rstn_sync[0], !rst};
            lock_sync <= {lock_sync[0], locked};
        end
    end
    // LD0 locked; LD1 video reset released; LD2 monitor HPD; LD3 heartbeat.
    assign leds = {alive_sync[1], !hpd_sync[1], rstn_sync[1], lock_sync[1]};
    assign status = {24'h484431, 4'b0000, leds}; // ASCII 'HD1', debug bits.
endmodule
