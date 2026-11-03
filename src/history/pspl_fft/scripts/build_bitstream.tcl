# Source only after create_project.tcl has opened the Day 6 project.
set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {[llength [get_projects -quiet]] == 0} {error "Open the Day 6 project first."}
if {[get_property NAME [current_project]] ne "day6_pspl_fft_project"} {
    error "This script only builds the generated day6_pspl_fft_project."
}
set lab_project_dir [get_property DIRECTORY [current_project]]
set lab_out [file join $lab_root out]
file mkdir $lab_out

# Refuse an old, permanently asserted auxiliary reset before building.
if {[llength [get_designs -quiet]] > 0} {close_design}
set lab_bds [get_files -quiet */system.bd]
if {[llength $lab_bds] != 1} {error "Expected exactly one system.bd: $lab_bds"}
open_bd_design [lindex $lab_bds 0]
if {[get_property CONFIG.C_AUX_RESET_HIGH [get_bd_cells proc_sys_reset_0]] != 1 ||
    [get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells proc_sys_reset_0]] != 0} {
    error "Reset polarity is not fixed. Source scripts/fix_aux_reset.tcl in this project; it repairs and rebuilds it."
}
if {[get_property CONFIG.CONST_VAL [get_bd_cells const_zero]] != 0} {
    error "const_zero must be 0. Review the block design before building."
}
set lab_aux_net [get_bd_nets -quiet -of_objects [get_bd_pins proc_sys_reset_0/aux_reset_in]]
set lab_zero_net [get_bd_nets -quiet -of_objects [get_bd_pins const_zero/dout]]
if {[llength $lab_aux_net] != 1 || $lab_aux_net ne $lab_zero_net} {
    error "aux_reset_in must be tied to const_zero for this design."
}

if {[get_property NEEDS_REFRESH [get_runs synth_1]] &&
    [string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {
    error "Sources have changed. Reset the synthesis/implementation runs in Vivado, then run this script again."
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {
    error "Synthesis did not complete: [get_property STATUS [get_runs synth_1]]. Inspect Messages."
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {
    error "Bitstream generation did not complete: [get_property STATUS [get_runs impl_1]]. Inspect Messages."
}
open_run impl_1
report_timing_summary -file [file join $lab_out day6_timing_summary.rpt]
report_utilization -file [file join $lab_out day6_utilization.rpt]
foreach kind {max min} {
    if {[llength [get_timing_paths -quiet -delay_type $kind -slack_lesser_than 0 -max_paths 1]]} {
        error "Negative $kind timing slack. Inspect day6_timing_summary.rpt before board deployment."
    }
}

set lab_bit [file join [get_property DIRECTORY [get_runs impl_1]] system_wrapper.bit]
if {![file isfile $lab_bit]} {error "Expected bitstream not found: $lab_bit"}
set lab_hwh_candidates {}
foreach suffix {gen srcs} {
    set candidate [file join $lab_project_dir day6_pspl_fft_project.$suffix sources_1 bd system hw_handoff system.hwh]
    if {[file isfile $candidate]} {lappend lab_hwh_candidates $candidate}
}
if {[llength $lab_hwh_candidates] == 0} {
    error "system.hwh not found under .gen or .srcs. Generate all block-design output products and check hw_handoff."
}
set lab_hwh [lindex $lab_hwh_candidates 0]
# Check the generated handoff before exporting the pair. Never edit the HWH.
set lab_stream [open $lab_hwh r]
set lab_hwh_text [read $lab_stream]
close $lab_stream
if {![regexp -indices {<MODULE[[:space:]][^>]*INSTANCE="proc_sys_reset_0"[^>]*>} $lab_hwh_text lab_reset_indices]} {
    error "proc_sys_reset_0 is missing from the generated HWH. Do not upload old output files."
}
set lab_reset_start [lindex $lab_reset_indices 0]
set lab_reset_end [string first {</MODULE>} $lab_hwh_text $lab_reset_start]
if {$lab_reset_end < 0} {error "Incomplete reset module in the generated HWH."}
set lab_reset_text [string range $lab_hwh_text $lab_reset_start $lab_reset_end]
if {![regexp {NAME="C_AUX_RESET_HIGH"[[:space:]]+VALUE="1"} $lab_reset_text] ||
    ![regexp {NAME="C_EXT_RESET_HIGH"[[:space:]]+VALUE="0"} $lab_reset_text]} {
    error "Generated HWH reset polarity is stale or wrong. Do not upload the output pair; regenerate the BD and rebuild."
}
puts "RESET POLARITY CHECK PASSED (C_AUX_RESET_HIGH=1, C_EXT_RESET_HIGH=0)."
file copy -force $lab_bit [file join $lab_out day6_pspl_fft.bit]
file copy -force $lab_hwh [file join $lab_out day6_pspl_fft.hwh]
file copy -force [file join $lab_root python day6_pspl_fft.py] [file join $lab_out day6_pspl_fft.py]
file copy -force [file join $lab_root python check_board.py] [file join $lab_out check_board.py]
set lab_info [open [file join $lab_out build_info.txt] w]
puts $lab_info "Vivado: [version -short]"
puts $lab_info "Part: [get_property PART [current_project]]"
puts $lab_info "Board: [get_property BOARD_PART [current_project]]"
puts $lab_info "Nominal PL clock: 100000000 Hz"
puts $lab_info "1000-point frames; LUT peak scale 10000 counts = 1 a.u."
puts $lab_info "PL test divider: 1000000; nominal test rate: 100 samples/s"
puts $lab_info "AXI GPIO ctrl: axi_gpio_ctrl output32/input32; sample: axi_gpio_data input32"
puts $lab_info "Source bitstream: $lab_bit"
puts $lab_info "Source handoff: $lab_hwh"
puts $lab_info "Build time: [clock format [clock seconds]]"
close $lab_info
puts "DAY 6 BUILD FINISHED. Files for upload are in: $lab_out"
puts "Upload day6_pspl_fft.bit, day6_pspl_fft.hwh, day6_pspl_fft.py, and check_board.py to one board folder."
