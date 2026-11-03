set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {[llength [get_projects -quiet]]} {error "Close the current project before running standalone simulation."}
file mkdir [file join $lab_root out]
if {![info exists lab_tests]} {set lab_tests {tb_dvp_framebuffer tb_cdc_counter tb_video_timing tb_tmds_encoder tb_serializer}}
foreach test $lab_tests {
    set sim_dir [file join $lab_root build sim $test]
    create_project $test $sim_dir -part xc7z020clg400-1 -force
    add_files -norecurse [glob [file join $lab_root rtl *.v]]
    add_files -fileset sim_1 -norecurse [file join $lab_root sim ${test}.sv]
    set_property top $test [get_filesets sim_1]
    set_property xsim.simulate.runtime all [get_filesets sim_1]
    set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
    launch_simulation
    close_sim
    set logs [glob -nocomplain [file join $sim_dir *.sim sim_1 behav xsim simulate.log]]
    if {![llength $logs]} {set logs [glob -nocomplain [file join $sim_dir *.sim sim_1 behav xsim xsim.log]]}
    if {![llength $logs]} {error "Simulation log not found: $test"}
    set f [open [lindex $logs 0] r]; set contents [read $f]; close $f
    file copy -force [lindex $logs 0] [file join $lab_root out ${test}.log]
    if {![regexp {PASS } $contents] || [regexp {Fatal:|FATAL|ERROR:} $contents]} {error "Simulation failed: $test"}
    close_project
}
puts "ALL HDMI SIMULATIONS PASSED"
