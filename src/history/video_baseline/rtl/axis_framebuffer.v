`timescale 1ns/1ps
// Packed uint8 grayscale: low byte is the leftmost pixel, one TLAST/frame.
// Writer and reader never own the same bank. Single-bit toggle handshake
// publishes a COMPLETE bank only during vertical blanking. The request is
// held stable until acknowledgment; no multi-bit bank/address CDC is needed.
module axis_framebuffer #(
    parameter integer WORDS=57600,
    parameter integer AW=16
)(
    input wire clk, input wire resetn,
    input wire [31:0] data, input wire [3:0] keep,
    input wire valid, input wire last, output wire ready,
    output wire pending, output reg protocol_error,
    output reg [15:0] presented,
    input wire pixel_clk, input wire pixel_reset,
    input wire vblank_start, input wire [AW-1:0] read_address,
    output wire [31:0] read_data, output reg have_frame
);
    (* ram_style="block" *) reg [31:0] bank0[0:WORDS-1];
    (* ram_style="block" *) reg [31:0] bank1[0:WORDS-1];
    reg [AW-1:0] write_address;
    reg [31:0] bank0_read,bank1_read;
    reg request, acknowledgment, write_bank, ack_seen, bad_frame;
    (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync, req_sync;
    assign pending=request!=ack_sync[1] || ack_seen!=ack_sync[1];
    assign ready=resetn && !pending;
    always @(posedge clk) begin
        if (valid && ready && write_address<WORDS) begin
            if(write_bank) bank1[write_address]<=data;
            else bank0[write_address]<=data;
        end
        if(!resetn) begin
            write_address<=0;request<=0;write_bank<=1;ack_sync<=0;
            ack_seen<=0;bad_frame<=0;protocol_error<=0;presented<=0;
        end else begin
            ack_sync<={ack_sync[0], acknowledgment};
            if(ack_sync[1]!=ack_seen) begin
                ack_seen<=ack_sync[1];
                write_bank<=~write_bank;
                presented<=presented+1'b1;
            end
            if(valid && ready) begin
                if(keep!=4'hf || write_address>=WORDS) bad_frame<=1;
                if(last) begin
                    write_address<=0;
                    if(write_address==WORDS-1 && keep==4'hf && !bad_frame)
                        request<=~request;
                    else protocol_error<=1;
                    bad_frame<=0;
                end else begin
                    if(write_address<WORDS) write_address<=write_address+1'b1;
                    else bad_frame<=1;
                end
            end
        end
    end
    // Include ack_seen in readiness to avoid accepting a first word into
    // the old write bank on the cycle that the ack synchronizer changes.
    // The extra cycle is intentionally handled by the pending output below.
    // Keep one independent synchronous read register per RAM. Mux AFTER
    // these registers: muxing two arrays before a shared register can prevent
    // block-RAM inference and create an impractically large LUT memory.
    always @(posedge pixel_clk) bank0_read<=bank0[read_address];
    always @(posedge pixel_clk) bank1_read<=bank1[read_address];
    assign read_data=acknowledgment ? bank1_read : bank0_read;
    always @(posedge pixel_clk) begin
        if(pixel_reset) begin req_sync<=0;acknowledgment<=0;have_frame<=0;end
        else begin
            req_sync<={req_sync[0],request};
            if(vblank_start && req_sync[1]!=acknowledgment) begin
                acknowledgment<=req_sync[1];have_frame<=1;
            end
        end
    end
endmodule
