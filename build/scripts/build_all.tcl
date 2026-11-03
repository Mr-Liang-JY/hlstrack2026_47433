set root [file dirname [file dirname [file normalize [info script]]]]
source [file join $root scripts run_simulation.tcl]
source [file join $root scripts create_project.tcl]
source [file join $root scripts build_bitstream.tcl]
