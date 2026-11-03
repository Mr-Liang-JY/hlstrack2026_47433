set r [file dirname [file dirname [file normalize [info script]]]]
source [file join $r scripts create_project.tcl]
source [file join $r scripts build_bitstream.tcl]
