# Run in Vivado Tcl Console after saving/closing any existing project:
# source C:/fpga_lab/day5_pspl/scripts/create_project.tcl
# Requires Zynq-7000 device support. Board definitions are bundled locally.
set lab_root [file dirname [file dirname [file normalize [info script]]]]
set lab_project_name day5_pspl_project
set lab_project_dir [file join $lab_root build $lab_project_name]
set lab_xpr [file join $lab_project_dir ${lab_project_name}.xpr]

if {[llength [get_projects -quiet]] > 0} {
    error "Save and close the current Vivado project first, then source this script again."
}
if {[file exists $lab_xpr]} {
    open_project $lab_xpr
    puts "Existing Day 5 project opened: $lab_xpr"
    puts "Inspect the diagram, then source scripts/build_bitstream.tcl."
    return
}
if {[llength [get_parts -quiet xc7z020clg400-1]] == 0} {
    error "Zynq-7000 part xc7z020clg400-1 is unavailable. Add its device support to this Vivado installation."
}
set lab_board_repo [file join $lab_root board_files]
set_param board.repoPaths [concat [get_param board.repoPaths] [list $lab_board_repo]]
set lab_board_parts [get_board_parts -quiet *pynq-z2*]
if {[llength $lab_board_parts] == 0} {
    error "PYNQ-Z2 board definition was not recognized. Check board_files/pynq-z2/A.0 and device support."
}

proc lab_latest_ip {pattern} {
    set definitions [lsort -dictionary [get_ipdefs -all -quiet $pattern]]
    if {[llength $definitions] == 0} {error "Required IP not installed: $pattern"}
    return [lindex $definitions end]
}

create_project $lab_project_name $lab_project_dir -part xc7z020clg400-1
set_property board_part [lindex $lab_board_parts 0] [current_project]
set_property target_language Verilog [current_project]
add_files -norecurse [list [file join $lab_root rtl sample_buffer.v] \
                         [file join $lab_root rtl pspl_capture_top.v]]
update_compile_order -fileset sources_1
create_bd_design system

create_bd_cell -type ip -vlnv [lab_latest_ip xilinx.com:ip:processing_system7:*] processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1"} \
    [get_bd_cells processing_system7_0]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000}] \
    [get_bd_cells processing_system7_0]

create_bd_cell -type ip -vlnv [lab_latest_ip xilinx.com:ip:axi_gpio:*] axi_gpio_0
set_property -dict [list CONFIG.C_IS_DUAL {1} \
    CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_INPUTS {0} CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_DOUT_DEFAULT {0x00000000} \
    CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_ALL_OUTPUTS_2 {0} \
    CONFIG.C_INTERRUPT_PRESENT {0}] [get_bd_cells axi_gpio_0]

create_bd_cell -type ip -vlnv [lab_latest_ip xilinx.com:ip:axi_interconnect:*] axi_interconnect_0
set_property CONFIG.NUM_MI {1} [get_bd_cells axi_interconnect_0]
create_bd_cell -type ip -vlnv [lab_latest_ip xilinx.com:ip:proc_sys_reset:*] proc_sys_reset_0
set_property CONFIG.C_EXT_RESET_HIGH {0} [get_bd_cells proc_sys_reset_0]
set_property CONFIG.C_AUX_RESET_HIGH {1} [get_bd_cells proc_sys_reset_0]
create_bd_cell -type ip -vlnv [lab_latest_ip xilinx.com:ip:xlconstant:*] const_one
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells const_one]
create_bd_cell -type ip -vlnv [lab_latest_ip xilinx.com:ip:xlconstant:*] const_zero
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] [get_bd_cells const_zero]
create_bd_cell -type module -reference pspl_capture_top pspl_capture_top_0
set_property CONFIG.SAMPLE_DIV {1000000} [get_bd_cells pspl_capture_top_0]

connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] \
                    [get_bd_intf_pins axi_interconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_interconnect_0/M00_AXI] \
                    [get_bd_intf_pins axi_gpio_0/S_AXI]

foreach pin {
    processing_system7_0/M_AXI_GP0_ACLK
    axi_interconnect_0/ACLK
    axi_interconnect_0/S00_ACLK
    axi_interconnect_0/M00_ACLK
    axi_gpio_0/s_axi_aclk
    proc_sys_reset_0/slowest_sync_clk
    pspl_capture_top_0/clk
} {
    connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins $pin]
}
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] \
               [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins const_one/dout] [get_bd_pins proc_sys_reset_0/dcm_locked]
connect_bd_net [get_bd_pins const_zero/dout] [get_bd_pins proc_sys_reset_0/aux_reset_in]
connect_bd_net [get_bd_pins const_zero/dout] [get_bd_pins proc_sys_reset_0/mb_debug_sys_rst]
foreach pin {axi_interconnect_0/ARESETN axi_interconnect_0/S00_ARESETN axi_interconnect_0/M00_ARESETN} {
    connect_bd_net [get_bd_pins proc_sys_reset_0/interconnect_aresetn] [get_bd_pins $pin]
}
foreach pin {axi_gpio_0/s_axi_aresetn pspl_capture_top_0/resetn} {
    connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins $pin]
}
connect_bd_net [get_bd_pins axi_gpio_0/gpio_io_o] [get_bd_pins pspl_capture_top_0/ps_control]
connect_bd_net [get_bd_pins pspl_capture_top_0/pl_status] [get_bd_pins axi_gpio_0/gpio2_io_i]

assign_bd_address
validate_bd_design
save_bd_design
set lab_bd [get_files -quiet */system.bd]
if {[llength $lab_bd] != 1} {error "Expected one system.bd, found: $lab_bd"}
generate_target all $lab_bd
set lab_wrappers [make_wrapper -files $lab_bd -top]
add_files -norecurse $lab_wrappers
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
regenerate_bd_layout
save_bd_design

puts "DAY 5 PROJECT CREATED: $lab_xpr"
puts "PL clock: 100 MHz; test ramp sample divider: 1000000 (nominal 100 samples/s)."
puts "GPIO channel 1: 32-bit output; channel 2: 32-bit input."
puts "Next: inspect system.bd, then source scripts/build_bitstream.tcl."
