set lab_root [file dirname [file dirname [file normalize [info script]]]]
set lab_name hdmi_stage1
set lab_dir [file join $lab_root build $lab_name]
if {[llength [get_projects -quiet]]} {error "Save and close your current project first."}
set_param general.maxThreads 2
set_param board.repoPaths [concat [get_param board.repoPaths] [list [file join $lab_root board_files]]]
if {[file exists [file join $lab_dir ${lab_name}.xpr]]} {
    open_project [file join $lab_dir ${lab_name}.xpr]
    puts "Opened existing project. Reset synthesis/implementation after editing RTL."
    return
}
if {![llength [get_parts -quiet xc7z020clg400-1]]} {error "Zynq-7000 device support is not installed."}
create_project $lab_name $lab_dir -part xc7z020clg400-1
set boards [get_board_parts -quiet *pynq-z2*]
if {![llength $boards]} {error "Bundled PYNQ-Z2 board definition not found."}
set_property board_part [lindex $boards 0] [current_project]
set_property target_language Verilog [current_project]
add_files -norecurse [glob [file join $lab_root rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $lab_root constraints pynq_z2_hdmi.xdc]
update_compile_order -fileset sources_1
proc lab_ip {pattern} {
    set defs [lsort -dictionary [get_ipdefs -all -quiet $pattern]]
    if {![llength $defs]} {error "IP not installed: $pattern"}
    return [lindex $defs end]
}
create_bd_design system
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:processing_system7:*] processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1"} [get_bd_cells processing_system7_0]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000}] [get_bd_cells processing_system7_0]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:clk_wiz:*] video_clocks
set_property -dict [list CONFIG.PRIM_IN_FREQ {100.000} CONFIG.PRIMITIVE {MMCM} CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {25.200} CONFIG.CLKOUT2_USED {true} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {126.000} CONFIG.RESET_TYPE {ACTIVE_LOW} \
    CONFIG.USE_LOCKED {true}] [get_bd_cells video_clocks]
create_bd_cell -type module -reference hdmi_video hdmi_video_0
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins video_clocks/clk_in1] [get_bd_pins hdmi_video_0/ref_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins video_clocks/resetn] [get_bd_pins hdmi_video_0/resetn]
connect_bd_net [get_bd_pins video_clocks/clk_out1] [get_bd_pins hdmi_video_0/pixel_clk]
connect_bd_net [get_bd_pins video_clocks/clk_out2] [get_bd_pins hdmi_video_0/serial_clk]
connect_bd_net [get_bd_pins video_clocks/locked] [get_bd_pins hdmi_video_0/locked]
foreach pin {button_reset hdmi_hpd_n} {
    create_bd_port -dir I $pin
    connect_bd_net [get_bd_ports $pin] [get_bd_pins hdmi_video_0/$pin]
}
foreach pin {hdmi_clk_p hdmi_clk_n} {
    create_bd_port -dir O $pin
    connect_bd_net [get_bd_ports $pin] [get_bd_pins hdmi_video_0/$pin]
}
foreach {pin msb} {hdmi_data_p 2 hdmi_data_n 2 leds 3} {
    create_bd_port -dir O -from $msb -to 0 $pin
    connect_bd_net [get_bd_ports $pin] [get_bd_pins hdmi_video_0/$pin]
}
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_gpio:*] axi_gpio_status
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_INPUTS {1} \
    CONFIG.C_ALL_OUTPUTS {0} CONFIG.C_IS_DUAL {0} CONFIG.C_INTERRUPT_PRESENT {0}] [get_bd_cells axi_gpio_status]
connect_bd_net [get_bd_pins hdmi_video_0/status] [get_bd_pins axi_gpio_status/gpio_io_i]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:axi_interconnect:*] control_interconnect
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] [get_bd_cells control_interconnect]
connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] [get_bd_intf_pins control_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_interconnect/M00_AXI] [get_bd_intf_pins axi_gpio_status/S_AXI]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:proc_sys_reset:*] proc_sys_reset_0
set_property CONFIG.C_AUX_RESET_HIGH {1} [get_bd_cells proc_sys_reset_0]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:xlconstant:*] const_zero
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] [get_bd_cells const_zero]
create_bd_cell -type ip -vlnv [lab_ip xilinx.com:ip:xlconstant:*] const_one
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells const_one]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins const_zero/dout] [get_bd_pins proc_sys_reset_0/aux_reset_in] [get_bd_pins proc_sys_reset_0/mb_debug_sys_rst]
connect_bd_net [get_bd_pins const_one/dout] [get_bd_pins proc_sys_reset_0/dcm_locked]
foreach pin {processing_system7_0/M_AXI_GP0_ACLK axi_gpio_status/s_axi_aclk \
    control_interconnect/ACLK control_interconnect/S00_ACLK control_interconnect/M00_ACLK \
    proc_sys_reset_0/slowest_sync_clk} {
    connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins $pin]
}
foreach pin {control_interconnect/ARESETN control_interconnect/S00_ARESETN control_interconnect/M00_ARESETN} {
    connect_bd_net [get_bd_pins proc_sys_reset_0/interconnect_aresetn] [get_bd_pins $pin]
}
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins axi_gpio_status/s_axi_aresetn]
assign_bd_address
validate_bd_design
if {[get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells proc_sys_reset_0]] != 0} {error "PS reset polarity must be active low."}
save_bd_design
regenerate_bd_layout
generate_target all [get_files */system.bd]
add_files -norecurse [make_wrapper -files [get_files */system.bd] -top]
set_property top system_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1
puts "HDMI PROJECT CREATED: [file join $lab_dir ${lab_name}.xpr]"
puts "Clock wizard parameters:"
foreach p {CONFIG.MMCM_CLKFBOUT_MULT_F CONFIG.MMCM_DIVCLK_DIVIDE CONFIG.MMCM_CLKOUT0_DIVIDE_F CONFIG.MMCM_CLKOUT1_DIVIDE} {
    puts "$p = [get_property $p [get_bd_cells video_clocks]]"
}
