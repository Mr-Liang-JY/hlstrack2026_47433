`timescale 1ns/1ps
// Two-row streaming Sobel, four elastic arithmetic stages, zero output border.
module sobel_frame_axis #(parameter integer WIDTH=128,HEIGHT=128)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK" *)
 (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME clk, ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET resetn, FREQ_HZ 100000000" *) input wire clk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 resetn RST" *)
 (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *) input wire resetn,
 input wire [31:0] ps_control,roi_config,output wire [31:0] pl_status,
 output reg [31:0] roi_edge_count,roi_edge_y_sum,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
 (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME S_AXIS, TDATA_NUM_BYTES 4, HAS_TKEEP 1, HAS_TLAST 1, HAS_TREADY 1" *) input wire [31:0] s_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TKEEP" *) input wire [3:0] s_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TLAST" *) input wire s_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TVALID" *) input wire s_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TREADY" *) output wire s_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
 (* X_INTERFACE_PARAMETER="XIL_INTERFACENAME M_AXIS, TDATA_NUM_BYTES 4, HAS_TKEEP 1, HAS_TLAST 1, HAS_TREADY 1" *) output wire [31:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TKEEP" *) output wire [3:0] m_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TLAST" *) output wire m_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TVALID" *) output wire m_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TREADY" *) input wire m_axis_tready
);
 localparam integer PIXELS=WIDTH*HEIGHT;
 localparam IDLE=0,RECEIVE=1,FLUSH=2,DRAIN=3;
 wire core_resetn=resetn && ps_control[0];
 reg [1:0] state;reg start_old,busy,done;
 reg [3:0] frame_id,error_code;reg [7:0] threshold,x0,y0,x1,y1;
 reg [15:0] input_index,emit_index;reg [7:0] input_x,emit_x,emit_y;reg [8:0] tail_left;
 (* ram_style="distributed" *) reg [7:0] row1[0:WIDTH-1],row2[0:WIDTH-1];
 reg [7:0] top0,top1,mid0,mid1,bot0,bot1;
 wire [7:0] top=row2[input_x],middle=row1[input_x],bottom=s_axis_tdata[7:0];
 reg [3:0] valid_pipe,border_pipe,last_pipe,roi_pipe;reg [7:0] y_pipe[0:3];
 reg [9:0] left_sum,right_sum,top_sum,bottom_sum;reg signed [10:0] gx,gy;
 reg [10:0] total,magnitude;reg [7:0] threshold1,threshold2,threshold3;reg edge_bit;
 wire [10:0] abs_gx=gx[10] ? -gx : gx,abs_gy=gy[10] ? -gy : gy;
 wire advance=!valid_pipe[3] || m_axis_tready;
 assign s_axis_tready=core_resetn && state==RECEIVE && advance;
 wire accept=s_axis_tvalid && s_axis_tready;
 wire emit=advance && ((accept && input_index>=WIDTH+1) || state==FLUSH);
 wire border=state==FLUSH || emit_x==0 || emit_x==WIDTH-1 || emit_y==0 || emit_y==HEIGHT-1;
 wire inside_roi=emit_x>=x0 && emit_x<x1 && emit_y>=y0 && emit_y<y1;
 assign m_axis_tvalid=core_resetn && valid_pipe[3];assign m_axis_tkeep=4'hf;assign m_axis_tlast=last_pipe[3];
 wire [7:0] out_magnitude=border_pipe[3] ? 0 : magnitude>255 ? 255 : magnitude[7:0];
 wire out_edge=!border_pipe[3] && edge_bit;
 assign m_axis_tdata={16'd0,out_magnitude,(out_edge ? 8'd255 : 8'd0)};
 assign pl_status={4'hd,frame_id,error_code,18'd0,busy,done};
 integer k;
 always @(posedge clk) begin
  if(accept) begin row2[input_x]<=middle;row1[input_x]<=bottom;end
  if(!core_resetn) begin
   state<=IDLE;start_old<=0;busy<=0;done<=0;frame_id<=0;error_code<=0;
   threshold<=80;x0<=0;y0<=0;x1<=WIDTH;y1<=HEIGHT;
   input_index<=0;emit_index<=0;input_x<=0;emit_x<=0;emit_y<=0;tail_left<=0;
   top0<=0;top1<=0;mid0<=0;mid1<=0;bot0<=0;bot1<=0;
   valid_pipe<=0;border_pipe<=0;last_pipe<=0;roi_pipe<=0;
   left_sum<=0;right_sum<=0;top_sum<=0;bottom_sum<=0;gx<=0;gy<=0;total<=0;
   magnitude<=0;edge_bit<=0;threshold1<=0;threshold2<=0;threshold3<=0;
   roi_edge_count<=0;roi_edge_y_sum<=0;for(k=0;k<4;k=k+1)y_pipe[k]<=0;
  end else begin
   start_old<=ps_control[1];
   if(advance) begin
    valid_pipe<={valid_pipe[2:0],emit};border_pipe<={border_pipe[2:0],border};
    last_pipe<={last_pipe[2:0],emit_index==PIXELS-1};roi_pipe<={roi_pipe[2:0],inside_roi};
    y_pipe[0]<=emit_y;for(k=1;k<4;k=k+1)y_pipe[k]<=y_pipe[k-1];
    if(emit) begin
     right_sum<={2'b0,top}+{1'b0,middle,1'b0}+{2'b0,bottom};
     left_sum<={2'b0,top0}+{1'b0,mid0,1'b0}+{2'b0,bot0};
     bottom_sum<={2'b0,bot0}+{1'b0,bot1,1'b0}+{2'b0,bottom};
     top_sum<={2'b0,top0}+{1'b0,top1,1'b0}+{2'b0,top};threshold1<=threshold;
    end
    if(valid_pipe[0]) begin gx<=$signed({1'b0,right_sum})-$signed({1'b0,left_sum});gy<=$signed({1'b0,bottom_sum})-$signed({1'b0,top_sum});threshold2<=threshold1;end
    if(valid_pipe[1]) begin total<=abs_gx+abs_gy;threshold3<=threshold2;end
    if(valid_pipe[2]) begin magnitude<=total;edge_bit<=total>={3'd0,threshold3};end
    if(emit) begin
     emit_index<=emit_index+1'b1;
     if(emit_x==WIDTH-1) begin emit_x<=0;emit_y<=emit_y+1'b1;end else emit_x<=emit_x+1'b1;
    end
   end
   if(accept) begin
    top0<=top1;top1<=top;mid0<=mid1;mid1<=middle;bot0<=bot1;bot1<=bottom;
    if(s_axis_tkeep!=15 || s_axis_tdata[31:8]!=0 || s_axis_tlast!=(input_index==PIXELS-1))error_code<=1;
    if(input_x==WIDTH-1)input_x<=0;else input_x<=input_x+1'b1;
    if(input_index==PIXELS-1)begin state<=FLUSH;tail_left<=WIDTH+1;end else input_index<=input_index+1'b1;
   end
   if(state==FLUSH && advance)begin tail_left<=tail_left-1'b1;if(tail_left==1)state<=DRAIN;end
   if(m_axis_tvalid && m_axis_tready)begin
    if(out_edge && roi_pipe[3])begin roi_edge_count<=roi_edge_count+1'b1;roi_edge_y_sum<=roi_edge_y_sum+y_pipe[3];end
    if(m_axis_tlast)begin state<=IDLE;busy<=0;done<=1;end
   end
   if(state==IDLE && ps_control[1] && !start_old)begin
    threshold<=ps_control[15:8];frame_id<=frame_id+1'b1;busy<=1;done<=0;error_code<=0;
    x0<=roi_config[7:0];y0<=roi_config[15:8];x1<=roi_config[23:16];y1<=roi_config[31:24];
    if(roi_config[7:0]>=roi_config[23:16] || roi_config[15:8]>=roi_config[31:24] || roi_config[23:16]>WIDTH || roi_config[31:24]>HEIGHT)error_code<=2;
    input_index<=0;input_x<=0;emit_index<=0;emit_x<=0;emit_y<=0;roi_edge_count<=0;roi_edge_y_sum<=0;valid_pipe<=0;state<=RECEIVE;
   end
  end
 end
endmodule
