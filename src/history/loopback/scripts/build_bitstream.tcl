set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {![llength [get_projects -quiet]] || [get_property NAME [current_project]] ne "comp_loop"} {
    error "Open the Day9 project first with create_project.tcl."
}
set out [file join $lab_root out]
file mkdir $out
if {[get_property NEEDS_REFRESH [get_runs synth_1]] && [string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {
    error "Sources changed. Reset synthesis and implementation runs before rebuilding."
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed; inspect the first ERROR in logs."}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {error "Implementation/bitstream failed."}
open_run impl_1
report_timing_summary -file [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
foreach type {max min} {
    if {[llength [get_timing_paths -quiet -delay_type $type -slack_lesser_than 0 -max_paths 1]]} {
        error "Negative $type slack. Output pair not exported. Inspect timing_summary.rpt."
    }
}
set directory [get_property DIRECTORY [current_project]]
set bit [file join [get_property DIRECTORY [get_runs impl_1]] system_wrapper.bit]
set hwh [file join $directory comp_loop.gen sources_1 bd system hw_handoff system.hwh]
if {![file exists $hwh]} {set hwh [file join $directory comp_loop.srcs sources_1 bd system hw_handoff system.hwh]}
if {![file exists $bit] || ![file exists $hwh]} {error "Matching bit/hwh output not found."}
file copy -force $bit [file join $out day9_shm.bit]
file copy -force $hwh [file join $out day9_shm.hwh]


set stream [open [file join $out build_info.txt] w]
puts $stream "Vivado: [version -short]; part: [get_property PART [current_project]]"
puts $stream "DMA uint32 passthrough; no Sobel or motion algorithm."
puts $stream "AXI DMA simple mode, 23-bit length, DDR via PS HP0, control via GP0."
puts $stream "PL: AXI Stream passthrough. PS: generic array generation and comparison."
puts $stream "Nominal FCLK=100MHz. Build/implementation passed; physical PYNQ test NOT RUN here."
puts $stream "Build time: [clock format [clock seconds]]"
close $stream
puts "DAY9 BUILD FINISHED: $out"
