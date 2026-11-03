# Source only after create_project.tcl has opened the Day 5 project.
set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {[llength [get_projects -quiet]] == 0} {error "Open the Day 5 project first."}
if {[get_property NAME [current_project]] ne "day5_pspl_project"} {
    error "This script only builds the generated day5_pspl_project."
}
set lab_project_dir [get_property DIRECTORY [current_project]]
set lab_out [file join $lab_root out]
file mkdir $lab_out

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
report_timing_summary -file [file join $lab_out day5_timing_summary.rpt]
report_utilization -file [file join $lab_out day5_utilization.rpt]
foreach kind {max min} {
    if {[llength [get_timing_paths -quiet -delay_type $kind -slack_lesser_than 0 -max_paths 1]]} {
        error "Negative $kind timing slack. Inspect day5_timing_summary.rpt before board deployment."
    }
}

set lab_bit [file join [get_property DIRECTORY [get_runs impl_1]] system_wrapper.bit]
if {![file isfile $lab_bit]} {error "Expected bitstream not found: $lab_bit"}
set lab_hwh_candidates {}
foreach suffix {gen srcs} {
    set candidate [file join $lab_project_dir day5_pspl_project.$suffix sources_1 bd system hw_handoff system.hwh]
    if {[file isfile $candidate]} {lappend lab_hwh_candidates $candidate}
}
if {[llength $lab_hwh_candidates] == 0} {
    error "system.hwh not found under .gen or .srcs. Generate all block-design output products and check hw_handoff."
}
set lab_hwh [lindex $lab_hwh_candidates 0]
file copy -force $lab_bit [file join $lab_out day5_pspl.bit]
file copy -force $lab_hwh [file join $lab_out day5_pspl.hwh]
file copy -force [file join $lab_root python day5_pspl.py] [file join $lab_out day5_pspl.py]
file copy -force [file join $lab_root python check_board.py] [file join $lab_out check_board.py]
set lab_info [open [file join $lab_out build_info.txt] w]
puts $lab_info "Vivado: [version -short]"
puts $lab_info "Part: [get_property PART [current_project]]"
puts $lab_info "Board: [get_property BOARD_PART [current_project]]"
puts $lab_info "Nominal PL clock: 100000000 Hz"
puts $lab_info "PL test divider: 1000000; nominal test rate: 100 samples/s"
puts $lab_info "AXI GPIO: axi_gpio_0; channel1 output32; channel2 input32"
puts $lab_info "Source bitstream: $lab_bit"
puts $lab_info "Source handoff: $lab_hwh"
puts $lab_info "Build time: [clock format [clock seconds]]"
close $lab_info
puts "DAY 5 BUILD FINISHED. Files for upload are in: $lab_out"
puts "Upload day5_pspl.bit, day5_pspl.hwh, day5_pspl.py, and check_board.py to one board folder."
