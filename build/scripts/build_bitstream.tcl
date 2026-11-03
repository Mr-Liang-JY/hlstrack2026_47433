set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {![llength [get_projects -quiet]] || [get_property NAME [current_project]] ne "award_video"} {error "Run create_project.tcl first."}
set out [file join $lab_root out]
file mkdir $out
set compiled_inputs [dict create]
foreach input_file [concat [glob [file join $lab_root rtl *.v]] [glob [file join $lab_root constraints *.xdc]]] {
    set f [open $input_file rb]; dict set compiled_inputs $input_file [read $f]; close $f
}
if {[get_property NEEDS_REFRESH [get_runs synth_1]] && [string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {
    reset_run synth_1
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed."}
if {[get_property NEEDS_REFRESH [get_runs impl_1]] && [string match {*Complete*} [get_property STATUS [get_runs impl_1]]]} {
    reset_run impl_1
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {error "Implementation failed."}
open_run impl_1
report_timing_summary -report_unconstrained -file [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -file [file join $out cdc.rpt]
report_clock_interaction -file [file join $out clock_interaction.rpt]
report_exceptions -file [file join $out timing_exceptions.rpt]
foreach type {max min} {
    if {[llength [get_timing_paths -quiet -delay_type $type -slack_lesser_than 0 -max_paths 1]]} {error "Negative $type slack; outputs not exported."}
}
set bad_drc [get_drc_violations -quiet -filter {SEVERITY == Error}]
if {[llength $bad_drc]} {error "DRC errors remain: $bad_drc"}
set hwh [file join [get_property DIRECTORY [current_project]] award_video.gen sources_1 bd system hw_handoff system.hwh]
set bit [file join [get_property DIRECTORY [get_runs impl_1]] system_wrapper.bit]
if {![file exists $bit] || ![file exists $hwh]} {error "Matching bit/hwh not found."}
file copy -force $bit [file join $out award_video.bit]
file copy -force $hwh [file join $out award_video.hwh]
dict for {input_file original_bytes} $compiled_inputs {
    set f [open $input_file rb]; set now_bytes [read $f]; close $f
    if {$now_bytes ne $original_bytes} {error "Source changed while building; rebuild required: $input_file"}
    set relative [file join [file tail [file dirname $input_file]] [file tail $input_file]]
    set saved_file [file join $out build_sources $relative]
    file mkdir [file dirname $saved_file]
    set f [open $saved_file wb]; puts -nonewline $f $original_bytes; close $f
}
set f [open [file join $out build_info.txt] w]
puts $f "Vivado: [version -short]; part: xc7z020clg400-1"
puts $f "1280x720 60Hz, 1650x750 total, pixel 74.25MHz; serial 371.25MHz DDR. Native PL compositor, two 128x128 images and 1024-byte metadata, atomic double buffer."
puts $f "PS FCLK0=100MHz; dual DMA Sobel/ROI and framebuffer -> TMDS -> OSERDESE2 -> J11 HDMI OUT."
puts $f "display_control status signature [31:24]=0xA8; presented frame count [23:8]."
puts $f "Physical board/display observations are separate from synthesis and simulation."
puts $f "Built: [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S %z}]"
close $f
set manifest_python python
if {[info exists ::env(AWARD_PYTHON)]} {set manifest_python $::env(AWARD_PYTHON)}
puts [exec $manifest_python -I [file join $lab_root scripts export_manifest.py]]
puts "HDMI BIT/HWH EXPORTED: $out"
