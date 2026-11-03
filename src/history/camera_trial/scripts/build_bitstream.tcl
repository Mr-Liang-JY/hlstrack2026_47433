set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {![llength [get_projects -quiet]] || [get_property NAME [current_project]] ne "camera_stage2"} {error "Run create_project.tcl first."}
set out [file join $lab_root out]
file mkdir $out
set compiled_inputs [dict create]
foreach input_file [concat [glob [file join $lab_root rtl *.v]] [glob [file join $lab_root constraints *.xdc]]] {
    set f [open $input_file rb]; dict set compiled_inputs $input_file [read $f]; close $f
}
# Module-reference OOC runs can otherwise retain an old checkpoint after a body edit.
# Keep a separate stamp, written only after verifying the actual implemented netlist.
set rtl_changed 0
foreach input_file [glob [file join $lab_root rtl *.v]] {
    set stamp [file join $lab_root build module_sources [file tail $input_file]]
    if {![file exists $stamp]} {set rtl_changed 1;break}
    set f [open $stamp rb];set previous [read $f];close $f
    if {$previous ne [dict get $compiled_inputs $input_file]} {set rtl_changed 1;break}
}
if {$rtl_changed} {
    open_bd_design [get_files */system.bd]
    update_compile_order -fileset sources_1
    set module_ips [get_ips -all -quiet *camera_video*]
    if {![llength $module_ips]} {error "Camera module-reference IP not found."}
    update_module_reference -verbose $module_ips
    validate_bd_design
    save_bd_design
    generate_target all [get_files */system.bd]
    create_ip_run [get_files */system.bd]
    update_compile_order -fileset sources_1
    set module_runs [get_runs -quiet *camera_video*_synth_1]
    if {![llength $module_runs]} {error "Camera module synthesis run not found."}
    foreach module_run $module_runs {reset_run $module_run}
    reset_run synth_1
}
if {[get_property NEEDS_REFRESH [get_runs synth_1]] || [string match {*ERROR*} [get_property STATUS [get_runs synth_1]]]} {
    reset_run synth_1
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
}
if {![string match {*synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed."}
set_property STEPS.INIT_DESIGN.TCL.POST [file join $lab_root scripts check_constraints.tcl] [get_runs impl_1]
if {[get_property NEEDS_REFRESH [get_runs impl_1]] && [string match {*Complete*} [get_property STATUS [get_runs impl_1]]]} {
    reset_run impl_1
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
}
if {![string match {*write_bitstream Complete*} [get_property STATUS [get_runs impl_1]]]} {error "Implementation failed."}
open_run impl_1
if {![llength [get_cells -hier -quiet -regexp {.*\/capture_request_reset_reg}]]} {
    error "Stale camera module checkpoint: reset-request register missing."
}
report_timing_summary -report_unconstrained -file [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -details -file [file join $out cdc.rpt]
set f [open [file join $out cdc.rpt] r];set cdc_text [read $f];close $f
if {[regexp {CDC-[0-9]+\s+Critical} $cdc_text]} {error "Critical CDC findings remain; outputs not exported."}
report_clock_interaction -file [file join $out clock_interaction.rpt]
report_exceptions -file [file join $out timing_exceptions.rpt]

foreach type {max min} {
    if {[llength [get_timing_paths -quiet -delay_type $type -slack_lesser_than 0 -max_paths 1]]} {error "Negative $type slack; outputs not exported."}
}
set bad_drc [get_drc_violations -quiet -filter {SEVERITY == Error}]
if {[llength $bad_drc]} {error "DRC errors remain: $bad_drc"}
set f [open [file join $out drc.rpt] r];set drc_text [read $f];close $f
if {[regexp {REQP-1839} $drc_text]} {error "BRAM async-control warning remains; verify module refresh."}
set hwh [file join [get_property DIRECTORY [current_project]] camera_stage2.gen sources_1 bd system hw_handoff system.hwh]
set bit [file join [get_property DIRECTORY [get_runs impl_1]] system_wrapper.bit]
if {![file exists $bit] || ![file exists $hwh]} {error "Matching bit/hwh not found."}
file copy -force $bit [file join $out camera_stage2.bit]
file copy -force $hwh [file join $out camera_stage2.hwh]
dict for {input_file original_bytes} $compiled_inputs {
    set f [open $input_file rb]; set now_bytes [read $f]; close $f
    if {$now_bytes ne $original_bytes} {error "Source changed while building; rebuild required: $input_file"}
    set relative [file join [file tail [file dirname $input_file]] [file tail $input_file]]
    set saved_file [file join $out build_sources $relative]
    file mkdir [file dirname $saved_file]
    set f [open $saved_file wb]; puts -nonewline $f $original_bytes; close $f
    if {[file tail [file dirname $input_file]] eq "rtl"} {
        set stamp [file join $lab_root build module_sources [file tail $input_file]]
        file mkdir [file dirname $stamp]
        set f [open $stamp wb];puts -nonewline $f $original_bytes;close $f
    }
}
set f [open [file join $out build_info.txt] w]
puts $f "Vivado: [version -short]; part: xc7z020clg400-1"
puts $f "640x480 RGB, 800x525 total, target pixel 25.2MHz; serial 126MHz DDR."
puts $f "PS FCLK0=100MHz; PS SCCB setup; camera 24MHz; PL DVP -> 2-bank BRAM -> HDMI OUT."
puts $f "Control GPIO defaults zero: camera XCLK off, reset asserted, capture off. Status [31:16]=0xCA02."
puts $f "Physical board/display observations are separate from synthesis and simulation."
puts $f "Built: [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S %z}]"
close $f
puts "HDMI BIT/HWH EXPORTED: $out"
