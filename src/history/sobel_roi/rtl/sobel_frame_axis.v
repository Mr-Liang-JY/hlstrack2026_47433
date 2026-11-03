`timescale 1ns/1ps
// Offline frame accelerator. One uint32 word per grayscale/output pixel.
// Store-and-process architecture: full frame BRAM, not a streaming line buffer.
module sobel_frame_axis #(
    parameter integer WIDTH = 128,
    parameter integer HEIGHT = 128
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk, ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET resetn, FREQ_HZ 100000000" *)
    input wire clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *)
    input wire resetn,
    input wire [31:0] ps_control,
    input wire [31:0] roi_config,
    output wire [31:0] pl_status,
    output reg [31:0] roi_edge_count,
    output reg [31:0] roi_edge_y_sum,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXIS, TDATA_NUM_BYTES 4, HAS_TKEEP 1, HAS_TLAST 1, HAS_TREADY 1" *)
    input wire [31:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TKEEP" *)
    input wire [3:0] s_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TLAST" *)
    input wire s_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TVALID" *)
    input wire s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TREADY" *)
    output wire s_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME M_AXIS, TDATA_NUM_BYTES 4, HAS_TKEEP 1, HAS_TLAST 1, HAS_TREADY 1" *)
    output wire [31:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TKEEP" *)
    output wire [3:0] m_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output wire m_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output wire m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input wire m_axis_tready
);
    localparam integer PIXELS = WIDTH * HEIGHT;
    localparam [3:0] IDLE=0, RECEIVE=1, PREPARE=2, READ_PIXEL=3,
                     TAKE_PIXEL=4, FIRE=5, RESULT=6, SEND=7;
    wire core_resetn = resetn & ps_control[0];
    reg [3:0] state;
    reg start_old, busy, done;
    reg [3:0] frame_id, error_code;
    reg [7:0] threshold, x0, y0, x1, y1;
    reg [7:0] x, y;
    reg [15:0] write_index, output_index;
    reg [3:0] tap;
    reg [7:0] patch [0:8];
    reg [31:0] output_word;
    (* ram_style = "block" *) reg [7:0] frame_memory [0:PIXELS-1];
    reg [15:0] read_address;
    reg [7:0] read_value;
    wire sobel_valid, sobel_edge;
    wire [10:0] sobel_magnitude;
    wire inside_roi = (x >= x0) && (x < x1) && (y >= y0) && (y < y1);
    assign s_axis_tready = core_resetn && (state == RECEIVE);
    assign m_axis_tvalid = core_resetn && (state == SEND);
    assign m_axis_tdata = output_word;
    assign m_axis_tkeep = 4'hf;
    assign m_axis_tlast = (output_index == PIXELS-1);
    assign pl_status = {4'hD, frame_id, error_code, 18'd0, busy, done};

    always @* begin
        case (tap)
          0: read_address = output_index - WIDTH - 1;
          1: read_address = output_index - WIDTH;
          2: read_address = output_index - WIDTH + 1;
          3: read_address = output_index - 1;
          4: read_address = output_index;
          5: read_address = output_index + 1;
          6: read_address = output_index + WIDTH - 1;
          7: read_address = output_index + WIDTH;
          default: read_address = output_index + WIDTH + 1;
        endcase
    end
    // Synchronous memory read. No reset loop over the frame RAM.
    always @(posedge clk) begin
        if (s_axis_tvalid && s_axis_tready)
            frame_memory[write_index] <= s_axis_tdata[7:0];
        if (state == READ_PIXEL)
            read_value <= frame_memory[read_address];
    end
    sobel3x3_core arithmetic (
        .clk(clk), .rst_n(core_resetn), .in_valid(state == FIRE),
        .p00(patch[0]), .p01(patch[1]), .p02(patch[2]),
        .p10(patch[3]), .p11(patch[4]), .p12(patch[5]),
        .p20(patch[6]), .p21(patch[7]), .p22(patch[8]),
        .threshold(threshold), .out_valid(sobel_valid),
        .magnitude(sobel_magnitude), .edge_bit(sobel_edge)
    );
    always @(posedge clk) begin
        if (!core_resetn) begin
            state <= IDLE; start_old <= 0; busy <= 0; done <= 0;
            frame_id <= 0; error_code <= 0; threshold <= 80;
            write_index <= 0; output_index <= 0; x <= 0; y <= 0;
            x0 <= 0; y0 <= 0; x1 <= WIDTH; y1 <= HEIGHT;
            tap <= 0; output_word <= 0;
            roi_edge_count <= 0; roi_edge_y_sum <= 0;
        end else begin
            start_old <= ps_control[1];
            case (state)
              IDLE: if (ps_control[1] && !start_old) begin
                  frame_id <= frame_id + 1'b1;
                  threshold <= ps_control[15:8];
                  x0 <= roi_config[7:0]; y0 <= roi_config[15:8];
                  x1 <= roi_config[23:16]; y1 <= roi_config[31:24];
                  error_code <= 0;
                  if ((roi_config[7:0] >= roi_config[23:16]) ||
                      (roi_config[15:8] >= roi_config[31:24]) ||
                      (roi_config[23:16] > WIDTH) || (roi_config[31:24] > HEIGHT))
                      error_code <= 4'd2;
                  busy <= 1; done <= 0; write_index <= 0;
                  output_index <= 0; x <= 0; y <= 0;
                  roi_edge_count <= 0; roi_edge_y_sum <= 0;
                  state <= RECEIVE;
              end
              RECEIVE: if (s_axis_tvalid && s_axis_tready) begin
                  if (s_axis_tkeep != 4'hf || s_axis_tdata[31:8] != 0 ||
                      s_axis_tlast != (write_index == PIXELS-1))
                      error_code <= 4'd1;
                  if (write_index == PIXELS-1) state <= PREPARE;
                  else write_index <= write_index + 1'b1;
              end
              PREPARE: begin
                  if (x == 0 || x == WIDTH-1 || y == 0 || y == HEIGHT-1) begin
                      output_word <= 0; state <= SEND;
                  end else begin tap <= 0; state <= READ_PIXEL; end
              end
              READ_PIXEL: state <= TAKE_PIXEL;
              TAKE_PIXEL: begin
                  patch[tap] <= read_value;
                  if (tap == 8) state <= FIRE;
                  else begin tap <= tap + 1'b1; state <= READ_PIXEL; end
              end
              FIRE: state <= RESULT;
              RESULT: begin
                  if (sobel_valid) begin
                      output_word <= sobel_edge ? 32'd255 : 32'd0;
                      if (sobel_edge && inside_roi) begin
                          roi_edge_count <= roi_edge_count + 1'b1;
                          roi_edge_y_sum <= roi_edge_y_sum + y;
                      end
                      state <= SEND;
                  end
              end
              SEND: if (m_axis_tready) begin
                  if (output_index == PIXELS-1) begin
                      done <= 1; busy <= 0; state <= IDLE;
                  end else begin
                      output_index <= output_index + 1'b1;
                      if (x == WIDTH-1) begin x <= 0; y <= y + 1'b1; end
                      else x <= x + 1'b1;
                      state <= PREPARE;
                  end
              end
              default: begin state <= IDLE; error_code <= 4'd4; busy <= 0; end
            endcase
        end
    end
endmodule
