set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {[llength [get_projects -quiet]]} {error "Close other projects before simulation."}
set_param general.maxThreads 2
set tests {tb_axis_framebuffer tb_video_timing tb_sobel_frame_axis tb_tmds_encoder tb_serializer tb_video_display}
if {[llength $argv]} {set tests $argv}
foreach test $tests {
    set sim_dir [file join $lab_root build sim $test]
    create_project $test $sim_dir -part xc7z020clg400-1 -force
    add_files -norecurse [glob [file join $lab_root rtl *.v]]
    add_files -fileset sim_1 -norecurse [file join $lab_root sim ${test}.sv]
    if {$test eq "tb_sobel_frame_axis"} {
        add_files -fileset sim_1 -norecurse [file join $lab_root sim vectors.txt]
        set_property file_type {Data Files} [get_files */vectors.txt]
    }
    if {$test eq "tb_video_display"} {
        foreach data {native_packet.mem native_golden.mem} {
            add_files -fileset sim_1 -norecurse [file join $lab_root sim $data]
            set_property file_type {Data Files} [get_files */$data]
        }
    }
    set_property top $test [get_filesets sim_1]
    set_property xsim.simulate.runtime all [get_filesets sim_1]
    set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
    launch_simulation
    close_sim
    set logs [glob -nocomplain [file join $sim_dir *.sim sim_1 behav xsim simulate.log]]
    if {![llength $logs]} {set logs [glob -nocomplain [file join $sim_dir *.sim sim_1 behav xsim xsim.log]]}
    if {![llength $logs]} {error "No simulation log: $test"}
    set f [open [lindex $logs 0] r];set result [read $f];close $f
    file copy -force [lindex $logs 0] [file join $lab_root out ${test}.log]
    if {![regexp {PASS } $result] || [regexp {Fatal:|FATAL|ERROR:} $result]} {error "Simulation FAILED: $test"}
    close_project
}
puts "REQUESTED VIDEO/SOBEL SIMULATIONS PASSED: $tests"
