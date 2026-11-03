`timescale 1ns/1ps
// Two RGB565 frame banks. Camera cannot be stalled: discard an entire frame
// when no bank is free. Publish only after a complete, geometrically valid frame.
module dvp_framebuffer #(parameter WIDTH=320,HEIGHT=240)(
    input wire cam_pclk,input wire cam_rst,input wire [7:0] cam_data,
    input wire cam_href,input wire cam_vsync,input wire byte_swap,
    input wire pixel_clk,input wire pixel_rst,input wire display_frame_end,
    input wire [$clog2(WIDTH*HEIGHT)-1:0] read_index,
    output reg [15:0] read_pixel,output reg display_valid,
    output reg [31:0] good_frames,output reg [31:0] bad_frames,
    output reg [31:0] dropped_frames,output reg [31:0] displayed_frames
);
    localparam PIXELS=WIDTH*HEIGHT;
    localparam AW=$clog2(PIXELS);
    (* ram_style="block" *) reg [15:0] memory[0:2*PIXELS-1];
    reg write_bank,pending_bank,request_toggle,pending_busy;
    reg acknowledge_toggle;
    wire ack_cam,request_pixel,bank_pixel;
    reg request_safe;
    cdc_bit ack_cross(cam_pclk,cam_rst,acknowledge_toggle,ack_cam);
    cdc_bit request_cross(pixel_clk,pixel_rst,request_toggle,request_pixel);
    cdc_bit bank_cross(pixel_clk,pixel_rst,pending_bank,bank_pixel);
    reg display_bank;
    reg seen_vsync,vs_d,hs_d,phase,have_pixels,skip_frame,bad_geometry,capture_frame;
    reg [7:0] first_byte;
    reg [15:0] line_pixels,lines;
    reg [AW:0] words;
    reg wr_en;
    reg [AW:0] wr_address;
    reg [15:0] wr_pixel;
    wire bank_free=!pending_busy || (ack_cam==request_toggle);
    // No memory reset: clearing all 153600 words would prevent BRAM inference.
    always @(posedge cam_pclk) if(wr_en) memory[wr_address]<=wr_pixel;
    always @(posedge pixel_clk)
        read_pixel<=memory[read_index+(display_bank ? PIXELS : 0)];

    // Synchronous resets keep BRAM address/enable registers stable between edges.
    // cam_rst itself asserts asynchronously and releases through reset_sync.
    always @(posedge cam_pclk) begin
        if(cam_rst) begin
            write_bank<=0;pending_bank<=0;request_toggle<=0;pending_busy<=0;
            seen_vsync<=0;vs_d<=0;hs_d<=0;phase<=0;have_pixels<=0;
            skip_frame<=0;bad_geometry<=0;capture_frame<=0;first_byte<=0;
            line_pixels<=0;lines<=0;words<=0;wr_en<=0;wr_address<=0;wr_pixel<=0;
            good_frames<=0;bad_frames<=0;dropped_frames<=0;
        end else begin
            vs_d<=cam_vsync;hs_d<=cam_href;wr_en<=0;
            if(pending_busy && ack_cam==request_toggle) begin
                pending_busy<=0;write_bank<=!pending_bank;
            end
            // Both VSYNC edges are safe boundaries when HREF is inactive.
            // This accepts either VSYNC polarity without guessing its meaning.
            if(cam_vsync!=vs_d && !cam_href) begin
                if(seen_vsync && have_pixels && !skip_frame) begin
                    if(!bad_geometry && !phase && lines==HEIGHT && words==PIXELS) begin
                        pending_bank<=write_bank;request_toggle<=!request_toggle;
                        pending_busy<=1;good_frames<=good_frames+1'b1;
                    end else bad_frames<=bad_frames+1'b1;
                end
                seen_vsync<=1;phase<=0;have_pixels<=0;skip_frame<=0;
                bad_geometry<=0;capture_frame<=0;line_pixels<=0;lines<=0;words<=0;
            end else if(seen_vsync) begin
                if(cam_href) begin
                    if(!have_pixels) begin
                        have_pixels<=1;
                        capture_frame<=bank_free;
                        if(!bank_free) begin skip_frame<=1;dropped_frames<=dropped_frames+1'b1;end
                    end
                    if(!phase) begin first_byte<=cam_data;phase<=1;end
                    else begin
                        phase<=0;
                        if(line_pixels!=16'hffff) line_pixels<=line_pixels+1'b1;
                        if(words<PIXELS+1) words<=words+1'b1;
                        if(capture_frame && !skip_frame && lines<HEIGHT && line_pixels<WIDTH && words<PIXELS) begin
                            wr_en<=1;
                            wr_address<=words+(write_bank ? PIXELS : 0);
                            wr_pixel<=byte_swap ? {cam_data,first_byte} : {first_byte,cam_data};
                        end
                    end
                end else if(hs_d) begin
                    if(phase || line_pixels!=WIDTH || lines>=HEIGHT) bad_geometry<=1;
                    phase<=0;line_pixels<=0;
                    if(lines!=16'hffff) lines<=lines+1'b1;
                end
            end
        end
    end
    always @(posedge pixel_clk) begin
        if(pixel_rst) begin
            display_bank<=1;display_valid<=0;acknowledge_toggle<=0;displayed_frames<=0;request_safe<=0;
        end else begin
            // One extra control cycle lets the separately synchronized bank bit settle.
            request_safe<=request_pixel;
            if(display_frame_end && request_safe!=acknowledge_toggle) begin
                display_bank<=bank_pixel;display_valid<=1;
                acknowledge_toggle<=request_safe;displayed_frames<=displayed_frames+1'b1;
            end
        end
    end
endmodule
