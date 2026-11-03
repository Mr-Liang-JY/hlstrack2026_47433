`timescale 1ns/1ps
module camera_video(
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME ref_clk, FREQ_HZ 100000000, ASSOCIATED_RESET resetn" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 ref_clk CLK" *) input wire ref_clk,
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME pixel_clk, FREQ_HZ 25200000" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 pixel_clk CLK" *) input wire pixel_clk,
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME serial_clk, FREQ_HZ 126000000" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 serial_clk CLK" *) input wire serial_clk,
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME xclk_24, FREQ_HZ 24000000" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 xclk_24 CLK" *) input wire xclk_24,
    input wire resetn,input wire locked,input wire camera_locked,input wire button_reset,
    input wire hdmi_hpd_n,input wire [31:0] control,
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME cam_pclk, FREQ_HZ 48000000" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 cam_pclk CLK" *) input wire cam_pclk,
    input wire cam_vsync,input wire cam_href,input wire [7:0] cam_data,
    inout wire cam_scl,inout wire cam_sda,inout wire cam_reset_n,
    output wire cam_xclk,output wire cam_pwdn,
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME hdmi_clk_p, FREQ_HZ 25200000" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 hdmi_clk_p CLK" *) output wire hdmi_clk_p,
    (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME hdmi_clk_n, FREQ_HZ 25200000" *)
    (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 hdmi_clk_n CLK" *) output wire hdmi_clk_n,
    output wire [2:0] hdmi_data_p,output wire [2:0] hdmi_data_n,
    output wire [3:0] leds,output wire [31:0] status,
    output wire [31:0] count_good,count_bad,count_drop,count_shown,count_pclk
);
    wire global_arst=!resetn || button_reset;
    wire lock_ref,camlock_ref;
    wire video_rst;
    reset_sync vr(pixel_clk,global_arst || !locked,video_rst);
    wire clock_enabled;
    cdc_bit ce(xclk_24,global_arst || !camera_locked,control[0],clock_enabled);
    ODDR #(.DDR_CLK_EDGE("SAME_EDGE"),.INIT(1'b0),.SRTYPE("SYNC"))
        xclock_output(.C(xclk_24),.CE(1'b1),.D1(1'b1),.D2(1'b0),
            .R(!clock_enabled),.S(1'b0),.Q(cam_xclk));
    wire scl_in,sda_in;
    IOBUF scl_buffer(.I(1'b0),.T(!control[2] || global_arst),.O(scl_in),.IO(cam_scl));
    IOBUF sda_buffer(.I(1'b0),.T(!control[3] || global_arst),.O(sda_in),.IO(cam_sda));
    IOBUF reset_buffer(.I(1'b0),.T(control[0] && control[1] && !global_arst),.O(),.IO(cam_reset_n));
    assign cam_pwdn=1'b0;
    // Register decoded PS requests before crossing into reset synchronizers.
    // Synchronize the control-domain reset too, then generate requests synchronously.
    wire control_domain_rst;
    reset_sync rs(ref_clk,global_arst,control_domain_rst);
    reg capture_request_reset=1'b1,pclk_request_reset=1'b1;
    always @(posedge ref_clk) begin
        if(control_domain_rst) begin capture_request_reset<=1'b1;pclk_request_reset<=1'b1;end
        else begin
            capture_request_reset<=!control[0] || !control[1] || !control[5] || !lock_ref || !camlock_ref;
            pclk_request_reset<=!control[0];
        end
    end
    wire capture_arst=capture_request_reset;
    wire capture_rst,pixel_buffer_rst;
    reset_sync cr(cam_pclk,capture_arst,capture_rst);
    reset_sync br(pixel_clk,capture_arst,pixel_buffer_rst);
    wire swap_cam;
    cdc_bit swap_cross(cam_pclk,capture_rst,control[4],swap_cam);
    wire [9:0] x,y;
    wire de,hs,vs,frame_end,heartbeat;
    wire [23:0] fallback_rgb;
    video_timing timing(pixel_clk,video_rst,x,y,de,hs,vs,frame_end);
    test_pattern pattern(pixel_clk,video_rst,frame_end,x,y,de,fallback_rgb,heartbeat);
    wire [16:0] read_index=de ? (y[9:1]*17'd320)+x[9:1] : 17'd0;
    wire [15:0] rgb565;
    (* IOB="TRUE" *) reg [7:0] sensor_data_q;
    (* IOB="TRUE" *) reg sensor_href_q,sensor_vsync_q;
    always @(posedge cam_pclk) begin
        sensor_data_q<=cam_data;sensor_href_q<=cam_href;sensor_vsync_q<=cam_vsync;
    end
    wire display_valid;
    wire [31:0] good_cam,bad_cam,drop_cam,shown_pixel;
    dvp_framebuffer fb(cam_pclk,capture_rst,sensor_data_q,sensor_href_q,sensor_vsync_q,swap_cam,
        pixel_clk,pixel_buffer_rst,frame_end,read_index,rgb565,display_valid,
        good_cam,bad_cam,drop_cam,shown_pixel);
    reg [31:0] pclk_ticks;
    wire pclk_reset;
    reset_sync pr(cam_pclk,pclk_request_reset,pclk_reset);
    always @(posedge cam_pclk or posedge pclk_reset)
        if(pclk_reset) pclk_ticks<=0;else pclk_ticks<=pclk_ticks+1'b1;
    cdc_counter cg(cam_pclk,capture_rst,good_cam,ref_clk,global_arst,count_good);
    cdc_counter cb(cam_pclk,capture_rst,bad_cam,ref_clk,global_arst,count_bad);
    cdc_counter cd(cam_pclk,capture_rst,drop_cam,ref_clk,global_arst,count_drop);
    cdc_counter cs(pixel_clk,pixel_buffer_rst,shown_pixel,ref_clk,global_arst,count_shown);
    cdc_counter cp(cam_pclk,pclk_reset,pclk_ticks,ref_clk,global_arst,count_pclk);
    reg de_d,hs_d,vs_d,valid_d,border_d;
    reg [23:0] fallback_d;
    always @(posedge pixel_clk) begin
        if(video_rst) begin de_d<=0;hs_d<=1;vs_d<=1;valid_d<=0;border_d<=0;fallback_d<=0;end
        else begin
            de_d<=de;hs_d<=hs;vs_d<=vs;valid_d<=display_valid;
            border_d<=(x<2 || x>=638 || y<2 || y>=478);
            fallback_d<=fallback_rgb;
        end
    end
    wire [23:0] camera_rgb={rgb565[15:11],rgb565[15:13],rgb565[10:5],rgb565[10:9],rgb565[4:0],rgb565[4:2]};
    wire [23:0] rgb=valid_d ? (border_d ? 24'h00ff00 : camera_rgb) : fallback_d;
    wire [9:0] encoded[0:2];
    tmds_encoder blue(pixel_clk,video_rst,rgb[7:0],de_d,hs_d,vs_d,encoded[0]);
    tmds_encoder green(pixel_clk,video_rst,rgb[15:8],de_d,1'b0,1'b0,encoded[1]);
    tmds_encoder red(pixel_clk,video_rst,rgb[23:16],de_d,1'b0,1'b0,encoded[2]);
    wire [2:0] data_serial;wire clock_serial;
    genvar k;
    generate for(k=0;k<3;k=k+1) begin:channels
        serializer_10to1 ser(pixel_clk,serial_clk,video_rst,encoded[k],data_serial[k]);
        OBUFDS #(.IOSTANDARD("TMDS_33"),.SLEW("FAST")) db(.I(data_serial[k]),.O(hdmi_data_p[k]),.OB(hdmi_data_n[k]));
    end endgenerate
    serializer_10to1 cser(pixel_clk,serial_clk,video_rst,10'b0000011111,clock_serial);
    OBUFDS #(.IOSTANDARD("TMDS_33"),.SLEW("FAST")) ck(.I(clock_serial),.O(hdmi_clk_p),.OB(hdmi_clk_n));
    wire hpd_ref,alive_ref,valid_ref,scl_ref,sda_ref,run_ref;
    cdc_bit dh(ref_clk,global_arst,!hdmi_hpd_n,hpd_ref);
    cdc_bit da(ref_clk,global_arst,heartbeat,alive_ref);
    cdc_bit dv(ref_clk,global_arst,display_valid,valid_ref);
    cdc_bit dscl(ref_clk,global_arst,scl_in,scl_ref);
    cdc_bit dsda(ref_clk,global_arst,sda_in,sda_ref);
    cdc_bit dr(ref_clk,global_arst,!video_rst,run_ref);
    cdc_bit dl(ref_clk,global_arst,locked,lock_ref);
    cdc_bit dcl(ref_clk,global_arst,camera_locked,camlock_ref);
    assign leds={alive_ref,valid_ref,hpd_ref,lock_ref};
    assign status={16'hCA02,7'b0,valid_ref,sda_ref,scl_ref,control[5],camlock_ref,alive_ref,hpd_ref,run_ref,lock_ref};
endmodule
