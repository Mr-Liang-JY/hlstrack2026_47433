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

    // Keep full-frame reception; cache three rows and reuse adjacent windows.
    // One uint32 per pixel, one TLAST per frame, unchanged v1 control contract.
    localparam integer PIXELS = WIDTH * HEIGHT;
    localparam [3:0] IDLE=0, RECEIVE=1, PREPARE=2, LOAD_ADDR=3,
        LOAD_STORE=4, PRIME=5, FIRE=6, RESULT=7, SEND=8;
    wire core_resetn = resetn & ps_control[0];
    reg [3:0] state;
    reg start_old, busy, done;
    reg [3:0] frame_id, error_code;
    reg [7:0] threshold, x0,y0,x1,y1,x,y;
    reg [15:0] write_index, output_index;
    reg [7:0] patch[0:8];
    reg [31:0] output_word;
    (* ram_style = "block" *) reg [7:0] frame_memory[0:PIXELS-1];
    (* ram_style = "distributed" *) reg [7:0] row0[0:WIDTH-1];
    (* ram_style = "distributed" *) reg [7:0] row1[0:WIDTH-1];
    (* ram_style = "distributed" *) reg [7:0] row2[0:WIDTH-1];
    reg [7:0] read_value, load_row, load_col;
    reg [1:0] load_bank, top_bank, prime_col;
    reg rows_initialized, rows_ready, window_ready;
    wire [7:0] column = state == PRIME ? {6'd0,prime_col} : x + 1'b1;
    wire [7:0] a = top_bank == 0 ? row0[column] : top_bank == 1 ? row1[column] : row2[column];
    wire [7:0] b = top_bank == 0 ? row1[column] : top_bank == 1 ? row2[column] : row0[column];
    wire [7:0] c = top_bank == 0 ? row2[column] : top_bank == 1 ? row0[column] : row1[column];
    wire inside_roi = x>=x0 && x<x1 && y>=y0 && y<y1;
    wire sobel_valid,sobel_edge;
    wire [10:0] sobel_magnitude;
    assign s_axis_tready = core_resetn && state==RECEIVE;
    assign m_axis_tvalid = core_resetn && state==SEND;
    assign m_axis_tdata = output_word;
    assign m_axis_tkeep = 4'hf;
    assign m_axis_tlast = output_index==PIXELS-1;
    assign pl_status = {4'hD,frame_id,error_code,18'd0,busy,done};
    always @(posedge clk) begin
        if(s_axis_tvalid && s_axis_tready)
            frame_memory[write_index] <= s_axis_tdata[7:0];
        if(state==LOAD_ADDR)
            read_value <= frame_memory[load_row*WIDTH+load_col];
        if(state==LOAD_STORE) begin
            case(load_bank)
                0: row0[load_col] <= read_value;
                1: row1[load_col] <= read_value;
                2: row2[load_col] <= read_value;
            endcase
        end
    end
    sobel3x3_core arithmetic(
        .clk(clk),.rst_n(core_resetn),.in_valid(state==FIRE),
        .p00(patch[0]),.p01(patch[1]),.p02(patch[2]),
        .p10(patch[3]),.p11(patch[4]),.p12(patch[5]),
        .p20(patch[6]),.p21(patch[7]),.p22(patch[8]),
        .threshold(threshold),.out_valid(sobel_valid),
        .magnitude(sobel_magnitude),.edge_bit(sobel_edge));
    always @(posedge clk) begin
        if(!core_resetn) begin
            state<=IDLE; start_old<=0; busy<=0; done<=0;
            frame_id<=0;error_code<=0;threshold<=80;
            write_index<=0;output_index<=0;x<=0;y<=0;
            x0<=0;y0<=0;x1<=WIDTH;y1<=HEIGHT;
            output_word<=0;load_row<=0;load_col<=0;load_bank<=0;
            top_bank<=0;prime_col<=0;rows_initialized<=0;rows_ready<=0;window_ready<=0;
        end else begin
            start_old<=ps_control[1];
            case(state)
                IDLE: if(ps_control[1] && !start_old) begin
                    frame_id<=frame_id+1'b1;threshold<=ps_control[15:8];
                    x0<=roi_config[7:0];y0<=roi_config[15:8];
                    x1<=roi_config[23:16];y1<=roi_config[31:24];
                    error_code<=0;
                    if(roi_config[7:0]>=roi_config[23:16] || roi_config[15:8]>=roi_config[31:24] ||
                        roi_config[23:16]>WIDTH || roi_config[31:24]>HEIGHT) error_code<=2;
                    busy<=1;done<=0;write_index<=0;output_index<=0;x<=0;y<=0;
                    roi_edge_count<=0;roi_edge_y_sum<=0;
                    top_bank<=0;rows_initialized<=0;rows_ready<=0;window_ready<=0;
                    state<=RECEIVE;
                end
                RECEIVE: if(s_axis_tvalid && s_axis_tready) begin
                    if(s_axis_tkeep!=4'hf || s_axis_tdata[31:8]!=0 || s_axis_tlast!=(write_index==PIXELS-1))
                        error_code<=1;
                    if(write_index==PIXELS-1) state<=PREPARE;
                    else write_index<=write_index+1'b1;
                end
                PREPARE: begin
                    if(x==0 || x==WIDTH-1 || y==0 || y==HEIGHT-1) begin
                        output_word<=0;state<=SEND;
                    end else if(!rows_ready) begin
                        load_col<=0;
                        if(!rows_initialized) begin load_row<=0;load_bank<=0;end
                        else begin
                            load_row<=y+1'b1;
                            load_bank<=top_bank==0 ? 2 : top_bank==1 ? 0 : 1;
                        end
                        state<=LOAD_ADDR;
                    end else if(!window_ready) begin prime_col<=0;state<=PRIME;end
                    else begin
                        patch[0]<=patch[1];patch[1]<=patch[2];patch[2]<=a;
                        patch[3]<=patch[4];patch[4]<=patch[5];patch[5]<=b;
                        patch[6]<=patch[7];patch[7]<=patch[8];patch[8]<=c;
                        state<=FIRE;
                    end
                end
                LOAD_ADDR: state<=LOAD_STORE;
                LOAD_STORE: begin
                    if(load_col==WIDTH-1) begin
                        load_col<=0;
                        if(!rows_initialized && load_row!=2) begin
                            load_row<=load_row+1'b1;load_bank<=load_bank+1'b1;state<=LOAD_ADDR;
                        end else begin rows_initialized<=1;rows_ready<=1;state<=PREPARE;end
                    end else begin load_col<=load_col+1'b1;state<=LOAD_ADDR;end
                end
                PRIME: begin
                    patch[0]<=patch[1];patch[1]<=patch[2];patch[2]<=a;
                    patch[3]<=patch[4];patch[4]<=patch[5];patch[5]<=b;
                    patch[6]<=patch[7];patch[7]<=patch[8];patch[8]<=c;
                    if(prime_col==2) begin window_ready<=1;state<=FIRE;end
                    else prime_col<=prime_col+1'b1;
                end
                FIRE: state<=RESULT;
                RESULT: if(sobel_valid) begin
                    output_word<={16'd0, (sobel_magnitude>255 ? 8'd255 : sobel_magnitude[7:0]), (sobel_edge ? 8'd255 : 8'd0)};
                    if(sobel_edge && inside_roi) begin
                        roi_edge_count<=roi_edge_count+1'b1;roi_edge_y_sum<=roi_edge_y_sum+y;
                    end
                    state<=SEND;
                end
                SEND: if(m_axis_tready) begin
                    if(output_index==PIXELS-1) begin done<=1;busy<=0;state<=IDLE;end
                    else begin
                        output_index<=output_index+1'b1;
                        if(x==WIDTH-1) begin
                            x<=0;y<=y+1'b1;rows_ready<=0;window_ready<=0;
                            if(y>=1 && y<HEIGHT-2) top_bank<=top_bank==2 ? 0 : top_bank+1'b1;
                        end else x<=x+1'b1;
                        state<=PREPARE;
                    end
                end
                default: begin state<=IDLE;busy<=0;error_code<=4;end
            endcase
        end
    end
endmodule
