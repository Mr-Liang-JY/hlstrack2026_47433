# Source in Vivado Tcl Console with other projects closed. All paths are relative to this script.
set lab_root [file dirname [file dirname [file normalize [info script]]]]
set lab_name video_stage3
set lab_dir [file join $lab_root build $lab_name]
if {[llength [get_projects -quiet]]} {error "Save and close the current Vivado project first."}
set_param board.repoPaths [concat [get_param board.repoPaths] [list [file join $lab_root board_files]]]
if {[file exists [file join $lab_dir ${lab_name}.xpr]]} {
    open_project [file join $lab_dir ${lab_name}.xpr]
    puts "Existing Day9 project opened. Source scripts/build_bitstream.tcl to continue."
    return
}
if {![llength [get_parts -quiet xc7z020clg400-1]]} {error "Install Zynq-7000 device support."}
proc lab_ip {pattern} {
    set names [lsort -dictionary [get_ipdefs -all -quiet $pattern]]
    if {![llength $names]} {error "Missing required IP: $pattern"}
    return [lindex $names end]
}
create_project $lab_name $lab_dir -part xc7z020clg400-1
set boards [get_board_parts -quiet *pynq-z2*]
if {![llength $boards]} {error "Bundled PYNQ-Z2 board definition not recognized."}
set_property board_part [lindex $boards 0] [current_project]
set_property target_language Verilog [current_project]
set_param general.maxThreads 2
add_files -norecurse [glob [file join $lab_root rtl *.v]]
add_files -fileset constrs_1 -norecurse [glob [file join $lab_root constraints *.xdc]]
update_compile_order -fileset sources_1
create_bd_design system
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:processing_system7:*] processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1"} [get_bd_cells processing_system7_0]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000}] [get_bd_cells processing_system7_0]

create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_dma:*] axi_dma_0
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {1} \
    CONFIG.c_sg_length_width {23} CONFIG.c_m_axi_mm2s_data_width {64} \
    CONFIG.c_m_axi_s2mm_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {32} \
    CONFIG.c_s_axis_s2mm_tdata_width {32} CONFIG.c_include_mm2s_dre {0} \
    CONFIG.c_include_s2mm_dre {0}] [get_bd_cells axi_dma_0]

create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_gpio:*] axi_gpio_ctrl
set_property -dict [list CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_ALL_INPUTS {0} CONFIG.C_DOUT_DEFAULT {0x00000000} \
    CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_ALL_OUTPUTS_2 {0} \
    CONFIG.C_INTERRUPT_PRESENT {0}] [get_bd_cells axi_gpio_ctrl]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_gpio:*] axi_gpio_stats
set_property -dict [list CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_INPUTS {1} \
    CONFIG.C_ALL_OUTPUTS {0} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1} \
    CONFIG.C_ALL_OUTPUTS_2 {0} CONFIG.C_INTERRUPT_PRESENT {0}] [get_bd_cells axi_gpio_stats]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_gpio:*] axi_gpio_roi
set_property -dict [list CONFIG.C_IS_DUAL {0} CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_ALL_INPUTS {0} CONFIG.C_INTERRUPT_PRESENT {0}] [get_bd_cells axi_gpio_roi]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_dma:*] display_dma
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {0} \
    CONFIG.c_sg_length_width {23} CONFIG.c_m_axi_mm2s_data_width {64} \
    CONFIG.c_m_axis_mm2s_tdata_width {32} CONFIG.c_include_mm2s_dre {0}] [get_bd_cells display_dma]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_gpio:*] display_control
set_property -dict [list CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_ALL_INPUTS {0} CONFIG.C_DOUT_DEFAULT {0x00000000} \
    CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_ALL_OUTPUTS_2 {0} \
    CONFIG.C_INTERRUPT_PRESENT {0}] [get_bd_cells display_control]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:clk_wiz:*] video_clocks
set_property -dict [list CONFIG.PRIM_IN_FREQ {100.000} CONFIG.PRIMITIVE {MMCM} CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {74.250} CONFIG.CLKOUT2_USED {true} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {371.250} CONFIG.RESET_TYPE {ACTIVE_LOW} CONFIG.USE_LOCKED {true}] [get_bd_cells video_clocks]
create_bd_cell -type module -reference video_display video_display_0
connect_bd_net [get_bd_pins video_clocks/clk_out1] [get_bd_pins video_display_0/pixel_clk]
connect_bd_net [get_bd_pins video_clocks/clk_out2] [get_bd_pins video_display_0/serial_clk]
connect_bd_net [get_bd_pins video_clocks/locked] [get_bd_pins video_display_0/locked]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins video_clocks/clk_in1]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins video_clocks/resetn]
connect_bd_net [get_bd_pins display_control/gpio_io_o] [get_bd_pins video_display_0/control]
connect_bd_net [get_bd_pins video_display_0/status] [get_bd_pins display_control/gpio2_io_i]
foreach pin {button_reset hdmi_hpd_n} {
    create_bd_port -dir I $pin
    connect_bd_net [get_bd_ports $pin] [get_bd_pins video_display_0/$pin]
}
foreach pin {hdmi_clk_p hdmi_clk_n} {
    create_bd_port -dir O $pin
    connect_bd_net [get_bd_ports $pin] [get_bd_pins video_display_0/$pin]
}
foreach {pin msb} {hdmi_data_p 2 hdmi_data_n 2 leds 3} {
    create_bd_port -dir O -from $msb -to 0 $pin
    connect_bd_net [get_bd_ports $pin] [get_bd_pins video_display_0/$pin]
}
create_bd_cell -type module -reference sobel_frame_axis sobel_frame_0
set_property -dict [list CONFIG.WIDTH {128} CONFIG.HEIGHT {128}] [get_bd_cells sobel_frame_0]

create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_interconnect:*] control_interconnect
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {6}] [get_bd_cells control_interconnect]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_interconnect:*] memory_interconnect
set_property -dict [list CONFIG.NUM_SI {3} CONFIG.NUM_MI {1}] [get_bd_cells memory_interconnect]
connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] [get_bd_intf_pins control_interconnect/S00_AXI]
foreach {port target} {M00_AXI axi_dma_0/S_AXI_LITE M01_AXI axi_gpio_ctrl/S_AXI M02_AXI axi_gpio_stats/S_AXI M03_AXI axi_gpio_roi/S_AXI M04_AXI display_dma/S_AXI_LITE M05_AXI display_control/S_AXI} {
    connect_bd_intf_net [get_bd_intf_pins control_interconnect/$port] [get_bd_intf_pins $target]
}
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXI_MM2S] [get_bd_intf_pins memory_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXI_S2MM] [get_bd_intf_pins memory_interconnect/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins display_dma/M_AXI_MM2S] [get_bd_intf_pins memory_interconnect/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins display_dma/M_AXIS_MM2S] [get_bd_intf_pins video_display_0/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins memory_interconnect/M00_AXI] [get_bd_intf_pins processing_system7_0/S_AXI_HP0]
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXIS_MM2S] [get_bd_intf_pins sobel_frame_0/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins sobel_frame_0/M_AXIS] [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]
connect_bd_net [get_bd_pins axi_gpio_ctrl/gpio_io_o] [get_bd_pins sobel_frame_0/ps_control]
connect_bd_net [get_bd_pins sobel_frame_0/pl_status] [get_bd_pins axi_gpio_ctrl/gpio2_io_i]
connect_bd_net [get_bd_pins axi_gpio_roi/gpio_io_o] [get_bd_pins sobel_frame_0/roi_config]
connect_bd_net [get_bd_pins sobel_frame_0/roi_edge_count] [get_bd_pins axi_gpio_stats/gpio_io_i]
connect_bd_net [get_bd_pins sobel_frame_0/roi_edge_y_sum] [get_bd_pins axi_gpio_stats/gpio2_io_i]

create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:proc_sys_reset:*] proc_sys_reset_0
# External reset polarity is inferred from PS FCLK_RESET0_N (read-only in 2024.2).
set_property CONFIG.C_AUX_RESET_HIGH {1} [get_bd_cells proc_sys_reset_0]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:xlconstant:*] const_zero
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] [get_bd_cells const_zero]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:xlconstant:*] const_one
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells const_one]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins const_zero/dout] [get_bd_pins proc_sys_reset_0/aux_reset_in] [get_bd_pins proc_sys_reset_0/mb_debug_sys_rst]
connect_bd_net [get_bd_pins const_one/dout] [get_bd_pins proc_sys_reset_0/dcm_locked]
foreach pin {
    processing_system7_0/M_AXI_GP0_ACLK processing_system7_0/S_AXI_HP0_ACLK
    axi_dma_0/s_axi_lite_aclk axi_dma_0/m_axi_mm2s_aclk axi_dma_0/m_axi_s2mm_aclk
    axi_gpio_ctrl/s_axi_aclk axi_gpio_stats/s_axi_aclk axi_gpio_roi/s_axi_aclk
    sobel_frame_0/clk video_display_0/ref_clk display_dma/s_axi_lite_aclk display_dma/m_axi_mm2s_aclk display_control/s_axi_aclk proc_sys_reset_0/slowest_sync_clk
    control_interconnect/ACLK control_interconnect/S00_ACLK
    control_interconnect/M00_ACLK control_interconnect/M01_ACLK control_interconnect/M02_ACLK control_interconnect/M03_ACLK control_interconnect/M04_ACLK control_interconnect/M05_ACLK
    memory_interconnect/ACLK memory_interconnect/S00_ACLK memory_interconnect/S01_ACLK memory_interconnect/S02_ACLK memory_interconnect/M00_ACLK
} {connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins $pin]}
foreach pin {
    control_interconnect/ARESETN control_interconnect/S00_ARESETN
    control_interconnect/M00_ARESETN control_interconnect/M01_ARESETN control_interconnect/M02_ARESETN control_interconnect/M03_ARESETN control_interconnect/M04_ARESETN control_interconnect/M05_ARESETN
    memory_interconnect/ARESETN memory_interconnect/S00_ARESETN memory_interconnect/S01_ARESETN memory_interconnect/S02_ARESETN memory_interconnect/M00_ARESETN
} {connect_bd_net [get_bd_pins proc_sys_reset_0/interconnect_aresetn] [get_bd_pins $pin]}
foreach pin {axi_dma_0/axi_resetn axi_gpio_ctrl/s_axi_aresetn axi_gpio_stats/s_axi_aresetn axi_gpio_roi/s_axi_aresetn sobel_frame_0/resetn video_display_0/resetn display_dma/axi_resetn display_control/s_axi_aresetn} {
    connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins $pin]
}
assign_bd_address
validate_bd_design
if {[get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells proc_sys_reset_0]] != 0} {
    error "External reset must be active low after connection to FCLK_RESET0_N."
}
save_bd_design
set bd [get_files -quiet */system.bd]
generate_target all $bd
set wrappers [make_wrapper -files $bd -top]
add_files -norecurse $wrappers
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
regenerate_bd_layout
save_bd_design
puts "DAY9 PROJECT CREATED AND VALIDATED: [file join $lab_dir ${lab_name}.xpr]"
