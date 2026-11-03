`timescale 1ns/1ps
module video_display(
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 ref_clk CLK" *)
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME ref_clk, FREQ_HZ 100000000, ASSOCIATED_BUSIF S_AXIS, ASSOCIATED_RESET resetn" *)
    input wire ref_clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 pixel_clk CLK" *)
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME pixel_clk, FREQ_HZ 74250000" *)
    input wire pixel_clk,
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 serial_clk CLK" *)
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME serial_clk, FREQ_HZ 371250000" *)
    input wire serial_clk,
    input wire resetn, input wire locked, input wire button_reset,
    input wire hdmi_hpd_n, input wire [31:0] control,
    output wire [31:0] status, output wire [3:0] leds,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME S_AXIS, TDATA_NUM_BYTES 4, HAS_TKEEP 1, HAS_TLAST 1, HAS_TREADY 1" *)
    input wire [31:0] s_axis_tdata,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TKEEP" *) input wire [3:0] s_axis_tkeep,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TVALID" *) input wire s_axis_tvalid,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TLAST" *) input wire s_axis_tlast,
    (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TREADY" *) output wire s_axis_tready,
    output wire hdmi_clk_p, output wire hdmi_clk_n,
    output wire [2:0] hdmi_data_p, output wire [2:0] hdmi_data_n
);
    wire rst,ref_rst;
    reset_sync pr(pixel_clk, !resetn || !locked || button_reset, rst);
    reset_sync rr(ref_clk, !resetn || !locked || button_reset, ref_rst);
    wire [10:0] x; wire [9:0] y;
    wire de,hs,vs,frame_end,have_frame,pending,error;
    wire [15:0] presented;
    wire [31:0] read_data;
    wire [15:0] address=de ? ((y>>1)*160+(x>>3)) : 16'd0;
    video_timing timing(pixel_clk,rst,x,y,de,hs,vs,frame_end);
    axis_framebuffer frame_store(
        .clk(ref_clk),.resetn(!ref_rst),.data(s_axis_tdata),.keep(s_axis_tkeep),
        .valid(s_axis_tvalid),.last(s_axis_tlast),.ready(s_axis_tready),
        .pending(pending),.protocol_error(error),.presented(presented),
        .pixel_clk(pixel_clk),.pixel_reset(rst),.vblank_start(x==0 && y==720),
        .read_address(address),.read_data(read_data),.have_frame(have_frame));
    // Synchronous BRAM read: delay coordinates/control by exactly one cycle.
    reg [1:0] byte_lane; reg de_d,hs_d,vs_d;
    (* ASYNC_REG="TRUE" *) reg [1:0] enable_sync;
    reg heartbeat; reg [5:0] frame_counter;
    always @(posedge pixel_clk) begin
        if(rst) begin
            byte_lane<=0;de_d<=0;hs_d<=0;vs_d<=0;enable_sync<=0;
            heartbeat<=0;frame_counter<=0;
        end else begin
            enable_sync<={enable_sync[0],control[0]};
            byte_lane<=x[2:1];de_d<=de;hs_d<=hs;vs_d<=vs;
            if(frame_end) begin
                if(frame_counter==29) begin frame_counter<=0;heartbeat<=~heartbeat;end
                else frame_counter<=frame_counter+1'b1;
            end
        end
    end
    reg [7:0] gray;
    always @* begin
        case(byte_lane)
            0:gray=read_data[7:0];1:gray=read_data[15:8];
            2:gray=read_data[23:16];3:gray=read_data[31:24];
        endcase
        if(!have_frame || !enable_sync[1]) gray=0;
    end
    // Separate the large BRAM output mux from TMDS disparity arithmetic.
    // Video control gets the same extra latency as the pixel data.
    reg [7:0] gray_pixel;reg de_q,hs_q,vs_q;
    always @(posedge pixel_clk) begin
        if(rst) begin gray_pixel<=0;de_q<=0;hs_q<=0;vs_q<=0;end
        else begin gray_pixel<=gray;de_q<=de_d;hs_q<=hs_d;vs_q<=vs_d;end
    end
    wire [9:0] encoded [0:2];
    tmds_encoder blue(pixel_clk,rst,gray_pixel,de_q,hs_q,vs_q,encoded[0]);
    tmds_encoder green(pixel_clk,rst,gray_pixel,de_q,1'b0,1'b0,encoded[1]);
    tmds_encoder red(pixel_clk,rst,gray_pixel,de_q,1'b0,1'b0,encoded[2]);
    wire [2:0] serial_data; wire clock_serial;
    genvar k;
    generate for(k=0;k<3;k=k+1) begin: channels
        serializer_10to1 ser(pixel_clk,serial_clk,rst,encoded[k],serial_data[k]);
        OBUFDS #(.IOSTANDARD("TMDS_33"),.SLEW("FAST"))
            dbuf(.I(serial_data[k]),.O(hdmi_data_p[k]),.OB(hdmi_data_n[k]));
    end endgenerate
    serializer_10to1 clock_ser(pixel_clk,serial_clk,rst,10'b0000011111,clock_serial);
    OBUFDS #(.IOSTANDARD("TMDS_33"),.SLEW("FAST")) cb(.I(clock_serial),.O(hdmi_clk_p),.OB(hdmi_clk_n));
    (* ASYNC_REG="TRUE" *) reg [1:0] hpd_sync,alive_sync,rstn_sync,lock_sync,have_sync;
    always @(posedge ref_clk) begin
        if(!resetn) begin
            hpd_sync<=3;alive_sync<=0;rstn_sync<=0;lock_sync<=0;have_sync<=0;
        end else begin
            hpd_sync<={hpd_sync[0],hdmi_hpd_n};alive_sync<={alive_sync[0],heartbeat};
            rstn_sync<={rstn_sync[0],!rst};lock_sync<={lock_sync[0],locked};
            have_sync<={have_sync[0],have_frame};
        end
    end
    assign leds={alive_sync[1],!hpd_sync[1],rstn_sync[1],lock_sync[1]};
    assign status={8'ha7,presented,error,pending,have_sync[1],alive_sync[1],
                   !hpd_sync[1],rstn_sync[1],lock_sync[1],control[0]};
endmodule
