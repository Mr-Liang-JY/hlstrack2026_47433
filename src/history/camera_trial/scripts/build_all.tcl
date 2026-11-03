set script_dir [file dirname [file normalize [info script]]]
if {[catch {
    source [file join $script_dir run_simulation.tcl]
    source [file join $script_dir run_software_checks.tcl]
    source [file join $script_dir create_project.tcl]
    source [file join $script_dir build_bitstream.tcl]
    source [file join $script_dir package_board.tcl]
} message options]} {
    puts stderr "HDMI BUILD FAILED: $message"
    puts stderr [dict get $options -errorinfo]
    exit 1
}
puts "CAMERA STAGE2 BUILD ALL PASSED, including deployment ZIP."
